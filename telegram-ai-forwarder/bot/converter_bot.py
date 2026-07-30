from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient
from telethon.errors import RPCError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .config import Settings

logger = logging.getLogger(__name__)


class ConverterBot:
    """Sends full source-post text to an existing Telegram conversion bot."""

    def __init__(self, client: TelegramClient, settings: Settings) -> None:
        self.client = client
        self.username = settings.converter_bot_username
        # A single conversation avoids matching one post with another post's reply.
        self._lock = asyncio.Lock()

    @retry(retry=retry_if_exception_type(RPCError), wait=wait_exponential_jitter(initial=1, max=20),
           stop=stop_after_attempt(3), reraise=True)
    async def convert(self, original_text: str) -> str:
        if not original_text.strip():
            raise ValueError("The source post has no text/caption to send to the converter bot")
        async with self._lock:
            logger.info("Sending full source post to converter bot @%s", self.username)
            async with self.client.conversation(self.username, timeout=90, exclusive=False) as conversation:
                await conversation.send_message(original_text)
                response = await conversation.get_response()
        result = (response.raw_text or "").strip()
        if not result:
            raise ValueError("Converter bot returned an empty message")
        return result
