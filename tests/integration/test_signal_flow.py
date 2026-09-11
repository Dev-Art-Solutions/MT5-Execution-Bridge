from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models.enums import ExecutionStatus
from app.services.execution_service import ExecutionService
from app.services.mt5_gateway import MT5Gateway
from app.worker.execution_worker import ExecutionWorker
from tests.fixtures.fake_mt5 import FakeMT5

TERMINAL = {s.value for s in [
    ExecutionStatus.DRY_RUN_APPROVED, ExecutionStatus.EXECUTED, ExecutionStatus.EXECUTED_PARTIAL,
    ExecutionStatus.RECOVERED_EXECUTED,
    ExecutionStatus.REJECTED_STALE, ExecutionStatus.REJECTED_FUTURE_TIMESTAMP, ExecutionStatus.REJECTED_SYMBOL,
    ExecutionStatus.REJECTED_SYMBOL_UNAVAILABLE, ExecutionStatus.REJECTED_RISK, ExecutionStatus.REJECTED_STOP_LOSS,
    ExecutionStatus.REJECTED_SPREAD, ExecutionStatus.REJECTED_DAILY_LOSS, ExecutionStatus.REJECTED_DAILY_TRADE_LIMIT,
    ExecutionStatus.REJECTED_POSITION_LIMIT, ExecutionStatus.REJECTED_VOLUME,
    ExecutionStatus.REJECTED_VOLUME_BELOW_MINIMUM, ExecutionStatus.REJECTED_ORDER_CHECK,
    ExecutionStatus.FAILED_MT5_UNAVAILABLE, ExecutionStatus.FAILED_MT5_STATE_UNKNOWN,
    ExecutionStatus.FAILED_BROKER_TIME_UNKNOWN, ExecutionStatus.FAILED_ORDER_SEND, ExecutionStatus.REVIEW_REQUIRED,
]}


def _build_app(tmp_path, *, dry_run: bool = True, live_execution_enabled: bool = False):
    symbol_map_path = tmp_path / "symbol-map.json"
    symbol_map_path.write_text('{"EURUSD": "EURUSD"}', encoding="utf-8")

    settings = Settings(
        database_path=str(tmp_path / "bridge.db"),
        symbol_map_path=str(symbol_map_path),
        dry_run=dry_run,
        live_execution_enabled=live_execution_enabled,
        mt5_server="VSCapital-Demo" if live_execution_enabled else "",
        mt5_login="12345" if live_execution_enabled else "",
    )
    app = create_app(settings=settings)

    fake = FakeMT5()
    fake.register_symbol("EURUSD")
    fake.register_tick("EURUSD", bid=1.0900, ask=1.0901)
    gateway = MT5Gateway(mt5_module=fake)
    gateway.initialize()

    app.state.gateway = gateway
    app.state.execution_service = ExecutionService(gateway, app.state.db, app.state.symbol_mapper, settings)
    app.state.worker = ExecutionWorker(app.state.db, app.state.execution_service)
    return app, fake


def _wait_for_terminal(client: TestClient, signal_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = client.get(f"/api/signals/{signal_id}").json()
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.1)
    raise AssertionError(f"signal {signal_id} did not reach a terminal status in time: {last}")


def _signal_payload(signal_id: str) -> dict:
    return {
        "signal_id": signal_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "symbol": "EURUSD",
        "action": "BUY",
        "risk_percent": 0.5,
        "stop_loss": 1.0850,
        "take_profit": 1.0950,
    }


def test_signal_flows_to_executed(tmp_path):
    app, fake = _build_app(tmp_path, dry_run=False, live_execution_enabled=True)
    with TestClient(app) as client:
        response = client.post("/api/signals", json=_signal_payload("flow-executed-0001"))
        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] is True
        assert body["duplicate"] is False

        final = _wait_for_terminal(client, "flow-executed-0001")
        assert final["status"] == ExecutionStatus.EXECUTED.value
        assert len(fake.sent_requests) == 1


def test_duplicate_signal_executes_once(tmp_path):
    app, fake = _build_app(tmp_path, dry_run=False, live_execution_enabled=True)
    with TestClient(app) as client:
        payload = _signal_payload("flow-duplicate-0001")
        first = client.post("/api/signals", json=payload).json()
        second = client.post("/api/signals", json=payload).json()

        assert first["duplicate"] is False
        assert second["duplicate"] is True

        _wait_for_terminal(client, "flow-duplicate-0001")
        assert len(fake.sent_requests) == 1


def test_health_and_status_endpoints(tmp_path):
    app, _ = _build_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        status = client.get("/api/status").json()
        assert status["service"] == "MT5 Execution Bridge"
        assert status["dryRun"] is True
        assert "password" not in status


def test_account_endpoint_reports_balance_without_credentials(tmp_path):
    app, _fake = _build_app(tmp_path)
    with TestClient(app) as client:
        account = client.get("/api/account").json()
        assert account["balance"] == 10_000.0
        assert "server" not in account
        assert "login" not in account


def test_positions_endpoint_reports_open_positions(tmp_path):
    from types import SimpleNamespace

    app, fake = _build_app(tmp_path)
    fake.positions = [
        SimpleNamespace(ticket=1, symbol="EURUSD", type=0, volume=0.1, price_open=1.09,
                        price_current=1.091, sl=1.08, tp=1.10, profit=1.0, swap=0.0, magic=0, time=0)
    ]
    with TestClient(app) as client:
        positions = client.get("/api/positions").json()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "EURUSD"


def test_orders_endpoint_reports_pending_orders(tmp_path):
    from types import SimpleNamespace

    app, fake = _build_app(tmp_path)
    fake.orders = [
        SimpleNamespace(ticket=2, symbol="EURUSD", type=2, volume_current=0.2, price_open=1.05,
                        sl=1.04, tp=1.06, magic=0, time_setup=0)
    ]
    with TestClient(app) as client:
        orders = client.get("/api/orders").json()
        assert len(orders) == 1
        assert orders[0]["symbol"] == "EURUSD"


def test_account_endpoint_503s_when_mt5_is_unavailable(tmp_path):
    app, fake = _build_app(tmp_path)
    fake.connect_ok = False
    app.state.gateway._connected = False
    with TestClient(app) as client:
        response = client.get("/api/account")
        assert response.status_code == 503


def test_mapped_symbol_persisted_through_api(tmp_path):
    app, _ = _build_app(tmp_path)
    with TestClient(app) as client:
        client.post("/api/signals", json=_signal_payload("flow-symbol-normalized-0001"))
        final = _wait_for_terminal(client, "flow-symbol-normalized-0001")
        assert final["symbol_raw"] == "EURUSD"
        assert final["symbol_normalized"] == "EURUSD"


def test_processing_recovery_review_required_when_no_broker_evidence(tmp_path):
    """A signal stuck in PROCESSING at startup (e.g. after a crash) is never
    auto-resent; with no matching MT5 history it becomes REVIEW_REQUIRED."""
    app, _fake = _build_app(tmp_path, dry_run=False, live_execution_enabled=True)
    db = app.state.db
    db.insert_signal_if_new({
        "signal_id": "flow-recovery-unknown-0001",
        "timestamp": datetime.now(UTC).isoformat(),
        "symbol": "EURUSD",
        "action": "BUY",
        "risk_percent": 0.5,
        "stop_loss": 1.0850,
        "take_profit": 1.0950,
        "strategy": None,
        "comment": None,
    })
    db.claim_next_pending()  # -> PROCESSING, simulating a crash mid-execution

    with TestClient(app):
        # lifespan startup runs worker.recover_on_startup() synchronously
        signal = db.get_signal("flow-recovery-unknown-0001")
        assert signal["status"] == "REVIEW_REQUIRED"


def test_processing_recovery_recovered_executed_when_meb_comment_matches(tmp_path):
    from types import SimpleNamespace

    from app.services.execution_service import meb_comment

    app, fake = _build_app(tmp_path, dry_run=False, live_execution_enabled=True)
    db = app.state.db
    signal_id = "flow-recovery-matched-0001"
    db.insert_signal_if_new({
        "signal_id": signal_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "symbol": "EURUSD",
        "action": "BUY",
        "risk_percent": 0.5,
        "stop_loss": 1.0850,
        "take_profit": 1.0950,
        "strategy": None,
        "comment": None,
    })
    db.claim_next_pending()  # -> PROCESSING, simulating a crash mid-execution

    fake.deals = [SimpleNamespace(order=42, ticket=43, comment=meb_comment(signal_id))]

    with TestClient(app):
        # lifespan startup runs worker.recover_on_startup() synchronously
        signal = db.get_signal(signal_id)
        assert signal["status"] == "RECOVERED_EXECUTED"
