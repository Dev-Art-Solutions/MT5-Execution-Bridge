# Test Plan

## Automated tests

Run with `pytest`. MT5 is mocked via `tests/fixtures/fake_mt5.py` --
CI never requires a broker login and never sends a trade.

### Unit tests (`tests/unit/`)

- **Validation** -- BUY valid, SELL valid, invalid action, missing SL,
  stale signal, future signal, excessive risk.
- **Idempotency** -- first signal, duplicate, duplicate after DB reopen.
- **Symbol mapping** -- mapped, unknown.
- **Symbol visibility** -- visible (no selection needed), invisible
  (selected then reused), missing (selected successfully), selection
  failure (`REJECTED_SYMBOL_UNAVAILABLE`).
- **Volume** -- BUY, SELL, round down, below minimum, calc failure.
- **Limits** -- spread, positions, daily trades, daily loss.
- **MT5 gateway** -- `positions_get()` empty vs. `None` (query failure),
  `server_time()` derived from a tick, malformed/missing tick time.
- **Broker day** -- trading-day key and start-of-day use the given broker
  time, not UTC "now"; a full pipeline run proves the daily-state key
  reflects the tick's day even when it differs from wall-clock UTC;
  undeterminable broker time fails closed.
- **Account namespace** -- `account_key_for()` requires both server and
  login; same-day baselines are independent per account and per server;
  baseline survives a DB reopen; trade counting is scoped per account and
  includes `EXECUTED_PARTIAL` but excludes dry-run/rejected/failed.
- **Configuration validation** -- out-of-range settings rejected; NaN/
  Infinity rejected for risk/loss percentages and signal risk/SL/TP; live
  execution requires `MT5_SERVER` and a numeric `MT5_LOGIN`.
- **Execution** -- dry run, order_check reject, order_send reject/success,
  `EXECUTED_PARTIAL` (10010, not retried), unexpected `PLACED` (10008) ->
  `REVIEW_REQUIRED`, ambiguous execution state, position-query failure
  fails closed before `order_check`/`order_send`, `symbol_normalized`
  persisted even when a later step rejects the signal.

### Integration tests (`tests/integration/`)

- `POST /api/signals` -> `PENDING` -> worker -> mocked MT5 -> `EXECUTED`.
- Duplicate `POST` of the same signal -> exactly one execution.
- `/health` and `/api/status` never leak credentials.
- Mapped symbol is visible via `GET /api/signals/{id}` as
  `symbol_normalized`.
- Restart recovery: a signal stuck in `PROCESSING` becomes
  `REVIEW_REQUIRED` with no matching MT5 history, or `RECOVERED_EXECUTED`
  when a matching `MEB:<hash>` deal comment is found -- never resent.

## Manual demo validation (MT5 demo account only)

Never use real funds for these. Run each with the bridge live, and confirm
against `GET /api/signals/{id}` and `docs/images/`.

1. **Dry run** -- `DRY_RUN=true`, submit a valid signal, confirm
   `DRY_RUN_APPROVED` and that no order appears in the MT5 terminal.
2. **Duplicate** -- submit the same `signal_id` twice, confirm the second
   response has `"duplicate": true` and only one execution row exists.
3. **Invalid SL** -- BUY with `stop_loss` above the market, confirm
   `REJECTED_STOP_LOSS`.
4. **Excessive risk** -- `risk_percent` above `MAX_RISK_PERCENT`, confirm
   `REJECTED_RISK`.
5. **Spread guard** -- lower `MAX_SPREAD_POINTS` below the current spread,
   confirm `REJECTED_SPREAD`.
6. **Broker/account namespace** -- if practical, confirm via
   `docs/validation` evidence or direct inspection that the daily-loss
   baseline key includes the connected account's server + login, not just
   the calendar date.
7. **Real demo order** -- only after 1-6 pass. Set `DRY_RUN=false` and
   `LIVE_EXECUTION_ENABLED=true`, submit one small valid signal, confirm
   `order_check` passed, `order_send` was called once, the retcode and
   ticket were persisted, and the position appears in the MT5 terminal.
   Do not repeat unnecessarily.

Report exact results (pass/fail, retcodes, screenshots) rather than
summarizing -- see the plan's Required Final Report format.
