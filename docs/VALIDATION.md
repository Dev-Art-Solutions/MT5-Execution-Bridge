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

## Daily loss guard

- lightweight, bridge-side only -- not a replacement for RiskGuard
- baseline equity persisted per broker-day; `REJECTED_DAILY_LOSS` blocks new
  execution only, it does not close positions

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
