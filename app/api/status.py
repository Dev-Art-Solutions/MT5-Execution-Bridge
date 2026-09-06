from fastapi import APIRouter, Request

from app.version import __version__

router = APIRouter()


@router.get("/api/status")
async def status(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    gateway = request.app.state.gateway
    worker = request.app.state.worker

    # Never expose password, account credentials, environment dump, or filesystem paths.
    return {
        "service": "MT5 Execution Bridge",
        "version": __version__,
        "environment": settings.environment,
        "dryRun": settings.dry_run,
        "liveExecutionEnabled": settings.live_execution_enabled,
        "mt5Connected": gateway.connected,
        "workerRunning": worker.running,
    }
