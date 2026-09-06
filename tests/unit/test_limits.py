from app.services import risk_service


def test_spread_within_limit_accepted():
    result = risk_service.check_spread(bid=1.0900, ask=1.0902, point=0.0001, max_spread_points=30)
    assert result.ok


def test_spread_exceeding_limit_rejected():
    result = risk_service.check_spread(bid=1.0900, ask=1.0940, point=0.0001, max_spread_points=30)
    assert not result.ok


def test_spread_invalid_quote_rejected():
    result = risk_service.check_spread(bid=0, ask=0, point=0.0001, max_spread_points=30)
    assert not result.ok


def test_daily_trade_limit_not_reached():
    result = risk_service.check_daily_trade_limit(trades_today=3, max_trades_per_day=5)
    assert result.ok


def test_daily_trade_limit_reached_rejected():
    result = risk_service.check_daily_trade_limit(trades_today=5, max_trades_per_day=5)
    assert not result.ok


def test_position_limit_not_reached():
    result = risk_service.check_position_limit(open_positions=2, max_open_positions=3)
    assert result.ok


def test_position_limit_reached_rejected():
    result = risk_service.check_position_limit(open_positions=3, max_open_positions=3)
    assert not result.ok


def test_daily_loss_within_bounds_accepted():
    result = risk_service.check_daily_loss(current_equity=9_900.0, baseline_equity=10_000.0, max_daily_loss_percent=3.0)
    assert result.ok


def test_daily_loss_exceeded_rejected():
    result = risk_service.check_daily_loss(current_equity=9_600.0, baseline_equity=10_000.0, max_daily_loss_percent=3.0)
    assert not result.ok
