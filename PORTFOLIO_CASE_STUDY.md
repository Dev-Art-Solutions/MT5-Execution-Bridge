# Portfolio Case Study: MT5 Execution Bridge

## Problem

A trading strategy, desktop tool, or local service that wants to act on
MetaTrader 5 has no safe, generic way to do so. Talking to the
`MetaTrader5` SDK directly means re-solving the same hard problems in every
project: what happens if the same signal arrives twice, what happens if
the process crashes right after the broker accepts an order, how much
should actually be risked per trade, and how do you stop a caller from
silently bypassing risk controls.

## Solution

A small, local-first FastAPI service that sits between signal sources and
the MT5 terminal. It validates, de-duplicates, and risk-checks every
signal through one deterministic pipeline before it is ever allowed near
`order_send()`, and persists a complete audit trail of every accepted and
rejected signal in SQLite.

## Architecture

```text
Local Strategy / App / Agent -> FastAPI (127.0.0.1:8200) -> SQLite (durable queue)
    -> Background Worker -> MT5Gateway -> MetaTrader 5 Terminal -> Broker
    -> SQLite Audit Record
```

See `docs/ARCHITECTURE.md` for the component breakdown.

## Engineering Challenges

### Duplicate signal delivery

A signal source can retry, double-fire, or replay. `signal_id` is a
`UNIQUE` SQLite column; a duplicate submission is recognized and returned
as such without a second execution, and this survives a process restart
because the database -- not an in-memory set -- is the source of truth.

### Crash after the broker accepted the order

The most dangerous failure mode: `order_send()` succeeds at the broker,
then the process dies before the result is persisted. On restart, a
signal left in `PROCESSING` is never blindly resent. Instead, every order
carries a unique `MEB:<hash>` comment derived from `signal_id`; recovery
searches recent MT5 history for that comment. A match becomes
`RECOVERED_EXECUTED`; no match becomes `REVIEW_REQUIRED`. No guessing.

### Broker symbol differences

Brokers rename symbols (`EURUSD` vs `EURUSD.a`, `XAUUSD` vs `GOLD`). The
bridge never guesses a suffix -- an unmapped symbol is rejected
(`REJECTED_SYMBOL`), and mapping is always explicit
(`examples/symbol-map.example.json`).

### Risk percent to position size

Callers describe risk as a percentage, not a lot size. Volume is derived
from account equity, `risk_percent`, and MT5's own contract math
(`order_calc_profit`), rounded down to the broker's `volume_step` --
never up, and never past `volume_max`. A calculation that cannot be
resolved rejects rather than falling back to a guessed-safe size.

### A signal cannot bypass risk

The pipeline order is fixed and enforced in code, not by caller
convention: freshness, symbol mapping, MT5 connection, market data, SL
validation, spread guard, trade/position limits, daily-loss guard,
risk-percent bound, volume calculation, `order_check()`, then
`order_send()`. There is no path from signal to broker order that skips a
step.

### Unknown is not the same as zero or safe

An MT5 API call can fail rather than return an empty/negative answer --
`positions_get()` returning `None` means "MT5 could not answer," not "zero
positions." Collapsing that into an empty list would let an infrastructure
failure silently look like a clean risk state and approve a trade it
shouldn't. The gateway preserves the distinction (`list | None`), and the
pipeline fails closed (`FAILED_MT5_STATE_UNKNOWN`) rather than treating
"unknown" as "safe." The same principle governs `order_send()`: a resting-
order retcode (`PLACED`) on what is always a market-order flow is
`REVIEW_REQUIRED`, not assumed to be either a fill or a clean miss.

### Broker day, not UTC day

MT5 reports its own server clock, which is not UTC and not the host
machine's local time -- and daily risk controls (loss baseline, trade
count) have to reset on the *broker's* midnight, not an arbitrary one. The
bridge derives the trading day from the last market tick's own timestamp,
and namespaces that daily state by broker server + account login so
switching MT5 accounts against the same local database can never inherit
another account's numbers. An undeterminable broker clock or account
identity fails the signal closed rather than guessing.

### Local deployment

MT5's Python integration expects an interactive session with the
terminal, not a headless server. The bridge assumes it runs on the same
Windows host as MT5, needs no reverse proxy or TLS termination, and its
auto-start story (Task Scheduler at logon vs. a Windows Service) was
chosen based on what was actually tested, not assumed -- see
`docs/INSTALLATION.md`.

## Safety Decisions

- Dry-run by default; live execution requires two independent flags to
  agree, not one.
- `order_check()` is always called and must pass before `order_send()` is
  ever reached.
- After `order_send()` is invoked, the bridge never retries blindly --
  an ambiguous outcome is reconciled, not guessed at.
- Every rejection persists a reason; every execution persists retcodes,
  tickets, and prices. Nothing is silently dropped.

## Failure Modes Considered

| Failure | Handling |
|---|---|
| Duplicate signal | Idempotent insert, `duplicate: true`, no re-execution |
| Stale/future signal | `REJECTED_STALE` / `REJECTED_FUTURE_TIMESTAMP` |
| Crash before `order_send()` | Signal stays `PENDING`/`PROCESSING`, retried on next worker pass |
| Crash after `order_send()` | `MEB:<hash>` reconciliation -> `RECOVERED_EXECUTED` or `REVIEW_REQUIRED` |
| MT5 unreachable | Bounded retry (max 3) before send; `FAILED_MT5_UNAVAILABLE` |
| Broker rejects the order | `order_check()` catches most cases (`REJECTED_ORDER_CHECK`); a live rejection is `FAILED_ORDER_SEND` |
| Partial fill (`TRADE_RETCODE_DONE_PARTIAL`) | `EXECUTED_PARTIAL`, real fill persisted, remainder never auto-sent |
| Unexpected `PLACED` retcode on a market order | `REVIEW_REQUIRED`, not assumed safe |
| MT5 position query fails | `FAILED_MT5_STATE_UNKNOWN`; never treated as zero open positions |
| Broker/server time undeterminable | `FAILED_BROKER_TIME_UNKNOWN`; never silently falls back to UTC |
| Unmapped/unavailable symbol | `REJECTED_SYMBOL` / `REJECTED_SYMBOL_UNAVAILABLE` |
| Excessive spread at execution time | `REJECTED_SPREAD` |
| Daily loss threshold breached | `REJECTED_DAILY_LOSS`; blocks new execution, does not liquidate |

## Client-Relevant Applications

The same pattern -- validate, de-duplicate, risk-gate, execute, audit --
generalizes beyond MT5 to any system where a client's software needs to
safely act on an external, stateful system it does not fully control:
payment execution, inventory reservation, infrastructure provisioning.
This project demonstrates the pattern end to end in a domain
(trading execution) where the cost of getting it wrong is immediate and
measurable.

## Result

A working local execution bridge: a JSON signal in, a risk-checked
decision and (in dry run or validated demo mode) an MT5 order out, with a
complete, queryable audit trail for every signal the service has ever
seen. See the README's **Demo Validation** section and `docs/TEST_PLAN.md`
for what was actually verified against a live MT5 terminal on this
machine, versus what remains to be exercised on a demo broker account.
