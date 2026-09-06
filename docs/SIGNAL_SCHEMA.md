# Signal Schema

`POST /api/signals`

```json
{
  "signal_id": "strategy-EURUSD-2026-09-06T03:15:00Z",
  "timestamp": "2026-09-06T03:15:00Z",
  "symbol": "EURUSD",
  "action": "BUY",
  "risk_percent": 0.5,
  "stop_loss": 1.0850,
  "take_profit": 1.0950,
  "strategy": "EMA Cross",
  "comment": "optional"
}
```

## Fields

| Field | Required | Notes |
|---|---|---|
| `signal_id` | yes | Max 160 chars. Safe characters only: `A-Z a-z 0-9 . _ : -`. Idempotency key. |
| `timestamp` | yes | ISO-8601. UTC preferred. |
| `symbol` | yes | Max 50 chars. Caller-side symbol name -- mapped explicitly to a broker symbol. |
| `action` | yes | `BUY` or `SELL` (case-insensitive on input, normalized to upper-case). |
| `risk_percent` | yes | `> 0` and `<= MAX_RISK_PERCENT`. |
| `stop_loss` | yes* | Required unless `REQUIRE_STOP_LOSS=false`. |
| `take_profit` | no | |
| `strategy` | no | Free text, for audit only. |
| `comment` | no | Free text, for audit only -- not sent to the broker (the broker comment is a bridge-generated `MEB:<hash>` tag). |

## Response

```json
{
  "accepted": true,
  "duplicate": false,
  "signal_id": "strategy-EURUSD-2026-09-06T03:15:00Z",
  "status": "PENDING"
}
```

A duplicate `signal_id` returns `"duplicate": true` and the signal's existing
status; it is never re-queued or re-executed.

## Status lookup

`GET /api/signals/{signal_id}` returns the full audit view: current status,
rejection reason (if any), normalized symbol, and attempt count.

## Status values

See `app/models/enums.py::ExecutionStatus` for the authoritative list.
