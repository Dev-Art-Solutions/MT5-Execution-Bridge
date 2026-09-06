from types import SimpleNamespace

from app.services.execution_service import account_key_for
from app.storage.database import Database


def _insert_dummy_signal(db: Database, signal_id: str) -> None:
    db.insert_signal_if_new({
        "signal_id": signal_id,
        "timestamp": "2026-09-06T01:00:00+00:00",
        "symbol": "EURUSD",
        "action": "BUY",
        "risk_percent": 0.5,
        "stop_loss": 1.08,
        "take_profit": None,
        "strategy": None,
        "comment": None,
    })


def test_account_key_combines_server_and_login():
    account = SimpleNamespace(server="VSCapital-Demo", login=12345)
    assert account_key_for(account) == "VSCapital-Demo|12345"


def test_account_key_none_when_server_missing():
    assert account_key_for(SimpleNamespace(server="", login=12345)) is None
    assert account_key_for(SimpleNamespace(server=None, login=12345)) is None


def test_account_key_none_when_login_missing():
    assert account_key_for(SimpleNamespace(server="VSCapital-Demo", login=0)) is None
    assert account_key_for(SimpleNamespace(server="VSCapital-Demo", login=None)) is None


def test_same_day_different_accounts_have_independent_baselines(db: Database):
    db.set_daily_loss_baseline("ServerA|1", "2026-09-06", 10_000.0)
    db.set_daily_loss_baseline("ServerB|1", "2026-09-06", 5_000.0)

    assert db.get_daily_loss_baseline("ServerA|1", "2026-09-06") == 10_000.0
    assert db.get_daily_loss_baseline("ServerB|1", "2026-09-06") == 5_000.0


def test_same_login_different_server_independent_baselines(db: Database):
    db.set_daily_loss_baseline("ServerA|777", "2026-09-06", 1_000.0)
    db.set_daily_loss_baseline("ServerB|777", "2026-09-06", 2_000.0)

    assert db.get_daily_loss_baseline("ServerA|777", "2026-09-06") == 1_000.0
    assert db.get_daily_loss_baseline("ServerB|777", "2026-09-06") == 2_000.0


def test_baseline_survives_db_reopen(tmp_path):
    db_path = str(tmp_path / "namespace.db")
    db1 = Database(db_path)
    db1.set_daily_loss_baseline("ServerA|1", "2026-09-06", 10_000.0)
    db1.close()

    db2 = Database(db_path)
    baseline = db2.get_daily_loss_baseline("ServerA|1", "2026-09-06")
    db2.close()

    assert baseline == 10_000.0


def test_trade_count_scoped_by_account_key(db: Database):
    _insert_dummy_signal(db, "s1")
    _insert_dummy_signal(db, "s2")
    db.insert_execution({
        "signal_id": "s1", "account_key": "ServerA|1", "attempt": 1,
        "started_at": "2026-09-06T01:00:00+00:00", "finished_at": "2026-09-06T01:00:01+00:00",
        "dry_run": 0, "mt5_symbol": "EURUSD", "requested_action": "BUY",
        "calculated_volume": 0.1, "entry_price": 1.09, "stop_loss": 1.08, "take_profit": None,
        "order_check_retcode": 10009, "order_send_retcode": 10009, "order_ticket": 1, "deal_ticket": 1,
        "result_message": "ok", "status": "EXECUTED",
    })
    db.insert_execution({
        "signal_id": "s2", "account_key": "ServerB|1", "attempt": 1,
        "started_at": "2026-09-06T01:00:00+00:00", "finished_at": "2026-09-06T01:00:01+00:00",
        "dry_run": 0, "mt5_symbol": "EURUSD", "requested_action": "BUY",
        "calculated_volume": 0.1, "entry_price": 1.09, "stop_loss": 1.08, "take_profit": None,
        "order_check_retcode": 10009, "order_send_retcode": 10009, "order_ticket": 2, "deal_ticket": 2,
        "result_message": "ok", "status": "EXECUTED",
    })

    assert db.count_executed_trades_since("ServerA|1", "2026-09-06T00:00:00+00:00") == 1
    assert db.count_executed_trades_since("ServerB|1", "2026-09-06T00:00:00+00:00") == 1
    assert db.count_executed_trades_since("ServerC|1", "2026-09-06T00:00:00+00:00") == 0


def test_trade_count_includes_executed_partial(db: Database):
    _insert_dummy_signal(db, "s1")
    db.insert_execution({
        "signal_id": "s1", "account_key": "ServerA|1", "attempt": 1,
        "started_at": "2026-09-06T01:00:00+00:00", "finished_at": "2026-09-06T01:00:01+00:00",
        "dry_run": 0, "mt5_symbol": "EURUSD", "requested_action": "BUY",
        "calculated_volume": 0.1, "entry_price": 1.09, "stop_loss": 1.08, "take_profit": None,
        "order_check_retcode": 10009, "order_send_retcode": 10010, "order_ticket": 1, "deal_ticket": 1,
        "executed_volume": 0.05, "executed_price": 1.09,
        "result_message": "partial", "status": "EXECUTED_PARTIAL",
    })

    assert db.count_executed_trades_since("ServerA|1", "2026-09-06T00:00:00+00:00") == 1


def test_trade_count_excludes_dry_run_and_rejections(db: Database):
    _insert_dummy_signal(db, "s1")
    _insert_dummy_signal(db, "s2")
    db.insert_execution({
        "signal_id": "s1", "account_key": "ServerA|1", "attempt": 1,
        "started_at": "2026-09-06T01:00:00+00:00", "finished_at": "2026-09-06T01:00:01+00:00",
        "dry_run": 1, "mt5_symbol": "EURUSD", "requested_action": "BUY",
        "calculated_volume": 0.1, "entry_price": 1.09, "stop_loss": 1.08, "take_profit": None,
        "order_check_retcode": 10009, "order_send_retcode": None, "order_ticket": None, "deal_ticket": None,
        "result_message": "dry run", "status": "DRY_RUN_APPROVED",
    })
    db.insert_execution({
        "signal_id": "s2", "account_key": "ServerA|1", "attempt": 1,
        "started_at": "2026-09-06T01:00:00+00:00", "finished_at": "2026-09-06T01:00:01+00:00",
        "dry_run": 0, "mt5_symbol": "EURUSD", "requested_action": "BUY",
        "calculated_volume": None, "entry_price": 1.09, "stop_loss": 1.08, "take_profit": None,
        "order_check_retcode": None, "order_send_retcode": None, "order_ticket": None, "deal_ticket": None,
        "result_message": "rejected", "status": "REJECTED_SPREAD",
    })

    assert db.count_executed_trades_since("ServerA|1", "2026-09-06T00:00:00+00:00") == 0
