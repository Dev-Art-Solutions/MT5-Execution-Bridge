# Installation

## Requirements

- Windows, with MetaTrader 5 terminal installed and a broker account (demo recommended).
- Python 3.12+.
- The `MetaTrader5` Python package requires the terminal to be present on the
  same machine; there is no remote-connection mode.

## Setup

```powershell
git clone https://github.com/Dev-Art-Solutions/MT5-Execution-Bridge.git
cd MT5-Execution-Bridge
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Edit `.env`:

- Set `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` for your (ideally demo) account.
- Set `MT5_TERMINAL_PATH` if MT5 is not in its default install location.
- Leave `DRY_RUN=true` and `LIVE_EXECUTION_ENABLED=false` until you have
  completed the demo validation scenarios in `docs/TEST_PLAN.md`.

Edit `examples/symbol-map.example.json` (or point `SYMBOL_MAP_PATH` at your
own file) with the exact broker symbol names your account uses -- these vary
by broker (e.g. `EURUSD` vs `EURUSD.a`) and are never guessed automatically.

## Run

```powershell
.\scripts\run-dev.ps1
```

or directly:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8200
```

## Verify

```powershell
.\scripts\smoke-test.ps1
```

This calls `/health`, `/api/status`, and submits one dry-run signal from
`examples/buy-signal.json`.

## Auto-start

See `docs/SECURITY.md` and the **Windows Deployment** section of the README
for why Task Scheduler at user logon is the currently validated option, and
why a Windows Service is not assumed to work without testing on your
specific MT5/broker/session configuration.
