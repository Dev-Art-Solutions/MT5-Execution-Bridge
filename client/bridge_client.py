from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8200"


class MT5ExecutionBridgeClient:
    """Minimal local client for the MT5 Execution Bridge HTTP API."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def health(self) -> dict[str, Any]:
        response = httpx.get(f"{self._base_url}/health", timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def status(self) -> dict[str, Any]:
        response = httpx.get(f"{self._base_url}/api/status", timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def send_signal(
        self,
        signal_id: str,
        symbol: str,
        action: str,
        risk_percent: float,
        stop_loss: float,
        take_profit: float | None = None,
        strategy: str | None = None,
        comment: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "signal_id": signal_id,
            "timestamp": timestamp or datetime.now(UTC).isoformat(),
            "symbol": symbol,
            "action": action,
            "risk_percent": risk_percent,
            "stop_loss": stop_loss,
        }
        if take_profit is not None:
            payload["take_profit"] = take_profit
        if strategy is not None:
            payload["strategy"] = strategy
        if comment is not None:
            payload["comment"] = comment

        response = httpx.post(f"{self._base_url}/api/signals", json=payload, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def get_signal(self, signal_id: str) -> dict[str, Any]:
        response = httpx.get(f"{self._base_url}/api/signals/{signal_id}", timeout=self._timeout)
        response.raise_for_status()
        return response.json()
