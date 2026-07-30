from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _chat_reference(value: str) -> str | int:
    value = value.strip()
    return int(value) if value.lstrip("-").isdigit() else value.lstrip("@")


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session_string: str
    source_channels: tuple[str | int, ...]
    target_channel: str | int
    converter_bot_username: str
    database_path: Path
    port: int

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv()
        raw_sources = os.getenv("SOURCE_CHANNELS") or os.getenv("SOURCE_CHANNEL", "")
        sources = tuple(_chat_reference(item) for item in raw_sources.split(",") if item.strip())
        if not sources:
            raise ValueError("Set SOURCE_CHANNELS (or SOURCE_CHANNEL) to at least one channel.")
        return cls(
            api_id=int(_required("API_ID")), api_hash=_required("API_HASH"),
            session_string=_required("SESSION_STRING"), source_channels=sources,
            target_channel=_chat_reference(_required("TARGET_CHANNEL")),
            converter_bot_username=_required("CONVERTER_BOT_USERNAME").lstrip("@"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/forwarder.db")),
            port=int(os.getenv("PORT", "10000")),
        )
