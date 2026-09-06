# Architecture

## Overview

```text
Local Strategy / App / Agent
          |
          | HTTP JSON (127.0.0.1:8200)
          v
FastAPI
  - schema validation
  - freshness validation
  - symbol normalization
  - idempotency
  - durable persistence
          |
          v
SQLite  (PENDING signal)
          |
          v
Background Worker
  - MT5 connection
  - symbol validation
  - market data
  - risk validation
  - risk-based volume
  - order_check()
  - order_send()
          |
          v
MetaTrader 5 Terminal -> Broker
          |
          v
SQLite Audit Record
```

## Components

- `app/main.py` -- FastAPI app factory, request-size middleware, process lifecycle.
- `app/api/` -- `/health`, `/api/status`, `/api/signals` routers.
- `app/models/` -- request/response schemas and the execution status enum.
- `app/services/signal_service.py` -- idempotent signal intake.
- `app/services/risk_service.py` -- pure, unit-testable risk predicates (freshness, SL, spread, limits).
- `app/services/volume_calculator.py` -- risk-percent to lot-size conversion using MT5 contract math.
- `app/services/symbol_mapper.py` -- explicit signal-symbol to broker-symbol mapping.
- `app/services/mt5_gateway.py` -- the only module that calls the raw `MetaTrader5` SDK.
- `app/services/execution_service.py` -- orchestrates the deterministic risk pipeline end to end.
- `app/storage/database.py` -- SQLite durable queue, idempotency store, and audit trail.
- `app/worker/execution_worker.py` -- single-consumer background task draining `PENDING` signals.
- `client/bridge_client.py` -- thin local HTTP client for signal sources.

## Why SQLite as the queue

The bridge runs on the same Windows host as the MT5 terminal. A single-writer,
file-backed database is enough to be durable across restarts without adding
infrastructure (Redis, Postgres, message brokers) the deployment target does
not need. `signal_id` is UNIQUE, so duplicate delivery from the caller can
never produce a second broker order.

## Why a single worker task

`Database.claim_next_pending()` atomically moves one signal from `PENDING`
to `PROCESSING` inside a single SQLite transaction. Running exactly one
consumer removes the class of "two workers grab the same signal" bugs
entirely, at the cost of throughput this system does not need.

## The irreversible boundary

Everything before `order_send()` can be retried safely. Nothing after it
can be. That boundary is enforced structurally: `ExecutionService` never
calls `order_send()` twice for the same attempt, and a process restart
never resumes a signal left in `PROCESSING` -- it is reconciled against
MT5 history instead. See `SECURITY.md` and `VALIDATION.md` for detail.
