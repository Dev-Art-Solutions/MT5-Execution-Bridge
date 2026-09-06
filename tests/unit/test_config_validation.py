import math

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models.signal import SignalCreate


def _base_settings(**overrides):
    return Settings(database_path=":memory:", symbol_map_path="unused.json", **overrides)


def test_default_settings_are_valid():
    settings = _base_settings()
    assert settings.max_risk_percent == 1.0


@pytest.mark.parametrize("field,value", [
    ("max_risk_percent", 0),
    ("max_risk_percent", 101),
    ("max_daily_loss_percent", -1),
    ("max_daily_loss_percent", 0),
    ("max_open_positions", 0),
    ("max_trades_per_day", 0),
    ("max_spread_points", 0),
    ("magic_number", -1),
    ("max_signal_age_seconds", 0),
    ("port", 0),
    ("port", 70000),
])
def test_invalid_settings_rejected(field, value):
    with pytest.raises(ValidationError):
        _base_settings(**{field: value})


@pytest.mark.parametrize("field", ["max_risk_percent", "max_daily_loss_percent"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_settings_rejected(field, value):
    with pytest.raises(ValidationError):
        _base_settings(**{field: value})


def test_live_execution_requires_server_and_login():
    with pytest.raises(ValidationError):
        _base_settings(dry_run=False, live_execution_enabled=True, mt5_server="", mt5_login="")


def test_live_execution_requires_numeric_login():
    with pytest.raises(ValidationError):
        _base_settings(dry_run=False, live_execution_enabled=True, mt5_server="VSCapital-Demo", mt5_login="not-a-number")


def test_live_execution_allowed_without_password():
    settings = _base_settings(
        dry_run=False, live_execution_enabled=True, mt5_server="VSCapital-Demo", mt5_login="12345", mt5_password="",
    )
    assert settings.live_execution_allowed is True


def _signal_payload(**overrides):
    base = {
        "signal_id": "cfg-test-0001",
        "timestamp": "2026-09-06T00:00:00Z",
        "symbol": "EURUSD",
        "action": "BUY",
        "risk_percent": 0.5,
        "stop_loss": 1.0850,
    }
    base.update(overrides)
    return base


def test_signal_risk_percent_nan_rejected():
    with pytest.raises(ValidationError):
        SignalCreate(**_signal_payload(risk_percent=math.nan))


def test_signal_stop_loss_infinity_rejected():
    with pytest.raises(ValidationError):
        SignalCreate(**_signal_payload(stop_loss=math.inf))


def test_signal_take_profit_infinity_rejected():
    with pytest.raises(ValidationError):
        SignalCreate(**_signal_payload(take_profit=math.inf))


def test_signal_risk_percent_over_100_rejected():
    with pytest.raises(ValidationError):
        SignalCreate(**_signal_payload(risk_percent=150))


def test_signal_stop_loss_non_positive_rejected():
    with pytest.raises(ValidationError):
        SignalCreate(**_signal_payload(stop_loss=-1.0))
