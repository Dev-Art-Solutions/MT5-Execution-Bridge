from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import Settings
from app.models.enums import ExecutionStatus, SignalAction
from app.services import risk_service
from app.services.mt5_gateway import MT5Gateway
from app.services.symbol_mapper import SymbolMapper
from app.services.volume_calculator import (
    ORDER_TYPE_BUY,
    ORDER_TYPE_SELL,
    calculate_risk_based_volume,
)
from app.storage.database import Database

logger = logging.getLogger("mt5_bridge.execution_service")

MAX_MT5_CONNECT_ATTEMPTS = 3
RECONCILIATION_LOOKBACK = timedelta(days=3)

# order_send()/order_check() retcodes this bridge treats specially.
TRADE_RETCODE_PLACED = 10008
TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_DONE_PARTIAL = 10010


def meb_comment(signal_id: str) -> str:
    """Deterministic short comment tag used to find an order again after a crash."""
    digest = hashlib.sha256(signal_id.encode("utf-8")).hexdigest()[:10]
    return f"MEB:{digest}"


def account_key_for(account_info: Any) -> str | None:
    """Namespace key for daily risk state: broker/server identity + login.

    Returns None if the identity cannot be established reliably -- daily
    state must never be evaluated against an anonymous/shared baseline.
    """
    server = getattr(account_info, "server", None)
    login = getattr(account_info, "login", None)
    if not server or not str(server).strip() or not login:
        return None
    return f"{server}|{login}"


class ExecutionService:
    def __init__(self, gateway: MT5Gateway, db: Database, symbol_mapper: SymbolMapper, settings: Settings) -> None:
        self._gateway = gateway
        self._db = db
        self._symbol_mapper = symbol_mapper
        self._settings = settings

    # -- restart recovery ---------------------------------------------------

    def reconcile_stuck_signal(self, signal_row: Any) -> ExecutionStatus:
        """Called at startup for any signal left in PROCESSING by a prior crash.

        Never assumes success or failure. Searches MT5 history for the unique
        comment tag; only a positive match is treated as executed.
        """
        signal_id = signal_row["signal_id"]
        comment = meb_comment(signal_id)

        if not self._ensure_connected():
            logger.warning("RECONCILE_MT5_UNAVAILABLE signal_id=%s", signal_id)
            self._db.update_signal_status(signal_id, ExecutionStatus.REVIEW_REQUIRED.value,
                                           "MT5 unavailable during restart reconciliation")
            return ExecutionStatus.REVIEW_REQUIRED

        found = self._find_deal_by_comment(comment)
        if found is not None:
            self._db.update_signal_status(signal_id, ExecutionStatus.RECOVERED_EXECUTED.value)
            logger.info("RECOVERED_EXECUTED signal_id=%s ticket=%s", signal_id, found.get("order"))
            return ExecutionStatus.RECOVERED_EXECUTED

        self._db.update_signal_status(signal_id, ExecutionStatus.REVIEW_REQUIRED.value,
                                       "No matching MT5 history found for prior PROCESSING attempt")
        logger.warning("REVIEW_REQUIRED signal_id=%s reason=no_history_match", signal_id)
        return ExecutionStatus.REVIEW_REQUIRED

    def _find_deal_by_comment(self, comment: str) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        deals = self._gateway.history_deals_get(now - RECONCILIATION_LOOKBACK, now)
        for deal in deals:
            deal_comment = getattr(deal, "comment", "")
            if deal_comment == comment:
                return {"order": getattr(deal, "order", None), "deal": getattr(deal, "ticket", None)}
        return None

    # -- main pipeline --------------------------------------------------

    def process_signal(self, signal_row: Any) -> ExecutionStatus:
        signal_id = signal_row["signal_id"]
        attempt = signal_row["attempt_count"]
        started_at = datetime.now(UTC).isoformat()

        execution_fields: dict[str, Any] = {
            "signal_id": signal_id,
            "account_key": None,
            "attempt": attempt,
            "started_at": started_at,
            "finished_at": None,
            "dry_run": 1 if self._settings.dry_run else 0,
            "mt5_symbol": None,
            "requested_action": signal_row["action"],
            "calculated_volume": None,
            "entry_price": None,
            "stop_loss": signal_row["stop_loss"],
            "take_profit": signal_row["take_profit"],
            "order_check_retcode": None,
            "order_send_retcode": None,
            "order_ticket": None,
            "deal_ticket": None,
            "executed_volume": None,
            "executed_price": None,
            "result_message": None,
            "status": ExecutionStatus.PROCESSING.value,
        }
        execution_id = self._db.insert_execution(execution_fields)

        def finish(status: ExecutionStatus, message: str | None = None, **extra: Any) -> ExecutionStatus:
            fields = {"status": status.value, "finished_at": datetime.now(UTC).isoformat(), "result_message": message}
            fields.update(extra)
            self._db.update_execution(execution_id, fields)
            is_rejection = status.value.startswith(("REJECTED", "FAILED")) or status == ExecutionStatus.REVIEW_REQUIRED
            self._db.update_signal_status(signal_id, status.value, message if is_rejection else None)
            return status

        # 2. freshness
        freshness = risk_service.check_freshness(
            datetime.fromisoformat(signal_row["signal_timestamp"]), self._settings.max_signal_age_seconds
        )
        if not freshness.ok:
            return finish(freshness.status, freshness.reason)

        # 6. action validation
        action = signal_row["action"]
        if action == SignalAction.BUY.value and not self._settings.allow_market_buy:
            return finish(ExecutionStatus.REJECTED_RISK, "Market BUY disabled by configuration")
        if action == SignalAction.SELL.value and not self._settings.allow_market_sell:
            return finish(ExecutionStatus.REJECTED_RISK, "Market SELL disabled by configuration")

        # 3. symbol mapping
        mt5_symbol = self._symbol_mapper.resolve(signal_row["symbol_raw"])
        if mt5_symbol is None:
            return finish(ExecutionStatus.REJECTED_SYMBOL, f"No explicit symbol mapping for {signal_row['symbol_raw']}")
        execution_fields["mt5_symbol"] = mt5_symbol
        self._db.update_execution(execution_id, {"mt5_symbol": mt5_symbol})
        # Persist the resolved symbol now, before any later step can fail --
        # it is real audit information regardless of what happens next.
        self._db.set_symbol_normalized(signal_id, mt5_symbol)

        # 4. MT5 connection
        if not self._ensure_connected():
            return finish(ExecutionStatus.FAILED_MT5_UNAVAILABLE, "Unable to connect to MT5 terminal")

        # 4b. account identity (needed to namespace all daily risk state below)
        account = self._gateway.account_info()
        if account is None:
            return finish(ExecutionStatus.FAILED_MT5_UNAVAILABLE, "Unable to retrieve account info")
        account_key = account_key_for(account)
        if account_key is None:
            return finish(
                ExecutionStatus.FAILED_MT5_UNAVAILABLE,
                "Unable to reliably determine MT5 account identity (server/login) for daily state namespacing",
            )
        self._db.update_execution(execution_id, {"account_key": account_key})
        current_equity = account.equity

        # symbol availability
        symbol_info = self._gateway.ensure_symbol(mt5_symbol)
        if symbol_info is None:
            return finish(ExecutionStatus.REJECTED_SYMBOL_UNAVAILABLE, f"Symbol {mt5_symbol} unavailable in MT5")

        # 5. market data
        tick = self._gateway.symbol_info_tick(mt5_symbol)
        if tick is None:
            return finish(ExecutionStatus.FAILED_MT5_UNAVAILABLE, "Unable to retrieve market tick")
        bid, ask = tick.bid, tick.ask
        entry_price = ask if action == SignalAction.BUY.value else bid
        self._db.update_execution(execution_id, {"entry_price": entry_price})

        # Broker/server day, not UTC -- used for every daily-state key below.
        # Never falls back to UTC/local time for risk enforcement.
        broker_now = self._gateway.server_time(mt5_symbol)
        if broker_now is None:
            return finish(ExecutionStatus.FAILED_BROKER_TIME_UNKNOWN, "Unable to determine broker/server time from market tick")

        # 7. SL validation
        sl_check = risk_service.check_stop_loss(action, signal_row["stop_loss"], entry_price, self._settings.require_stop_loss)
        if not sl_check.ok:
            return finish(sl_check.status, sl_check.reason)

        # 8. spread validation
        point = getattr(symbol_info, "point", 0.0)
        spread_check = risk_service.check_spread(bid, ask, point, self._settings.max_spread_points)
        if not spread_check.ok:
            return finish(spread_check.status, spread_check.reason)

        # 9. trade-count validation (scoped to this broker/account, broker-day)
        day_start = risk_service.start_of_trading_day(broker_now).isoformat()
        trades_today = self._db.count_executed_trades_since(account_key, day_start)
        trade_limit_check = risk_service.check_daily_trade_limit(trades_today, self._settings.max_trades_per_day)
        if not trade_limit_check.ok:
            return finish(trade_limit_check.status, trade_limit_check.reason)

        # 10. position-count validation
        positions = self._gateway.positions_get()
        if positions is None:
            # MT5 failed to answer -- unknown must never be treated as zero.
            logger.warning("MT5_POSITION_QUERY_FAILED error=%s", self._gateway.last_error())
            return finish(ExecutionStatus.FAILED_MT5_STATE_UNKNOWN, "MT5 position query failed; cannot verify open-position count")
        open_positions = [p for p in positions if getattr(p, "magic", None) == self._settings.magic_number]
        position_check = risk_service.check_position_limit(len(open_positions), self._settings.max_open_positions)
        if not position_check.ok:
            return finish(position_check.status, position_check.reason)

        # 11. daily-loss validation (namespaced by account_key + broker day)
        trading_day = risk_service.trading_day_key(broker_now)
        baseline = self._db.get_daily_loss_baseline(account_key, trading_day)
        if baseline is None:
            self._db.set_daily_loss_baseline(account_key, trading_day, current_equity)
            baseline = current_equity
        loss_check = risk_service.check_daily_loss(current_equity, baseline, self._settings.max_daily_loss_percent)
        if not loss_check.ok:
            return finish(loss_check.status, loss_check.reason)

        # 12. risk-percent validation
        risk_check = risk_service.check_risk_percent(signal_row["risk_percent"], self._settings.max_risk_percent)
        if not risk_check.ok:
            return finish(risk_check.status, risk_check.reason)

        # 13 & 14. risk-based volume + broker volume constraints
        stop_loss = signal_row["stop_loss"]
        volume_result = calculate_risk_based_volume(
            gateway=self._gateway,
            symbol=mt5_symbol,
            action=action,
            entry_price=entry_price,
            stop_loss=stop_loss,
            equity=current_equity,
            risk_percent=signal_row["risk_percent"],
            volume_min=getattr(symbol_info, "volume_min", 0.01),
            volume_max=getattr(symbol_info, "volume_max", 100.0),
            volume_step=getattr(symbol_info, "volume_step", 0.01),
        )
        if not volume_result.ok:
            status = ExecutionStatus.REJECTED_VOLUME_BELOW_MINIMUM if volume_result.reason == "REJECTED_VOLUME_BELOW_MINIMUM" else ExecutionStatus.REJECTED_VOLUME
            return finish(status, volume_result.reason)
        self._db.update_execution(execution_id, {"calculated_volume": volume_result.volume})

        # 15. order_check()
        request = self._build_order_request(mt5_symbol, action, volume_result.volume, entry_price,
                                              signal_row["stop_loss"], signal_row["take_profit"], symbol_info, signal_id)
        check_result = self._gateway.order_check(request)
        check_retcode = getattr(check_result, "retcode", None)
        self._db.update_execution(execution_id, {"order_check_retcode": check_retcode})
        if check_result is None or not self._is_check_success(check_retcode):
            comment = getattr(check_result, "comment", "order_check returned no result")
            return finish(ExecutionStatus.REJECTED_ORDER_CHECK, f"retcode={check_retcode} comment={comment}")

        # dry run stops here
        if self._settings.dry_run or not self._settings.live_execution_allowed:
            return finish(ExecutionStatus.DRY_RUN_APPROVED, "Dry run: order_check passed, order_send skipped")

        # 16. order_send() -- irreversible boundary
        send_result = self._gateway.order_send(request)
        send_retcode = getattr(send_result, "retcode", None)
        self._db.update_execution(execution_id, {"order_send_retcode": send_retcode})

        if send_result is None:
            # Ambiguous: broker may or may not have received it. Do not blindly retry.
            return finish(ExecutionStatus.REVIEW_REQUIRED, "order_send returned no result; manual reconciliation required")

        comment = getattr(send_result, "comment", "")
        order_ticket = getattr(send_result, "order", None)
        deal_ticket = getattr(send_result, "deal", None)
        executed_volume = getattr(send_result, "volume", None)
        executed_price = getattr(send_result, "price", None)
        exposure_fields = {
            "order_ticket": order_ticket,
            "deal_ticket": deal_ticket,
            "executed_volume": executed_volume,
            "executed_price": executed_price,
        }

        if send_retcode == TRADE_RETCODE_DONE:
            return finish(ExecutionStatus.EXECUTED, comment or "order_send success", **exposure_fields)

        if send_retcode == TRADE_RETCODE_DONE_PARTIAL:
            # Real exposure exists at less than the requested volume. Record
            # it and stop -- never automatically send the remaining volume.
            return finish(ExecutionStatus.EXECUTED_PARTIAL, comment or "order_send partial fill", **exposure_fields)

        if send_retcode == TRADE_RETCODE_PLACED:
            # PLACED describes a resting/pending order. This bridge only ever
            # submits TRADE_ACTION_DEAL market orders, so seeing PLACED here
            # is unexpected -- treat it as ambiguous rather than assume it
            # means either a fill or a clean rejection.
            return finish(
                ExecutionStatus.REVIEW_REQUIRED,
                f"Unexpected PLACED retcode for a market order: comment={comment}",
                order_ticket=order_ticket,
                deal_ticket=deal_ticket,
            )

        return finish(ExecutionStatus.FAILED_ORDER_SEND, f"retcode={send_retcode} comment={comment}")

    # -- helpers ----------------------------------------------------------

    def _ensure_connected(self) -> bool:
        if self._gateway.connected:
            return True
        for attempt in range(1, MAX_MT5_CONNECT_ATTEMPTS + 1):
            ok = self._gateway.initialize(
                terminal_path=self._settings.mt5_terminal_path or None,
                login=int(self._settings.mt5_login) if self._settings.mt5_login else None,
                password=self._settings.mt5_password or None,
                server=self._settings.mt5_server or None,
            )
            if ok:
                return True
            logger.warning("MT5_CONNECT_ATTEMPT_FAILED attempt=%d/%d", attempt, MAX_MT5_CONNECT_ATTEMPTS)
        return False

    def _build_order_request(self, symbol: str, action: str, volume: float, price: float,
                              stop_loss: float | None, take_profit: float | None,
                              symbol_info: Any, signal_id: str) -> dict[str, Any]:
        mt5 = self._gateway.raw
        order_type = ORDER_TYPE_BUY if action == SignalAction.BUY.value else ORDER_TYPE_SELL
        trade_action_deal = mt5.TRADE_ACTION_DEAL if mt5 else 1
        type_time_gtc = mt5.ORDER_TIME_GTC if mt5 else 0
        filling = self._resolve_filling_mode(symbol_info)

        request: dict[str, Any] = {
            "action": trade_action_deal,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": self._settings.magic_number,
            "comment": meb_comment(signal_id),
            "type_time": type_time_gtc,
            "type_filling": filling,
        }
        if stop_loss is not None:
            request["sl"] = stop_loss
        if take_profit is not None:
            request["tp"] = take_profit
        return request

    def _resolve_filling_mode(self, symbol_info: Any) -> int:
        """Pick a filling mode the symbol actually supports rather than one hard-coded value."""
        mt5 = self._gateway.raw
        filling_mode = getattr(symbol_info, "filling_mode", None)
        if mt5 is None or filling_mode is None:
            return 1  # ORDER_FILLING_IOC fallback constant
        if filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        if filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    @staticmethod
    def _is_check_success(retcode: int | None) -> bool:
        # TRADE_RETCODE_DONE=10009 is what order_check returns for a request that would succeed.
        return retcode in (0, TRADE_RETCODE_DONE)
