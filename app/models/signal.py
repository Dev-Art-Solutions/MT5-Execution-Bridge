from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import SignalAction

_SAFE_SIGNAL_ID = re.compile(r"^[A-Za-z0-9._:\-]+$")


class SignalCreate(BaseModel):
    signal_id: str = Field(min_length=1, max_length=160)
    timestamp: datetime
    symbol: str = Field(min_length=1, max_length=50)
    action: str
    risk_percent: float = Field(gt=0)
    stop_loss: float | None = None
    take_profit: float | None = None
    strategy: str | None = None
    comment: str | None = None

    @field_validator("signal_id")
    @classmethod
    def _validate_signal_id(cls, value: str) -> str:
        if not _SAFE_SIGNAL_ID.match(value):
            raise ValueError("signal_id must contain only safe printable characters (A-Z a-z 0-9 . _ : -)")
        return value

    @field_validator("action")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in (SignalAction.BUY.value, SignalAction.SELL.value):
            raise ValueError("action must be BUY or SELL")
        return normalized


class SignalAcceptedResponse(BaseModel):
    accepted: bool
    duplicate: bool
    signal_id: str
    status: str


class SignalStatusResponse(BaseModel):
    signal_id: str
    status: str
    rejection_reason: str | None
    symbol_raw: str
    symbol_normalized: str | None
    action: str
    risk_percent: float
    stop_loss: float | None
    take_profit: float | None
    attempt_count: int
    received_at: str
    updated_at: str
