from __future__ import annotations

import logging
from telethon import TelegramClient
from telethon.tl.custom.message import Message

logger = logging.getLogger(__name__)

class Publisher:
    def __init__(self, client: TelegramClient, target: str | int) -> None:
        self.client, self.target = client, target

    async def publish(self, original: Message, text: str) -> Message:
        """Reuse Telegram's remote media reference; never persist a local copy."""
        if original.media:
            try:
                return await self.client.send_file(self.target, original.media, caption=text)
            except Exception:
                logger.exception("Media repost failed; using text-only fallback")
        return await self.client.send_message(self.target, text, link_preview=False)
