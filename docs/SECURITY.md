# Security

Localhost is the v1 security boundary. There is no OAuth/JWT layer -- the
API is not designed to be reachable off the host it runs on.

## Localhost-only API

`HOST` defaults to `127.0.0.1`. If `HOST` is set to any non-loopback
address, the application refuses to start unless `ALLOW_REMOTE_BINDING=true`
is also set, and logs a strong warning when it is. This is a config
validator (`app/config.py::Settings._enforce_local_binding`), not a
convention -- an accidental `HOST=0.0.0.0` cannot silently expose the
service.

## `.env` handling

`.env` is gitignored and must never be committed. `.env.example` documents
every variable with safe defaults. Copy it to `.env` locally; do not check
in real credentials, account IDs, or terminal paths.

## MT5 credential protection

`MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` are read from `.env` only.
`GET /api/status` never returns them, and `MT5Gateway` never logs them --
only `mt5.last_error()` diagnostics are logged on connection failure.

## No credentials inside the signal payload

The signal schema (`docs/SIGNAL_SCHEMA.md`) has no field for broker
credentials, account IDs, or terminal paths. A signal source only ever
describes a trade intent.

## Remote-binding warning

Covered above -- fails closed by default, opt-in and loud when overridden.

## Logging hygiene

Structured log events (`SIGNAL_RECEIVED`, `EXECUTION_STARTED`,
`ORDER_EXECUTED`, etc.) include the `signal_id` for correlation. Passwords
are never logged. Only retcodes, comments, and identifiers, are.

## Request body size limit

`BodySizeLimitMiddleware` rejects any request with `Content-Length` over
16 KB before it reaches the parser. Signals are small JSON documents; there
is no legitimate reason for a larger request body.
