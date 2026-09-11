from datetime import UTC, datetime

from app.services.mt5_gateway import MT5Gateway
from tests.fixtures.fake_mt5 import FakeMT5


def test_positions_get_empty_result_is_not_none():
    mt5 = FakeMT5()
    gateway = MT5Gateway(mt5_module=mt5)
    positions = gateway.positions_get()
    assert positions == []
    assert positions is not None


def test_positions_get_failure_returns_none():
    mt5 = FakeMT5()
    mt5.positions_fail = True
    gateway = MT5Gateway(mt5_module=mt5)
    assert gateway.positions_get() is None


def test_connected_self_heals_when_the_terminal_drops_without_shutdown():
    """The terminal can vanish -- closed, network loss -- without ever
    calling back through the SDK. A cached True from initialize() must not
    keep reporting connected forever once account_info() actually fails."""
    mt5 = FakeMT5()
    gateway = MT5Gateway(mt5_module=mt5)
    assert gateway.initialize() is True
    assert gateway.connected is True

    mt5.account_info_fail = True
    assert gateway.connected is False

    # And it stays correctly false, rather than flapping back true from the
    # stale internal flag on a second read.
    assert gateway.connected is False


def test_connected_recovers_once_the_terminal_answers_again():
    mt5 = FakeMT5()
    gateway = MT5Gateway(mt5_module=mt5)
    gateway.initialize()
    mt5.account_info_fail = True
    assert gateway.connected is False

    mt5.account_info_fail = False
    gateway.initialize()
    assert gateway.connected is True


def test_server_time_derived_from_tick():
    mt5 = FakeMT5()
    known_time = datetime(2026, 9, 7, 3, 0, tzinfo=UTC)
    mt5.register_tick("EURUSD", bid=1.09, ask=1.0901, tick_time=int(known_time.timestamp()))
    gateway = MT5Gateway(mt5_module=mt5)

    server_time = gateway.server_time("EURUSD")

    assert server_time == known_time


def test_server_time_none_when_no_tick():
    mt5 = FakeMT5()
    gateway = MT5Gateway(mt5_module=mt5)
    assert gateway.server_time("UNKNOWN") is None


def test_server_time_none_on_malformed_tick_time():
    mt5 = FakeMT5()
    mt5.register_tick("EURUSD", bid=1.09, ask=1.0901)
    mt5.ticks["EURUSD"].time = "not-a-number"
    gateway = MT5Gateway(mt5_module=mt5)
    assert gateway.server_time("EURUSD") is None
