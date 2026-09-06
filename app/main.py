from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import health, signals, status
from app.config import Settings, get_settings
from app.services.execution_service import ExecutionService
from app.services.mt5_gateway import MT5Gateway
from app.services.signal_service import SignalService
from app.services.symbol_mapper import SymbolMapper
from app.storage.database import Database
from app.worker.execution_worker import ExecutionWorker

MAX_REQUEST_BODY_BYTES = 16 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("mt5_bridge")


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Signals are tiny; reject anything unexpectedly large before parsing it."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "request body too large"})
        return await call_next(request)


def _build_state(app: FastAPI, settings: Settings) -> None:
    db = Database(settings.database_path)
    gateway = MT5Gateway()
    symbol_mapper = SymbolMapper.from_file(settings.symbol_map_path)
    execution_service = ExecutionService(gateway, db, symbol_mapper, settings)
    worker = ExecutionWorker(db, execution_service)

    app.state.settings = settings
    app.state.db = db
    app.state.gateway = gateway
    app.state.symbol_mapper = symbol_mapper
    app.state.execution_service = execution_service
    app.state.signal_service = SignalService(db)
    app.state.worker = worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("STARTUP environment=%s dry_run=%s live_execution_enabled=%s host=%s port=%d",
                app.state.settings.environment, app.state.settings.dry_run,
                app.state.settings.live_execution_enabled, app.state.settings.host, app.state.settings.port)
    await app.state.worker.start()
    try:
        yield
    finally:
        await app.state.worker.stop()
        app.state.gateway.shutdown()
        app.state.db.close()
        logger.info("SHUTDOWN")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="MT5 Execution Bridge", version="0.1.0", lifespan=lifespan)
    _build_state(app, settings)

    app.add_middleware(BodySizeLimitMiddleware)

    app.include_router(health.router)
    app.include_router(status.router)
    app.include_router(signals.router)

    return app


app = create_app()
