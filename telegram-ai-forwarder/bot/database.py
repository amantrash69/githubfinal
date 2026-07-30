from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class ForwardingStore:
    """SQLite store that makes processing idempotent across restarts."""
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS processed_messages (
            source_channel TEXT NOT NULL, source_message_id INTEGER NOT NULL,
            processing_status TEXT NOT NULL, target_message_id INTEGER,
            error_message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (source_channel, source_message_id))""")
        self.connection.commit()

    def claim(self, source_channel: str, message_id: int) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.connection.execute("""INSERT OR IGNORE INTO processed_messages
            (source_channel, source_message_id, processing_status, created_at, updated_at)
            VALUES (?, ?, 'processing', ?, ?)""", (source_channel, message_id, now, now))
        self.connection.commit()
        return cursor.rowcount == 1

    def mark_published(self, channel: str, message_id: int, target_id: int) -> None:
        self._update(channel, message_id, "published", target_id, None)

    def mark_failed(self, channel: str, message_id: int, error: str) -> None:
        self._update(channel, message_id, "failed", None, error[:1000])

    def _update(self, channel: str, message_id: int, status: str, target_id: int | None, error: str | None) -> None:
        self.connection.execute("""UPDATE processed_messages SET processing_status=?, target_message_id=?,
            error_message=?, updated_at=? WHERE source_channel=? AND source_message_id=?""",
            (status, target_id, error, datetime.now(timezone.utc).isoformat(), channel, message_id))
        self.connection.commit()

    def status_counts(self) -> dict[str, int]:
        return dict(self.connection.execute("SELECT processing_status, COUNT(*) FROM processed_messages GROUP BY processing_status"))
