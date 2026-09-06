from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.enums import ExecutionStatus, SignalAction

FUTURE_TOLERANCE_SECONDS = 5


@dataclass
class RiskCheckResult:
    ok: bool
    status: ExecutionStatus | None = None
    reason: str | None = None


def check_freshness(signal_timestamp: datetime, max_age_seconds: int, now: datetime | None = None) -> RiskCheckResult:
    now = now or datetime.now(UTC)
    if signal_timestamp.tzinfo is None:
        signal_timestamp = signal_timestamp.replace(tzinfo=UTC)
    age = (now - signal_timestamp).total_seconds()
    if age > max_age_seconds:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_STALE, f"Signal age {age:.1f}s exceeds max {max_age_seconds}s")
    if age < -FUTURE_TOLERANCE_SECONDS:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_FUTURE_TIMESTAMP, f"Signal timestamp is {-age:.1f}s in the future")
    return RiskCheckResult(True)


def check_risk_percent(risk_percent: float, max_risk_percent: float) -> RiskCheckResult:
    if risk_percent <= 0 or risk_percent > max_risk_percent:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_RISK, f"risk_percent {risk_percent} outside (0, {max_risk_percent}]")
    return RiskCheckResult(True)


def check_stop_loss(action: str, stop_loss: float | None, entry_price: float, require_stop_loss: bool) -> RiskCheckResult:
    if stop_loss is None:
        if require_stop_loss:
            return RiskCheckResult(False, ExecutionStatus.REJECTED_STOP_LOSS, "stop_loss is required")
        return RiskCheckResult(True)
    if action == SignalAction.BUY.value and stop_loss >= entry_price:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_STOP_LOSS, "BUY stop_loss must be below entry price")
    if action == SignalAction.SELL.value and stop_loss <= entry_price:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_STOP_LOSS, "SELL stop_loss must be above entry price")
    return RiskCheckResult(True)


def check_spread(bid: float, ask: float, point: float, max_spread_points: int) -> RiskCheckResult:
    if bid <= 0 or ask <= 0 or point <= 0 or ask < bid:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_SPREAD, "Invalid quote data")
    spread_points = (ask - bid) / point
    if spread_points > max_spread_points:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_SPREAD, f"Spread {spread_points:.1f} points exceeds max {max_spread_points}")
    return RiskCheckResult(True)


def check_daily_trade_limit(trades_today: int, max_trades_per_day: int) -> RiskCheckResult:
    if trades_today >= max_trades_per_day:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_DAILY_TRADE_LIMIT, f"{trades_today} bridge trades already executed today")
    return RiskCheckResult(True)


def check_position_limit(open_positions: int, max_open_positions: int) -> RiskCheckResult:
    if open_positions >= max_open_positions:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_POSITION_LIMIT, f"{open_positions} bridge positions already open")
    return RiskCheckResult(True)


def check_daily_loss(current_equity: float, baseline_equity: float, max_daily_loss_percent: float) -> RiskCheckResult:
    if baseline_equity <= 0:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_DAILY_LOSS, "Invalid baseline equity")
    loss_percent = (baseline_equity - current_equity) / baseline_equity * 100.0
    if loss_percent >= max_daily_loss_percent:
        return RiskCheckResult(False, ExecutionStatus.REJECTED_DAILY_LOSS, f"Daily loss {loss_percent:.2f}% exceeds max {max_daily_loss_percent}%")
    return RiskCheckResult(True)


def trading_day_key(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return now.strftime("%Y-%m-%d")


def start_of_trading_day(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return datetime(now.year, now.month, now.day, tzinfo=UTC)
