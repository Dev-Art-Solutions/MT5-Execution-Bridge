# Changelog

All notable changes to this project are documented here.

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
