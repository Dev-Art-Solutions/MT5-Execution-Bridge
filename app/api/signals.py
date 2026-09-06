from fastapi import APIRouter, HTTPException, Request

from app.models.signal import SignalAcceptedResponse, SignalCreate, SignalStatusResponse

router = APIRouter()


@router.post("/api/signals", response_model=SignalAcceptedResponse)
async def submit_signal(signal: SignalCreate, request: Request) -> SignalAcceptedResponse:
    signal_service = request.app.state.signal_service
    row, duplicate = signal_service.submit(signal)
    return SignalAcceptedResponse(
        accepted=True,
        duplicate=duplicate,
        signal_id=row["signal_id"],
        status=row["status"],
    )


@router.get("/api/signals/{signal_id}", response_model=SignalStatusResponse)
async def get_signal(signal_id: str, request: Request) -> SignalStatusResponse:
    signal_service = request.app.state.signal_service
    row = signal_service.get(signal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="signal not found")
    return SignalStatusResponse(
        signal_id=row["signal_id"],
        status=row["status"],
        rejection_reason=row["rejection_reason"],
        symbol_raw=row["symbol_raw"],
        symbol_normalized=row["symbol_normalized"],
        action=row["action"],
        risk_percent=row["risk_percent"],
        stop_loss=row["stop_loss"],
        take_profit=row["take_profit"],
        attempt_count=row["attempt_count"],
        received_at=row["received_at"],
        updated_at=row["updated_at"],
    )
