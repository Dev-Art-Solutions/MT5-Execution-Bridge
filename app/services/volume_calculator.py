from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.enums import SignalAction
from app.services.mt5_gateway import MT5Gateway

# Stable MetaTrader5 SDK constants (do not require the module to be importable).
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1


@dataclass
class VolumeResult:
    ok: bool
    volume: float | None
    reason: str | None = None


def calculate_risk_based_volume(
    gateway: MT5Gateway,
    symbol: str,
    action: str,
    entry_price: float,
    stop_loss: float,
    equity: float,
    risk_percent: float,
    volume_min: float,
    volume_max: float,
    volume_step: float,
) -> VolumeResult:
    """Derive position size from risk_percent using MT5's own contract math.

    Never rounds up beyond the intended risk; unresolvable calculations reject
    rather than defaulting to a guessed-safe volume.
    """
    if entry_price <= 0 or stop_loss <= 0:
        return VolumeResult(ok=False, volume=None, reason="Invalid entry or stop-loss price")

    order_type = ORDER_TYPE_BUY if action == SignalAction.BUY.value else ORDER_TYPE_SELL

    loss_for_one_lot = gateway.order_calc_profit(order_type, symbol, 1.0, entry_price, stop_loss)
    if loss_for_one_lot is None:
        return VolumeResult(ok=False, volume=None, reason="order_calc_profit failed")

    risk_per_lot = abs(loss_for_one_lot)
    if risk_per_lot <= 0:
        return VolumeResult(ok=False, volume=None, reason="Non-positive per-lot risk")

    allowed_loss = equity * (risk_percent / 100.0)
    raw_volume = allowed_loss / risk_per_lot

    if volume_step <= 0:
        return VolumeResult(ok=False, volume=None, reason="Invalid broker volume_step")

    steps = math.floor(raw_volume / volume_step)
    volume = round(steps * volume_step, 8)

    if volume < volume_min:
        return VolumeResult(ok=False, volume=volume, reason="REJECTED_VOLUME_BELOW_MINIMUM")

    volume = min(volume, volume_max)
    return VolumeResult(ok=True, volume=volume)
