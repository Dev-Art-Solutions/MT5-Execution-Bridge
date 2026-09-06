from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness only. Does not require MT5 connectivity."""
    return {"status": "ok"}
