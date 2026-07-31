import os
import asyncio
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from bot.database import init_db
from bot.admin_panel import register_admin_handlers
from bot.message_processor import process_new_message

# --- DUMMY WEB SERVER FOR RENDER ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render requires binding to 0.0.0.0 and dynamically assigns a PORT
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Dummy web server listening on port {port}")
# -----------------------------------

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

if not all([API_ID, API_HASH, SESSION_STRING]):
    raise ValueError("Missing API_ID, API_HASH, or SESSION_STRING in environment variables.")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage())
async def general_message_handler(event):
    await process_new_message(client, event.message)

async def main():
    # 1. Initialize Database
    init_db()
    
    # 2. Start the dummy web server so Render doesn't crash
    await start_web_server()
    
    # 3. Start Telegram Client
    await client.start()
    register_admin_handlers(client)
    
    print("🟢 Bot started. Forwarding system is active.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
