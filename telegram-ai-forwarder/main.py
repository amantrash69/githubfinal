from __future__ import annotations

import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from bot.config import Settings
from bot.database import ForwardingStore
from bot.telegram_client import TelegramForwarder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

async def main() -> None:
    settings = Settings.from_environment()
    store = ForwardingStore(settings.database_path)
    forwarder = TelegramForwarder(settings, store)
    app = FastAPI()
    @app.get("/")
    async def health() -> dict[str, object]:
        return {"status": "Telegram AI Forwarder is running", "messages": store.status_counts()}
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=settings.port, log_level="warning"))
    logging.info("Application started")
    await asyncio.gather(server.serve(), forwarder.run())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
