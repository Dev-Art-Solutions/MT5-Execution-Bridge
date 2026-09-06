from __future__ import annotations

import pytest

from app.config import Settings
from app.services.execution_service import ExecutionService
from app.services.mt5_gateway import MT5Gateway
from app.services.symbol_mapper import SymbolMapper
from app.storage.database import Database
from tests.fixtures.fake_mt5 import FakeMT5


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(str(tmp_path / "bridge.db"))
    yield database
    database.close()


@pytest.fixture
def fake_mt5() -> FakeMT5:
    mt5 = FakeMT5()
    mt5.register_symbol("EURUSD")
    mt5.register_tick("EURUSD", bid=1.0900, ask=1.0901)
    return mt5


@pytest.fixture
def gateway(fake_mt5: FakeMT5) -> MT5Gateway:
    gw = MT5Gateway(mt5_module=fake_mt5)
    gw.initialize()
    return gw


@pytest.fixture
def symbol_mapper() -> SymbolMapper:
    return SymbolMapper({"EURUSD": "EURUSD"})


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_path=str(tmp_path / "bridge.db"),
        symbol_map_path=str(tmp_path / "unused-map.json"),
        dry_run=True,
        live_execution_enabled=False,
        max_risk_percent=1.0,
        max_spread_points=30,
        max_trades_per_day=5,
        max_open_positions=3,
        max_daily_loss_percent=3.0,
        max_signal_age_seconds=60,
        require_stop_loss=True,
    )


@pytest.fixture
def execution_service(gateway: MT5Gateway, db: Database, symbol_mapper: SymbolMapper, settings: Settings) -> ExecutionService:
    return ExecutionService(gateway, db, symbol_mapper, settings)
