from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/api/account")
async def account(request: Request) -> dict[str, object]:
    snapshot = request.app.state.execution_service.account_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="MT5 is not connected")
    return snapshot


@router.get("/api/positions")
async def positions(request: Request) -> list[dict[str, object]]:
    snapshot = request.app.state.execution_service.positions_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="MT5 is not connected")
    return snapshot


@router.get("/api/orders")
async def orders(request: Request) -> list[dict[str, object]]:
    snapshot = request.app.state.execution_service.orders_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="MT5 is not connected")
    return snapshot
