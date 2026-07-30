from __future__ import annotations

import asyncio
import logging
import re
from telethon import TelegramClient, events
from telethon import functions, types
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message
from .config import Settings
from .database import ForwardingStore
from .converter_bot import ConverterBot
from .publisher import Publisher

logger = logging.getLogger(__name__)

INVITE_LINK_PATTERN = re.compile(r"(?:https?://)?t\.me/(?:joinchat/|\+)([A-Za-z0-9_-]+)", re.IGNORECASE)


async def resolve_chat(client: TelegramClient, reference: str | int):
    """Resolve a username/ID, or join and resolve a private t.me invite link."""
    if isinstance(reference, str):
        match = INVITE_LINK_PATTERN.fullmatch(reference.strip().rstrip("/"))
        if match:
            invite = await client(functions.messages.CheckChatInviteRequest(hash=match.group(1)))
            if isinstance(invite, types.ChatInviteAlready):
                return invite.chat
            # Joining happens only for the Telegram account stored in SESSION_STRING.
            updates = await client(functions.messages.ImportChatInviteRequest(hash=match.group(1)))
            if not updates.chats:
                raise RuntimeError("Telegram accepted the invite but did not return a chat")
            return updates.chats[0]
    return await client.get_entity(reference)

class TelegramForwarder:
    def __init__(self, settings: Settings, store: ForwardingStore) -> None:
        self.settings, self.store = settings, store
        self.client = TelegramClient(StringSession(settings.session_string), settings.api_id, settings.api_hash)

    async def run(self) -> None:
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError("SESSION_STRING is unauthorized. Generate it locally; production will never prompt for login.")
        sources = [await resolve_chat(self.client, item) for item in self.settings.source_channels]
        source_ids = {entity.id for entity in sources}
        target = await resolve_chat(self.client, self.settings.target_channel)
        publisher = Publisher(self.client, target)
        converter = ConverterBot(self.client, self.settings)
        logger.info("Connected to Telegram; monitoring %d source channel(s)", len(source_ids))

        @self.client.on(events.NewMessage(chats=sources))
        async def on_new_message(event: events.NewMessage.Event) -> None:
            # Independent tasks keep updates arriving while the converter replies.
            asyncio.create_task(self._process(event.message, source_ids, converter, publisher))
        await self.client.run_until_disconnected()

    async def _process(self, message: Message, source_ids: set[int], converter: ConverterBot, publisher: Publisher) -> None:
        # Message.chat_id is usually Telegram's marked -100... form; compare the
        # underlying channel ID to the entities resolved during startup.
        peer_channel_id = getattr(message.peer_id, "channel_id", None)
        if message.chat_id is None or peer_channel_id not in source_ids:
            return
        channel = str(message.chat_id)
        if not self.store.claim(channel, message.id):
            logger.info("Skipping duplicate source message %s/%s", channel, message.id)
            return
        try:
            logger.info("New message detected: %s/%s", channel, message.id)
            source_text = (message.raw_text or "").strip()
            if not source_text:
                raise ValueError("Message has no text/caption for the converter bot")
            converted_message = await converter.convert(source_text)
            target = await publisher.publish(message, converted_message)
            self.store.mark_published(channel, message.id, target.id)
            logger.info("Successfully published message %s", target.id)
        except Exception as exc:
            logger.exception("Processing failed for %s/%s", channel, message.id)
            self.store.mark_failed(channel, message.id, str(exc))
