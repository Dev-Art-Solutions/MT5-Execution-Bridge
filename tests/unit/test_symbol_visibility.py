from app.services.mt5_gateway import MT5Gateway
from tests.fixtures.fake_mt5 import FakeMT5


def test_visible_symbol_requires_no_selection():
    mt5 = FakeMT5()
    mt5.register_symbol("EURUSD", visible=True)
    gateway = MT5Gateway(mt5_module=mt5)

    info = gateway.ensure_symbol("EURUSD")

    assert info is not None
    assert info.visible is True


def test_invisible_symbol_is_selected_then_reused():
    mt5 = FakeMT5()
    mt5.register_symbol("EURUSD", visible=False)
    gateway = MT5Gateway(mt5_module=mt5)

    info = gateway.ensure_symbol("EURUSD")

    assert info is not None
    assert info.visible is True  # select() flips it in the fake, proving select was called


def test_missing_symbol_selected_successfully():
    mt5 = FakeMT5()
    gateway = MT5Gateway(mt5_module=mt5)
    # Symbol isn't registered at all until "discovered" by a successful select.
    mt5.symbols["XAUUSD"] = None  # placeholder so symbol_select can find it

    def fake_select(symbol, enable):
        if symbol == "XAUUSD" and enable:
            mt5.register_symbol("XAUUSD", visible=True)
            return True
        return False

    mt5.symbol_select = fake_select
    del mt5.symbols["XAUUSD"]

    info = gateway.ensure_symbol("XAUUSD")

    assert info is not None
    assert info.visible is True


def test_symbol_selection_failure_rejected():
    mt5 = FakeMT5()
    gateway = MT5Gateway(mt5_module=mt5)
    # Not registered at all, and select always fails for it.
    info = gateway.ensure_symbol("UNKNOWN")
    assert info is None
