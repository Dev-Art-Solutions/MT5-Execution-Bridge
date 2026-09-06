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
    ExecutionStatus.DRY_RUN_APPROVED, ExecutionStatus.EXECUTED, ExecutionStatus.RECOVERED_EXECUTED,
    ExecutionStatus.REJECTED_STALE, ExecutionStatus.REJECTED_FUTURE_TIMESTAMP, ExecutionStatus.REJECTED_SYMBOL,
    ExecutionStatus.REJECTED_SYMBOL_UNAVAILABLE, ExecutionStatus.REJECTED_RISK, ExecutionStatus.REJECTED_STOP_LOSS,
    ExecutionStatus.REJECTED_SPREAD, ExecutionStatus.REJECTED_DAILY_LOSS, ExecutionStatus.REJECTED_DAILY_TRADE_LIMIT,
    ExecutionStatus.REJECTED_POSITION_LIMIT, ExecutionStatus.REJECTED_VOLUME,
    ExecutionStatus.REJECTED_VOLUME_BELOW_MINIMUM, ExecutionStatus.REJECTED_ORDER_CHECK,
    ExecutionStatus.FAILED_MT5_UNAVAILABLE, ExecutionStatus.FAILED_ORDER_SEND, ExecutionStatus.REVIEW_REQUIRED,
]}


def _build_app(tmp_path, *, dry_run: bool = True, live_execution_enabled: bool = False):
    symbol_map_path = tmp_path / "symbol-map.json"
    symbol_map_path.write_text('{"EURUSD": "EURUSD"}', encoding="utf-8")

    settings = Settings(
        database_path=str(tmp_path / "bridge.db"),
        symbol_map_path=str(symbol_map_path),
        dry_run=dry_run,
        live_execution_enabled=live_execution_enabled,
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
