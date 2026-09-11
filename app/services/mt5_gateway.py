from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
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
    def orders_get(self, **kwargs: Any) -> Any: ...
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
        """Whether the terminal is actually still there, not just whether
        initialize() once said so.

        The MT5 terminal can drop the connection -- closed, network loss,
        crashed -- without ever calling back through this SDK, so a boolean
        set once by initialize()/shutdown() goes stale the moment that
        happens: every caller that trusts it (including this class's own
        _ensure_connected()-style callers, and /api/status) keeps reporting
        "connected" while every real call fails. account_info() is the
        cheapest real liveness probe the SDK offers, so a cached True is
        re-validated against it rather than returned on faith.
        """
        if not self._connected or self._mt5 is None:
            return False
        if self._mt5.account_info() is None:
            self._connected = False
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
            logger.warning("MT5_INITIALIZE_FAILED error=%s", self.last_error())
        return self._connected

    def shutdown(self) -> None:
        if self._mt5 is not None and self._connected:
            self._mt5.shutdown()
        self._connected = False

    def last_error(self) -> Any:
        """Safe (credential-free) diagnostic info: MT5's (code, description) tuple."""
        try:
            return self._mt5.last_error() if self._mt5 else None
        except Exception:  # noqa: BLE001 -- native SDK call, exception type is not documented
            return None

    def account_info(self) -> Any:
        return self._mt5.account_info() if self._mt5 else None

    def symbol_info(self, symbol: str) -> Any:
        return self._mt5.symbol_info(symbol) if self._mt5 else None

    def ensure_symbol(self, symbol: str) -> Any:
        """Return symbol_info, selecting it in Market Watch if missing OR not visible.

        symbol_info() existing is not the same as the symbol being usable --
        a symbol can exist but be hidden from Market Watch (visible=False),
        which still requires an explicit symbol_select() before quotes/trading work.
        """
        if self._mt5 is None:
            return None
        info = self._mt5.symbol_info(symbol)
        if info is not None and getattr(info, "visible", True):
            return info
        if not self._mt5.symbol_select(symbol, True):
            return None
        return self._mt5.symbol_info(symbol)

    def symbol_info_tick(self, symbol: str) -> Any:
        return self._mt5.symbol_info_tick(symbol) if self._mt5 else None

    def server_time(self, reference_symbol: str) -> datetime | None:
        """Broker/server time, derived from the reference symbol's last tick.

        MT5 tick timestamps reflect the broker server's own clock, not
        necessarily UTC -- callers must never substitute local/UTC time for
        this when computing a trading-day identity (daily-loss baseline,
        daily trade count, daily state key).
        """
        tick = self.symbol_info_tick(reference_symbol)
        if tick is None:
            return None
        try:
            return datetime.fromtimestamp(tick.time, tz=UTC)
        except (OSError, OverflowError, ValueError, AttributeError, TypeError):
            return None

    def positions_get(self, **kwargs: Any) -> list[Any] | None:
        """Return open positions, or None if MT5 failed to answer.

        MT5's positions_get() returns None on a genuine query failure and an
        (possibly empty) tuple on success. Collapsing None into [] would let
        an infrastructure failure look identical to "zero open positions" --
        unknown must never equal zero for a risk control.
        """
        if self._mt5 is None:
            return None
        result = self._mt5.positions_get(**kwargs)
        if result is None:
            return None
        return list(result)

    def orders_get(self, **kwargs: Any) -> list[Any] | None:
        """Pending (resting) orders -- distinct from positions_get()'s open
        fills. Same None-means-unknown contract as positions_get()."""
        if self._mt5 is None:
            return None
        result = self._mt5.orders_get(**kwargs)
        if result is None:
            return None
        return list(result)

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
