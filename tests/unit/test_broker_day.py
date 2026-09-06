from datetime import UTC, datetime

from app.models.enums import ExecutionStatus
from app.services import risk_service
from app.services.execution_service import ExecutionService
from app.storage.database import Database
from tests.unit.test_execution import _submit_and_claim


def test_trading_day_key_reflects_given_broker_time_not_utc_now():
    broker_time = datetime(2026, 9, 7, 1, 30, tzinfo=UTC)
    assert risk_service.trading_day_key(broker_time) == "2026-09-07"


def test_start_of_trading_day_is_midnight_of_given_date():
    broker_time = datetime(2026, 9, 7, 23, 59, tzinfo=UTC)
    assert risk_service.start_of_trading_day(broker_time) == datetime(2026, 9, 7, tzinfo=UTC)


def test_broker_day_drives_daily_state_key_not_wall_clock(gateway, db: Database, symbol_mapper, settings, fake_mt5):
    """UTC 'now' during the test run is irrelevant; the tick's own time decides the day."""
    far_future = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
    fake_mt5.register_tick("EURUSD", bid=1.0900, ask=1.0901, tick_time=int(far_future.timestamp()))

    service = ExecutionService(gateway, db, symbol_mapper, settings)
    row = _submit_and_claim(db, "exec-broker-day")
    status = service.process_signal(row)

    assert status == ExecutionStatus.DRY_RUN_APPROVED
    account_key = f"{fake_mt5.account_server}|{fake_mt5.account_login}"
    baseline = db.get_daily_loss_baseline(account_key, "2030-01-01")
    assert baseline == fake_mt5.account_equity


def test_broker_time_unavailable_fails_closed(gateway, db: Database, symbol_mapper, settings, fake_mt5):
    fake_mt5.ticks["EURUSD"].time = "not-a-timestamp"
    service = ExecutionService(gateway, db, symbol_mapper, settings)
    row = _submit_and_claim(db, "exec-broker-time-unknown")
    status = service.process_signal(row)
    assert status == ExecutionStatus.FAILED_BROKER_TIME_UNKNOWN


def test_missing_account_identity_fails_closed(gateway, db: Database, symbol_mapper, settings, fake_mt5):
    fake_mt5.account_server = ""
    service = ExecutionService(gateway, db, symbol_mapper, settings)
    row = _submit_and_claim(db, "exec-no-identity")
    status = service.process_signal(row)
    assert status == ExecutionStatus.FAILED_MT5_UNAVAILABLE
