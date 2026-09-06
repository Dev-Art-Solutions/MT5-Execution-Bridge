from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionRecord:
    signal_id: str
    attempt: int
    started_at: str
    finished_at: str | None
    dry_run: bool
    mt5_symbol: str | None
    requested_action: str
    calculated_volume: float | None
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    order_check_retcode: int | None
    order_send_retcode: int | None
    order_ticket: int | None
    deal_ticket: int | None
    result_message: str | None
    status: str
