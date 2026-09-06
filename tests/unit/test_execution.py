from datetime import UTC, datetime

from app.models.enums import ExecutionStatus
from app.services.execution_service import ExecutionService
from app.services.mt5_gateway import MT5Gateway
from app.storage.database import Database


def _submit_and_claim(db: Database, signal_id: str = "exec-0001") -> object:
    db.insert_signal_if_new({
        "signal_id": signal_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "symbol": "EURUSD",
        "action": "BUY",
        "risk_percent": 0.5,
        "stop_loss": 1.0850,
        "take_profit": 1.0950,
        "strategy": "test",
        "comment": None,
    })
    return db.claim_next_pending()


def _live_settings(settings):
    return settings.model_copy(update={"dry_run": False, "live_execution_enabled": True})


def test_dry_run_approved(execution_service: ExecutionService, db: Database):
    row = _submit_and_claim(db, "exec-dry-run")
    status = execution_service.process_signal(row)
    assert status == ExecutionStatus.DRY_RUN_APPROVED


def test_order_check_rejected(execution_service: ExecutionService, db: Database, fake_mt5):
    fake_mt5.order_check_retcode = 10006  # TRADE_RETCODE_REJECT
    row = _submit_and_claim(db, "exec-check-reject")
    status = execution_service.process_signal(row)
    assert status == ExecutionStatus.REJECTED_ORDER_CHECK


def test_order_send_rejected(gateway: MT5Gateway, db: Database, symbol_mapper, settings, fake_mt5):
    fake_mt5.order_send_retcode = 10006  # TRADE_RETCODE_REJECT
    live_settings = _live_settings(settings)
    service = ExecutionService(gateway, db, symbol_mapper, live_settings)
    row = _submit_and_claim(db, "exec-send-reject")
    status = service.process_signal(row)
    assert status == ExecutionStatus.FAILED_ORDER_SEND


def test_order_send_success(gateway: MT5Gateway, db: Database, symbol_mapper, settings):
    live_settings = _live_settings(settings)
    service = ExecutionService(gateway, db, symbol_mapper, live_settings)
    row = _submit_and_claim(db, "exec-send-success")
    status = service.process_signal(row)
    assert status == ExecutionStatus.EXECUTED

    executions = db.get_executions_for_signal("exec-send-success")
    assert executions[-1]["order_ticket"] == 555
    assert executions[-1]["deal_ticket"] == 777


def test_ambiguous_execution_state_review_required(gateway: MT5Gateway, db: Database, symbol_mapper, settings, fake_mt5):
    fake_mt5.order_send_result = None

    def _order_send_none(request):
        return None

    fake_mt5.order_send = _order_send_none
    live_settings = _live_settings(settings)
    service = ExecutionService(gateway, db, symbol_mapper, live_settings)
    row = _submit_and_claim(db, "exec-ambiguous")
    status = service.process_signal(row)
    assert status == ExecutionStatus.REVIEW_REQUIRED


def test_order_send_partial_fill_recorded_and_not_retried(gateway: MT5Gateway, db: Database, symbol_mapper, settings, fake_mt5):
    from types import SimpleNamespace

    fake_mt5.order_send_result = SimpleNamespace(
        retcode=10010, comment="partial", order=901, deal=902, volume=0.05, price=1.0901
    )
    live_settings = _live_settings(settings)
    service = ExecutionService(gateway, db, symbol_mapper, live_settings)
    row = _submit_and_claim(db, "exec-partial")
    status = service.process_signal(row)

    assert status == ExecutionStatus.EXECUTED_PARTIAL
    executions = db.get_executions_for_signal("exec-partial")
    assert executions[-1]["order_ticket"] == 901
    assert executions[-1]["executed_volume"] == 0.05
    assert executions[-1]["executed_price"] == 1.0901
    assert len(fake_mt5.sent_requests) == 1  # no second order_send


def test_order_send_placed_is_review_required(gateway: MT5Gateway, db: Database, symbol_mapper, settings, fake_mt5):
    from types import SimpleNamespace

    fake_mt5.order_send_result = SimpleNamespace(retcode=10008, comment="placed", order=1, deal=0)
    live_settings = _live_settings(settings)
    service = ExecutionService(gateway, db, symbol_mapper, live_settings)
    row = _submit_and_claim(db, "exec-placed")
    status = service.process_signal(row)

    assert status == ExecutionStatus.REVIEW_REQUIRED
    assert len(fake_mt5.sent_requests) == 1  # no second order_send


def test_order_send_done_still_executed(gateway: MT5Gateway, db: Database, symbol_mapper, settings, fake_mt5):
    live_settings = _live_settings(settings)
    service = ExecutionService(gateway, db, symbol_mapper, live_settings)
    row = _submit_and_claim(db, "exec-done")
    status = service.process_signal(row)
    assert status == ExecutionStatus.EXECUTED


def test_positions_query_failure_fails_closed(execution_service: ExecutionService, db: Database, fake_mt5):
    fake_mt5.positions_fail = True
    row = _submit_and_claim(db, "exec-positions-unknown")
    status = execution_service.process_signal(row)

    assert status == ExecutionStatus.FAILED_MT5_STATE_UNKNOWN
    assert len(fake_mt5.checked_requests) == 0  # order_check never reached
    assert len(fake_mt5.sent_requests) == 0  # order_send never reached


def test_symbol_normalized_persisted_even_on_later_rejection(execution_service: ExecutionService, db: Database, fake_mt5):
    fake_mt5.positions_fail = True  # forces a later-stage failure
    row = _submit_and_claim(db, "exec-symbol-persist")
    execution_service.process_signal(row)

    signal = db.get_signal("exec-symbol-persist")
    assert signal["symbol_normalized"] == "EURUSD"
