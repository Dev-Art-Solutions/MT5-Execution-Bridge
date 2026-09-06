from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger("mt5_bridge.mt5_gateway")

try:
    import MetaTrader5 as _mt5_module  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised only off-Windows / no terminal
    _mt5_module = None


class MT5Module(Protocol):
    """The subset of the MetaTrader5 package surface the bridge depends on."""

    def initialize(self, path: str | None = None, **kwargs: Any) -> bool: ...
    def shutdown(self) -> None: ...
    def last_error(self) -> Any: ...
    def account_info(self) -> Any: ...
    def symbol_info(self, symbol: str) -> Any: ...
    def symbol_select(self, symbol: str, enable: bool) -> bool: ...
    def symbol_info_tick(self, symbol: str) -> Any: ...
    def positions_get(self, **kwargs: Any) -> Any: ...
    def history_deals_get(self, *args: Any, **kwargs: Any) -> Any: ...
    def order_calc_profit(self, action: Any, symbol: str, volume: float, price_open: float, price_close: float) -> float | None: ...
    def order_check(self, request: dict[str, Any]) -> Any: ...
    def order_send(self, request: dict[str, Any]) -> Any: ...


@dataclass
class MT5ConnectionError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


class MT5Gateway:
    """Thin, testable wrapper around the raw MetaTrader5 SDK calls.

    Keeping raw SDK calls isolated here means the risk pipeline and worker
    can be unit-tested against a fake module instead of a live terminal.
    """

    def __init__(self, mt5_module: MT5Module | None = None) -> None:
        self._mt5 = mt5_module if mt5_module is not None else _mt5_module
        self._connected = False

    @property
    def available(self) -> bool:
        return self._mt5 is not None

    @property
    def connected(self) -> bool:
        return self._connected

    def initialize(self, terminal_path: str | None = None, login: int | None = None,
                    password: str | None = None, server: str | None = None) -> bool:
        if self._mt5 is None:
            return False
        kwargs: dict[str, Any] = {}
        if login:
            kwargs["login"] = login
        if password:
            kwargs["password"] = password
        if server:
            kwargs["server"] = server
        ok = self._mt5.initialize(terminal_path, **kwargs) if terminal_path else self._mt5.initialize(**kwargs)
        self._connected = bool(ok)
        if not ok:
            logger.warning("MT5_INITIALIZE_FAILED error=%s", self._safe_last_error())
        return self._connected

    def shutdown(self) -> None:
        if self._mt5 is not None and self._connected:
            self._mt5.shutdown()
        self._connected = False

    def _safe_last_error(self) -> Any:
        try:
            return self._mt5.last_error() if self._mt5 else None
        except Exception:  # noqa: BLE001 -- native SDK call, exception type is not documented
            return None

    def account_info(self) -> Any:
        return self._mt5.account_info() if self._mt5 else None

    def symbol_info(self, symbol: str) -> Any:
        return self._mt5.symbol_info(symbol) if self._mt5 else None

    def ensure_symbol(self, symbol: str) -> Any:
        """Return symbol_info, selecting it in Market Watch if not already visible."""
        if self._mt5 is None:
            return None
        info = self._mt5.symbol_info(symbol)
        if info is not None:
            return info
        if self._mt5.symbol_select(symbol, True):
            return self._mt5.symbol_info(symbol)
        return None

    def symbol_info_tick(self, symbol: str) -> Any:
        return self._mt5.symbol_info_tick(symbol) if self._mt5 else None

    def positions_get(self, **kwargs: Any) -> list[Any]:
        if self._mt5 is None:
            return []
        result = self._mt5.positions_get(**kwargs)
        return list(result) if result is not None else []

    def history_deals_get(self, date_from: Any, date_to: Any, **kwargs: Any) -> list[Any]:
        if self._mt5 is None:
            return []
        result = self._mt5.history_deals_get(date_from, date_to, **kwargs)
        return list(result) if result is not None else []

    def order_calc_profit(self, order_type: Any, symbol: str, volume: float,
                           price_open: float, price_close: float) -> float | None:
        if self._mt5 is None:
            return None
        return self._mt5.order_calc_profit(order_type, symbol, volume, price_open, price_close)

    def order_check(self, request: dict[str, Any]) -> Any:
        return self._mt5.order_check(request) if self._mt5 else None

    def order_send(self, request: dict[str, Any]) -> Any:
        return self._mt5.order_send(request) if self._mt5 else None

    @property
    def raw(self) -> MT5Module | None:
        """Access to constants (mt5.ORDER_TYPE_BUY, mt5.TRADE_ACTION_DEAL, ...)."""
        return self._mt5
