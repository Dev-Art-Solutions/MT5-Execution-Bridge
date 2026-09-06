# MT5 Execution Bridge

MT5 Execution Bridge is a local-first FastAPI service that receives
structured trading signals, persists and de-duplicates them, applies
deterministic risk checks, and routes approved market orders to
MetaTrader 5.

The signal source decides what it wants to do.
The bridge decides whether that request is valid and safe to execute.

This is the third project in the Dev Art Solutions trading portfolio:

```text
TradeAudit    = post-trade analytics, behavioral review, quantitative analysis
RiskGuard     = native MQL5 risk monitoring and safety controls
MT5 Execution Bridge = local signal ingestion, risk validation, MT5 execution
```

It does not implement a trading strategy, and makes no claims about
profitability.

## What it is

A localhost-only HTTP service, running on the same Windows machine as an
MT5 terminal, that turns a JSON trading signal into either a rejected
request with a reason, or a risk-checked market order -- with a durable,
queryable audit trail either way.

## Architecture

```text
Local Strategy / App / Agent
          |  HTTP JSON (127.0.0.1:8200)
          v
FastAPI -> validation, idempotency, persistence
          v
SQLite (PENDING signal)
          v
Background Worker -> MT5 connection, risk checks, volume calc,
                      order_check(), order_send()
          v
MetaTrader 5 Terminal -> Broker
          v
SQLite Audit Record
```

See `docs/ARCHITECTURE.md` for the full breakdown.

## Local-first model

No IIS, nginx, DNS, TLS, public firewall rules, or cloud infrastructure.
The API binds to `127.0.0.1` by default and refuses to start on a
non-loopback address unless `ALLOW_REMOTE_BINDING=true` is explicitly set.

## Signal lifecycle

```text
PENDING -> PROCESSING -> DRY_RUN_APPROVED | EXECUTED | REJECTED_* | REVIEW_REQUIRED
```

See `docs/SIGNAL_SCHEMA.md` and `app/models/enums.py` for the full status enum.

## Example request

```bash
curl -X POST http://127.0.0.1:8200/api/signals \
  -H "Content-Type: application/json" \
  -d @examples/buy-signal.json
```

```json
{
  "signal_id": "strategy-EURUSD-2026-09-06T03:15:00Z",
  "timestamp": "2026-09-06T03:15:00Z",
  "symbol": "EURUSD",
  "action": "BUY",
  "risk_percent": 0.5,
  "stop_loss": 1.0850,
  "take_profit": 1.0950,
  "strategy": "EMA Cross"
}
```

## Risk model

Every accepted signal runs through the same deterministic pipeline in a
fixed order: freshness, symbol mapping, MT5 connection, market data, action
enablement, stop-loss validation, spread guard, daily trade-count limit,
open-position limit, daily-loss guard, risk-percent bound, risk-based
volume calculation, `order_check()`, and only then `order_send()`. See
`docs/VALIDATION.md`.

## Dry run

`DRY_RUN=true` (the default) runs the entire pipeline -- including
`order_check()` -- and stops before `order_send()`, recording
`DRY_RUN_APPROVED` or a specific rejection status.

## Idempotency

`signal_id` is a `UNIQUE` column in SQLite. Submitting the same signal
twice returns `"duplicate": true` and never queues a second execution --
this survives process restarts, because the database (not an in-memory
set) is the source of truth.

## MT5 execution

`app/services/mt5_gateway.py` is the only module that calls the raw
`MetaTrader5` SDK. Order construction picks a filling mode the symbol
actually supports rather than a single hard-coded value, and every order
carries a bridge-generated `MEB:<hash>` comment used for post-crash
reconciliation (see **Safety Claims** below).

## Python client

```python
from client.bridge_client import MT5ExecutionBridgeClient

client = MT5ExecutionBridgeClient()
client.send_signal(
    signal_id="example-001",
    symbol="EURUSD",
    action="BUY",
    risk_percent=0.5,
    stop_loss=1.0850,
    take_profit=1.0950,
)
```

Runnable end to end: `python examples/python_client_example.py`.

## Installation

See `docs/INSTALLATION.md`.

## Configuration

See `.env.example` for every variable. Defaults are always the safe
option: dry-run, live execution disabled, localhost-only.

## Demo validation

See `docs/TEST_PLAN.md` for the manual demo scenarios (dry run, duplicate,
invalid SL, excessive risk, spread guard, one real demo order) that must
pass on an MT5 demo account before enabling live execution.

## Safety claims

- localhost-only by default
- dry-run by default
- dual live-execution opt-in (`DRY_RUN=false` **and**
  `LIVE_EXECUTION_ENABLED=true` -- one flag alone is not enough)
- stop-loss required by default
- risk-based position sizing (callers never specify lots)
- spread guard, daily-loss guard, trade-count guard, position-count guard
- stale-signal rejection
- durable, restart-safe duplicate protection
- no blind retry after `order_send()` -- an ambiguous outcome becomes
  `REVIEW_REQUIRED`, reconciled against MT5 history, never resent

## Limitations

- The MT5 terminal must be installed and reachable on the same machine.
- Broker symbol names vary and must be mapped explicitly.
- The broker may still reject an order that passed `order_check()`.
- Execution price can differ from the price seen at signal-validation time.
- The `MetaTrader5` Python integration depends on the local Windows/terminal
  environment; headless/service-mode reliability has not been assumed --
  see `docs/INSTALLATION.md` for what was actually validated.
- This project does not evaluate strategy profitability and makes no
  claims about trading results.
- Demo testing (`docs/TEST_PLAN.md`) is required before any live use.

## Dev Art Solutions

Part of a three-project trading infrastructure portfolio demonstrating
Python, FastAPI, SQLite, and MetaTrader 5 integration with a deterministic,
auditable risk gate between signal and execution.

## License

MIT -- see `LICENSE`.
