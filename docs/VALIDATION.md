# Validation Rules

## `signal_id`

- required, max 160 chars
- safe characters only: `A-Z a-z 0-9 . _ : -`
- unique -- the idempotency key

## `timestamp`

- ISO-8601, UTC preferred, required

## `symbol`

- required, max 50 chars
- resolved through an explicit symbol map; unmapped symbols are rejected
  (`REJECTED_SYMBOL`), never guessed
- the resolved broker symbol is persisted to `signals.symbol_normalized`
  immediately after mapping succeeds -- before any later validation step
  can fail -- so it is always visible via `GET /api/signals/{id}` even for
  a rejected signal
- a symbol that exists in MT5 but is hidden from Market Watch
  (`visible=false`) is explicitly selected and re-queried, the same as a
  symbol missing entirely; only a symbol still unusable after that becomes
  `REJECTED_SYMBOL_UNAVAILABLE`

## `action`

- `BUY` / `SELL` / `buy` / `sell` accepted on input, normalized to upper-case
- disabled independently via `ALLOW_MARKET_BUY` / `ALLOW_MARKET_SELL`

## `risk_percent`

- `> 0` and `<= MAX_RISK_PERCENT`

## `stop_loss`

- required when `REQUIRE_STOP_LOSS=true` (default)
- BUY: must be below the expected entry price
- SELL: must be above the expected entry price
- never invented or moved automatically

## Freshness

- default `MAX_SIGNAL_AGE_SECONDS=60`
- signals older than the limit: `REJECTED_STALE`
- signals more than 5 seconds in the future: `REJECTED_FUTURE_TIMESTAMP`

## Spread guard

- `spread_points = (ask - bid) / point`
- rejected above `MAX_SPREAD_POINTS`, or on invalid quote data: `REJECTED_SPREAD`

## Daily trade / position limits

- counts bridge-originated activity only (by `MAGIC_NUMBER` / bridge comment tag)
- `REJECTED_DAILY_TRADE_LIMIT`, `REJECTED_POSITION_LIMIT`
- an MT5 position-query failure (not "zero positions", an actual query
  failure) is `FAILED_MT5_STATE_UNKNOWN` -- the pipeline never continues
  as if zero positions were open when MT5 could not confirm that

## Daily loss guard

- lightweight, bridge-side only -- not a replacement for RiskGuard
- the trading day is the **MT5 server's own day** (derived from the last
  market tick's timestamp), not UTC and not the host machine's local
  clock -- if it cannot be determined, the signal fails closed
  (`FAILED_BROKER_TIME_UNKNOWN`) rather than guessing
- baseline equity, daily trade count, and the daily state key are all
  namespaced by `broker server + MT5 login`, so switching accounts while
  reusing the same SQLite database can never inherit another account's
  daily numbers
- `REJECTED_DAILY_LOSS` blocks new execution only, it does not close positions

## Risk-based volume

- callers never specify lots directly
- volume is derived from `equity * risk_percent / 100`, MT5 contract math
  (`order_calc_profit`), and rounded **down** to `volume_step`
- below `volume_min`: `REJECTED_VOLUME_BELOW_MINIMUM`
- unresolvable calculation: `REJECTED_VOLUME` (unknown risk is never treated
  as safe)

## Order checks

- `order_check()` is always called before any live send
- broker-side rejection: `REJECTED_ORDER_CHECK`, `order_send()` is never called

## `order_send()` result

- `TRADE_RETCODE_DONE` (10009) -> `EXECUTED`
- `TRADE_RETCODE_DONE_PARTIAL` (10010) -> `EXECUTED_PARTIAL`, with whatever
  fill price/volume the broker reported persisted; the remaining requested
  volume is never automatically sent
- an unexpected `TRADE_RETCODE_PLACED` (10008) -- this bridge only ever
  submits market orders, so a resting/pending-order retcode here is not
  a flow it can trust -- is `REVIEW_REQUIRED`, not assumed safe
- any other rejection retcode: `FAILED_ORDER_SEND`
- no result at all from `order_send()`: `REVIEW_REQUIRED`
- none of `EXECUTED_PARTIAL` / `REVIEW_REQUIRED` / `FAILED_ORDER_SEND` are
  ever automatically retried or resent
