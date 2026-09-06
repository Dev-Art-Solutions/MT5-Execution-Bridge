from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

TRADE_RETCODE_PLACED = 10008
TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_DONE_PARTIAL = 10010
TRADE_RETCODE_REJECT = 10006
TRADE_RETCODE_INVALID_STOPS = 10016


class FakeMT5:
    """In-memory stand-in for the MetaTrader5 SDK module, used across tests."""

    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    def __init__(self) -> None:
        self.connect_ok = True
        self.symbols: dict[str, SimpleNamespace] = {}
        self.ticks: dict[str, SimpleNamespace] = {}
        self.account_equity = 10_000.0
        self.account_server: str | None = "VSCapital-Demo"
        self.account_login: int | None = 12345
        self.positions: list[SimpleNamespace] = []
        self.positions_fail = False
        self.deals: list[SimpleNamespace] = []
        self.calc_profit_per_lot: float | None = -100.0  # loss for a 1-lot move to SL
        self.order_check_retcode = TRADE_RETCODE_DONE
        self.order_send_retcode = TRADE_RETCODE_DONE
        self.order_send_result: SimpleNamespace | None = None
        self.sent_requests: list[dict[str, Any]] = []
        self.checked_requests: list[dict[str, Any]] = []

    def register_symbol(self, symbol: str, *, point: float = 0.0001, volume_min: float = 0.01,
                         volume_max: float = 100.0, volume_step: float = 0.01,
                         filling_mode: int = 2, visible: bool = True) -> None:
        self.symbols[symbol] = SimpleNamespace(
            point=point, volume_min=volume_min, volume_max=volume_max,
            volume_step=volume_step, filling_mode=filling_mode, visible=visible,
        )

    def register_tick(self, symbol: str, bid: float, ask: float, tick_time: int | None = None) -> None:
        self.ticks[symbol] = SimpleNamespace(bid=bid, ask=ask, time=tick_time if tick_time is not None else int(time.time()))

    # -- SDK surface --------------------------------------------------------

    def initialize(self, path: str | None = None, **kwargs: Any) -> bool:
        return self.connect_ok

    def shutdown(self) -> None:
        pass

    def last_error(self) -> tuple[int, str]:
        return (0, "")

    def account_info(self) -> SimpleNamespace:
        return SimpleNamespace(equity=self.account_equity, server=self.account_server, login=self.account_login)

    def symbol_info(self, symbol: str) -> SimpleNamespace | None:
        return self.symbols.get(symbol)

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        info = self.symbols.get(symbol)
        if info is None:
            return False
        if enable:
            info.visible = True
        return True

    def symbol_info_tick(self, symbol: str) -> SimpleNamespace | None:
        return self.ticks.get(symbol)

    def positions_get(self, **kwargs: Any) -> list[SimpleNamespace] | None:
        if self.positions_fail:
            return None
        return list(self.positions)

    def history_deals_get(self, date_from: Any, date_to: Any, **kwargs: Any) -> list[SimpleNamespace]:
        return list(self.deals)

    def order_calc_profit(self, order_type: Any, symbol: str, volume: float,
                           price_open: float, price_close: float) -> float | None:
        if self.calc_profit_per_lot is None:
            return None
        return self.calc_profit_per_lot * volume

    def order_check(self, request: dict[str, Any]) -> SimpleNamespace:
        self.checked_requests.append(request)
        return SimpleNamespace(retcode=self.order_check_retcode, comment="check")

    def order_send(self, request: dict[str, Any]) -> SimpleNamespace | None:
        self.sent_requests.append(request)
        if self.order_send_result is not None:
            return self.order_send_result
        return SimpleNamespace(retcode=self.order_send_retcode, comment="send", order=555, deal=777)
