from app.storage.database import Database


def _sample_signal(signal_id: str = "dup-0001") -> dict:
    return {
        "signal_id": signal_id,
        "timestamp": "2026-09-06T03:15:00+00:00",
        "symbol": "EURUSD",
        "action": "BUY",
        "risk_percent": 0.5,
        "stop_loss": 1.0850,
        "take_profit": 1.0950,
        "strategy": "test",
        "comment": None,
    }


def test_first_signal_is_created(db: Database):
    row, created = db.insert_signal_if_new(_sample_signal())
    assert created
    assert row["status"] == "PENDING"


def test_duplicate_signal_is_recognized(db: Database):
    db.insert_signal_if_new(_sample_signal())
    row, created = db.insert_signal_if_new(_sample_signal())
    assert not created
    assert row["signal_id"] == "dup-0001"


def test_duplicate_survives_db_reopen(tmp_path):
    db_path = str(tmp_path / "reopen.db")
    db1 = Database(db_path)
    db1.insert_signal_if_new(_sample_signal())
    db1.close()

    db2 = Database(db_path)
    row, created = db2.insert_signal_if_new(_sample_signal())
    db2.close()

    assert not created
    assert row["signal_id"] == "dup-0001"
