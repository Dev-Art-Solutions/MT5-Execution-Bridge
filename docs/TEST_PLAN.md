# Test Plan

## Automated tests

Run with `pytest`. MT5 is mocked via `tests/fixtures/fake_mt5.py` --
CI never requires a broker login and never sends a trade.

### Unit tests (`tests/unit/`)

- **Validation** -- BUY valid, SELL valid, invalid action, missing SL,
  stale signal, future signal, excessive risk.
- **Idempotency** -- first signal, duplicate, duplicate after DB reopen.
- **Symbol mapping** -- mapped, unknown.
- **Volume** -- BUY, SELL, round down, below minimum, calc failure.
- **Limits** -- spread, positions, daily trades, daily loss.
- **Execution** -- dry run, order_check reject, order_send reject,
  order_send success, ambiguous execution state.

### Integration tests (`tests/integration/`)

- `POST /api/signals` -> `PENDING` -> worker -> mocked MT5 -> `EXECUTED`.
- Duplicate `POST` of the same signal -> exactly one execution.
- `/health` and `/api/status` never leak credentials.

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
6. **Real demo order** -- only after 1-5 pass. Set `DRY_RUN=false` and
   `LIVE_EXECUTION_ENABLED=true`, submit one small valid signal, confirm
   `order_check` passed, `order_send` was called once, the retcode and
   ticket were persisted, and the position appears in the MT5 terminal.
   Do not repeat unnecessarily.

Report exact results (pass/fail, retcodes, screenshots) rather than
summarizing -- see the plan's Required Final Report format.
