# Changelog

All notable changes to this project are documented here.

## [Unreleased] - Hardening pass

### Fixed

- `MT5Gateway.positions_get()` now distinguishes a genuine MT5 query
  failure (`None`) from a successful empty result (`[]`); a failure fails
  the pipeline closed as `FAILED_MT5_STATE_UNKNOWN` instead of being
  silently treated as zero open positions.
- `order_send()` retcodes are modeled honestly instead of binary
  success/failure: `TRADE_RETCODE_DONE_PARTIAL` (10010) is
  `EXECUTED_PARTIAL` with the real fill persisted; an unexpected
  `TRADE_RETCODE_PLACED` (10008) for a market order is `REVIEW_REQUIRED`,
  not assumed safe.
- Daily-loss baseline, daily trade count, and the daily state key now use
  the MT5 server's own day (from the last market tick), not UTC/local
  time; an undeterminable broker time fails closed
  (`FAILED_BROKER_TIME_UNKNOWN`) instead of silently falling back to UTC.
- Daily state is now namespaced by broker server + MT5 login, so
  switching MT5 account/server while reusing the same SQLite database can
  no longer inherit another account's baseline or trade count.
- `signals.symbol_normalized` is now actually persisted (immediately after
  mapping succeeds, before any later step can fail) -- previously it was
  never written despite the column and API field existing.
- `MT5Gateway.ensure_symbol()` now selects a symbol that exists but is
  hidden from Market Watch (`visible=false`), not only a symbol missing
  entirely.
- `scripts/install-service.ps1` / `uninstall-service.ps1` renamed to
  `install-autostart.ps1` / `uninstall-autostart.ps1` -- they create a
  Windows Task Scheduler task, not a Windows Service.

### Added

- Strict settings validation (`app/config.py`): risk/loss percentages,
  position/trade/spread limits, magic number, signal-age, and port are all
  bounds-checked, and financial floats reject NaN/Infinity. Enabling live
  execution now requires `MT5_SERVER` and a numeric `MT5_LOGIN` (a
  password is not required -- an already-authenticated terminal session
  remains a supported way to run live).
- `SignalCreate.risk_percent` / `stop_loss` / `take_profit` reject
  non-finite and out-of-range values at the API boundary.
- `executions.account_key`, `executions.executed_volume`,
  `executions.executed_price` columns; `daily_loss_baseline` is now keyed
  by `(account_key, trading_day)` instead of `trading_day` alone.
- Regression tests for every issue above, plus reconciliation integration
  tests (`RECOVERED_EXECUTED` / `REVIEW_REQUIRED` on startup recovery) and
  broker-day / account-namespace / config-validation / symbol-visibility
  unit tests.

## [0.1.0] - Unreleased

### Added

- FastAPI service exposing `/health`, `/api/status`, `/api/signals`
  (POST + GET by id), bound to `127.0.0.1` by default.
- SQLite-backed durable queue, idempotency store, and audit trail.
- Deterministic risk pipeline: freshness, symbol mapping, MT5 connection,
  market data, SL validation, spread guard, daily trade/position limits,
  daily loss guard, risk-percent validation, risk-based volume calculation,
  `order_check()`, `order_send()`.
- Dry-run mode that exercises the full pipeline up to (not including)
  `order_send()`.
- Dual opt-in for live execution (`DRY_RUN=false` AND
  `LIVE_EXECUTION_ENABLED=true`).
- Ambiguous-execution protection: unique `MEB:<hash>` broker comment per
  signal, MT5 history reconciliation on restart, no blind retry after
  `order_send()`.
- `MT5Gateway` isolating all raw `MetaTrader5` SDK calls for testability.
- `client/bridge_client.py` local HTTP client and a runnable example.
- Unit and integration test suite against a mocked MT5 module; CI on
  Windows runners with no broker dependency.
