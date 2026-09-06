from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.storage.migrations import SCHEMA_STATEMENTS


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    """Thread-safe SQLite wrapper acting as durable queue + idempotency + audit store."""

    def __init__(self, path: str) -> None:
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            for statement in SCHEMA_STATEMENTS:
                self._conn.execute(statement)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- signals ---------------------------------------------------------

    def insert_signal_if_new(self, signal: dict[str, Any]) -> tuple[sqlite3.Row, bool]:
        """Atomically insert a signal. Returns (row, created)."""
        now = _utcnow_iso()
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT OR IGNORE INTO signals (
                    signal_id, received_at, signal_timestamp, symbol_raw, symbol_normalized,
                    action, risk_percent, stop_loss, take_profit, strategy, comment,
                    status, rejection_reason, attempt_count, last_attempt_at, created_at, updated_at
                ) VALUES (
                    :signal_id, :received_at, :signal_timestamp, :symbol_raw, NULL,
                    :action, :risk_percent, :stop_loss, :take_profit, :strategy, :comment,
                    :status, NULL, 0, NULL, :created_at, :updated_at
                )
                """,
                {
                    "signal_id": signal["signal_id"],
                    "received_at": now,
                    "signal_timestamp": signal["timestamp"],
                    "symbol_raw": signal["symbol"],
                    "action": signal["action"],
                    "risk_percent": signal["risk_percent"],
                    "stop_loss": signal.get("stop_loss"),
                    "take_profit": signal.get("take_profit"),
                    "strategy": signal.get("strategy"),
                    "comment": signal.get("comment"),
                    "status": "PENDING",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            created = cursor.rowcount == 1
            row = self._conn.execute(
                "SELECT * FROM signals WHERE signal_id = ?", (signal["signal_id"],)
            ).fetchone()
            return row, created

    def get_signal(self, signal_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM signals WHERE signal_id = ?", (signal_id,)
            ).fetchone()

    def claim_next_pending(self) -> sqlite3.Row | None:
        """Atomically claim one PENDING signal for processing (PENDING -> PROCESSING)."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT * FROM signals WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            now = _utcnow_iso()
            cursor = self._conn.execute(
                """
                UPDATE signals SET status = 'PROCESSING', attempt_count = attempt_count + 1,
                       last_attempt_at = ?, updated_at = ?
                WHERE signal_id = ? AND status = 'PENDING'
                """,
                (now, now, row["signal_id"]),
            )
            if cursor.rowcount == 0:
                return None
            return self._conn.execute(
                "SELECT * FROM signals WHERE signal_id = ?", (row["signal_id"],)
            ).fetchone()

    def update_signal_status(
        self, signal_id: str, status: str, rejection_reason: str | None = None,
        symbol_normalized: str | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE signals SET status = ?, rejection_reason = ?,
                       symbol_normalized = COALESCE(?, symbol_normalized), updated_at = ?
                WHERE signal_id = ?
                """,
                (status, rejection_reason, symbol_normalized, _utcnow_iso(), signal_id),
            )

    def requeue_signal(self, signal_id: str) -> None:
        """Return a signal to PENDING for a bounded pre-send retry attempt."""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE signals SET status = 'PENDING', updated_at = ? WHERE signal_id = ?",
                (_utcnow_iso(), signal_id),
            )

    def find_stuck_processing(self) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM signals WHERE status = 'PROCESSING'"
            ).fetchall()

    def set_symbol_normalized(self, signal_id: str, symbol_normalized: str) -> None:
        """Persist the resolved broker symbol immediately, before later
        validation steps can fail -- the mapping decision is real audit
        information regardless of what happens to the signal afterward."""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE signals SET symbol_normalized = ?, updated_at = ? WHERE signal_id = ?",
                (symbol_normalized, _utcnow_iso(), signal_id),
            )

    # -- executions --------------------------------------------------------

    def insert_execution(self, record: dict[str, Any]) -> int:
        record = {
            "account_key": None,
            "executed_volume": None,
            "executed_price": None,
            **record,
        }
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO executions (
                    signal_id, account_key, attempt, started_at, finished_at, dry_run, mt5_symbol,
                    requested_action, calculated_volume, entry_price, stop_loss, take_profit,
                    order_check_retcode, order_send_retcode, order_ticket, deal_ticket,
                    executed_volume, executed_price, result_message, status
                ) VALUES (
                    :signal_id, :account_key, :attempt, :started_at, :finished_at, :dry_run, :mt5_symbol,
                    :requested_action, :calculated_volume, :entry_price, :stop_loss, :take_profit,
                    :order_check_retcode, :order_send_retcode, :order_ticket, :deal_ticket,
                    :executed_volume, :executed_price, :result_message, :status
                )
                """,
                record,
            )
            return cursor.lastrowid

    def update_execution(self, execution_id: int, fields: dict[str, Any]) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key} = :{key}" for key in fields)
        params = dict(fields)
        params["id"] = execution_id
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE executions SET {assignments} WHERE id = :id", params
            )

    def get_executions_for_signal(self, signal_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM executions WHERE signal_id = ? ORDER BY attempt ASC",
                (signal_id,),
            ).fetchall()

    def count_executed_trades_since(self, account_key: str, since_iso: str) -> int:
        """Count bridge-originated trades for one account since a timestamp.

        Scoped by account_key so switching MT5 account/server while reusing
        the same SQLite database can never inherit another account's count.
        Counts EXECUTED, EXECUTED_PARTIAL, and RECOVERED_EXECUTED only --
        DRY_RUN_APPROVED, rejections, and failures never occupy a trade slot.
        """
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS n FROM executions
                WHERE status IN ('EXECUTED', 'EXECUTED_PARTIAL', 'RECOVERED_EXECUTED')
                  AND account_key = ? AND started_at >= ?
                """,
                (account_key, since_iso),
            ).fetchone()
            return row["n"] if row else 0

    # -- daily loss baseline -------------------------------------------------

    def get_daily_loss_baseline(self, account_key: str, trading_day: str) -> float | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT baseline_equity FROM daily_loss_baseline WHERE account_key = ? AND trading_day = ?",
                (account_key, trading_day),
            ).fetchone()
            return row["baseline_equity"] if row else None

    def set_daily_loss_baseline(self, account_key: str, trading_day: str, equity: float) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO daily_loss_baseline (account_key, trading_day, baseline_equity, recorded_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(account_key, trading_day) DO NOTHING
                """,
                (account_key, trading_day, equity, _utcnow_iso()),
            )
