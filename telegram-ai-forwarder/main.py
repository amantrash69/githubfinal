import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from bot.database import init_db
from bot.admin_panel import register_admin_handlers
from bot.message_processor import process_new_message

# Environment Variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

if not all([API_ID, API_HASH, SESSION_STRING]):
    raise ValueError("Missing API_ID, API_HASH, or SESSION_STRING in environment variables.")

# Use StringSession for Render compatibility (ephemeral storage)
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage())
async def general_message_handler(event):
    # Route all incoming messages to the processor
    # The processor itself will check if the source is an enabled source channel
    await process_new_message(client, event.message)

async def main():
    # 1. Initialize SQLite Database
    init_db()
    
    # 2. Start Telegram Client
    await client.start()
    
    # 3. Register Admin Panel Commands
    register_admin_handlers(client)
    
    print("🟢 Bot started. Forwarding system is active.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
