"""Run locally once to generate SESSION_STRING; do not use this in production."""
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main() -> None:
    load_dotenv()
    api_id, api_hash = os.getenv("API_ID"), os.getenv("API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("Set API_ID and API_HASH in your local .env first.")
    async with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        print("SESSION_STRING=" + client.session.save())

asyncio.run(main())
