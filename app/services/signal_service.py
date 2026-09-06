from __future__ import annotations

import sqlite3

from app.models.signal import SignalCreate
from app.storage.database import Database


class SignalService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def submit(self, signal: SignalCreate) -> tuple[sqlite3.Row, bool]:
        """Persist a signal idempotently. Returns (row, duplicate)."""
        row, created = self._db.insert_signal_if_new(
            {
                "signal_id": signal.signal_id,
                "timestamp": signal.timestamp.isoformat(),
                "symbol": signal.symbol,
                "action": signal.action,
                "risk_percent": signal.risk_percent,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "strategy": signal.strategy,
                "comment": signal.comment,
            }
        )
        return row, not created

    def get(self, signal_id: str) -> sqlite3.Row | None:
        return self._db.get_signal(signal_id)
