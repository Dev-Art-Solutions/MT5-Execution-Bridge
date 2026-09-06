from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models.enums import ExecutionStatus
from app.models.signal import SignalCreate
from app.services import risk_service


def _payload(**overrides):
    base = {
        "signal_id": "strategy-EURUSD-0001",
        "timestamp": datetime.now(UTC).isoformat(),
        "symbol": "EURUSD",
        "action": "BUY",
        "risk_percent": 0.5,
        "stop_loss": 1.0850,
    }
    base.update(overrides)
    return base


def test_buy_signal_valid():
    signal = SignalCreate(**_payload(action="BUY"))
    assert signal.action == "BUY"


def test_sell_signal_valid():
    signal = SignalCreate(**_payload(action="SELL", stop_loss=1.0950))
    assert signal.action == "SELL"


def test_invalid_action_rejected():
    with pytest.raises(ValidationError):
        SignalCreate(**_payload(action="HOLD"))


def test_missing_stop_loss_rejected_when_required():
    result = risk_service.check_stop_loss("BUY", None, entry_price=1.09, require_stop_loss=True)
    assert not result.ok
    assert result.status == ExecutionStatus.REJECTED_STOP_LOSS


def test_missing_stop_loss_allowed_when_not_required():
    result = risk_service.check_stop_loss("BUY", None, entry_price=1.09, require_stop_loss=False)
    assert result.ok


def test_stale_signal_rejected():
    old_timestamp = datetime.now(UTC) - timedelta(seconds=120)
    result = risk_service.check_freshness(old_timestamp, max_age_seconds=60)
    assert not result.ok
    assert result.status == ExecutionStatus.REJECTED_STALE


def test_future_signal_rejected():
    future_timestamp = datetime.now(UTC) + timedelta(seconds=30)
    result = risk_service.check_freshness(future_timestamp, max_age_seconds=60)
    assert not result.ok
    assert result.status == ExecutionStatus.REJECTED_FUTURE_TIMESTAMP


def test_fresh_signal_accepted():
    result = risk_service.check_freshness(datetime.now(UTC), max_age_seconds=60)
    assert result.ok


def test_excessive_risk_rejected():
    result = risk_service.check_risk_percent(risk_percent=5.0, max_risk_percent=1.0)
    assert not result.ok
    assert result.status == ExecutionStatus.REJECTED_RISK


def test_risk_within_bounds_accepted():
    result = risk_service.check_risk_percent(risk_percent=0.5, max_risk_percent=1.0)
    assert result.ok
