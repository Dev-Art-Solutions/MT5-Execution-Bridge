from app.services.volume_calculator import calculate_risk_based_volume


def test_volume_buy(gateway):
    result = calculate_risk_based_volume(
        gateway, "EURUSD", "BUY", entry_price=1.0901, stop_loss=1.0850,
        equity=10_000.0, risk_percent=1.0, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    assert result.ok
    assert result.volume == 1.0


def test_volume_sell(gateway):
    result = calculate_risk_based_volume(
        gateway, "EURUSD", "SELL", entry_price=1.0900, stop_loss=1.0950,
        equity=10_000.0, risk_percent=1.0, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    assert result.ok
    assert result.volume == 1.0


def test_volume_rounds_down_to_step(gateway):
    result = calculate_risk_based_volume(
        gateway, "EURUSD", "BUY", entry_price=1.0901, stop_loss=1.0850,
        equity=5_500.0, risk_percent=1.0, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    assert result.ok
    assert result.volume == 0.55


def test_volume_below_minimum_rejected(gateway):
    result = calculate_risk_based_volume(
        gateway, "EURUSD", "BUY", entry_price=1.0901, stop_loss=1.0850,
        equity=10.0, risk_percent=0.1, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    assert not result.ok
    assert result.reason == "REJECTED_VOLUME_BELOW_MINIMUM"


def test_volume_calc_failure_rejected(gateway, fake_mt5):
    fake_mt5.calc_profit_per_lot = None
    result = calculate_risk_based_volume(
        gateway, "EURUSD", "BUY", entry_price=1.0901, stop_loss=1.0850,
        equity=10_000.0, risk_percent=1.0, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    assert not result.ok
    assert result.reason == "order_calc_profit failed"
