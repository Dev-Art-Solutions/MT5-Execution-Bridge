SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id TEXT NOT NULL UNIQUE,
        received_at TEXT NOT NULL,
        signal_timestamp TEXT NOT NULL,
        symbol_raw TEXT NOT NULL,
        symbol_normalized TEXT,
        action TEXT NOT NULL,
        risk_percent REAL NOT NULL,
        stop_loss REAL,
        take_profit REAL,
        strategy TEXT,
        comment TEXT,
        status TEXT NOT NULL,
        rejection_reason TEXT,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_attempt_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id TEXT NOT NULL,
        attempt INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        dry_run INTEGER NOT NULL,
        mt5_symbol TEXT,
        requested_action TEXT NOT NULL,
        calculated_volume REAL,
        entry_price REAL,
        stop_loss REAL,
        take_profit REAL,
        order_check_retcode INTEGER,
        order_send_retcode INTEGER,
        order_ticket INTEGER,
        deal_ticket INTEGER,
        result_message TEXT,
        status TEXT NOT NULL,
        FOREIGN KEY (signal_id) REFERENCES signals (signal_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_loss_baseline (
        trading_day TEXT PRIMARY KEY,
        baseline_equity REAL NOT NULL,
        recorded_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_signals_status ON signals (status)",
    "CREATE INDEX IF NOT EXISTS idx_executions_signal_id ON executions (signal_id)",
]
