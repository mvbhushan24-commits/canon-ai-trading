"""Unit tests for bearish premium / discount analysis."""

from decimal import Decimal

pytest_plugins = ["tests.unit.engines.premium_discount_conftest"]

from backend.engines.market_premium_discount.bearish import BearishPremiumDiscountAnalyzer
from backend.engines.market_premium_discount.schemas import (
    FibDirection,
    PremiumDiscountZone,
)
from backend.engines.market_structure.schemas import TrendDirection
from tests.unit.engines.premium_discount_conftest import (
    build_valid_dealing_range,
    premium_config,
    premium_order_blocks,
)


def test_project_fibonacci_bearish_from_high_to_low() -> None:
    config = premium_config()
    analyzer = BearishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range(low=Decimal("2300"), high=Decimal("2350"))

    fibonacci = analyzer.project_fibonacci(dealing_range)

    assert fibonacci.direction is FibDirection.BEARISH
    assert fibonacci.equilibrium_level == Decimal("2325")
    assert fibonacci.levels[0].price == dealing_range.high
    assert fibonacci.levels[-1].price == dealing_range.low


def test_fibonacci_ote_levels_bearish_projection() -> None:
    config = premium_config(ote_fib_low=0.62, ote_fib_high=0.79)
    analyzer = BearishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range(low=Decimal("2300"), high=Decimal("2350"))

    fibonacci = analyzer.project_fibonacci(dealing_range)

    assert fibonacci.ote_high_level == dealing_range.high - (dealing_range.range_size * Decimal("0.62"))
    assert fibonacci.ote_low_level == dealing_range.high - (dealing_range.range_size * Decimal("0.79"))
    assert fibonacci.ote_low_level < fibonacci.ote_high_level


def test_derive_ote_premium_territory() -> None:
    config = premium_config()
    analyzer = BearishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range()
    fibonacci = analyzer.project_fibonacci(dealing_range)
    from backend.engines.market_premium_discount.quality import QualityScorer

    scorer = QualityScorer(config)
    zone_entries = scorer.collect_zone_entries(
        order_blocks=premium_order_blocks(dealing_range),
        fair_value_gap_state=None,
        breaker_blocks=None,
        mitigation_blocks=None,
        liquidity_state=None,
        dealing_range=dealing_range,
    )

    ote = analyzer.derive_ote(dealing_range, fibonacci, zone_entries)

    assert ote is not None
    assert ote.territory is PremiumDiscountZone.PREMIUM
    assert ote.direction is FibDirection.BEARISH


def test_derive_ote_disabled() -> None:
    config = premium_config(ote_enabled=False)
    analyzer = BearishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range()
    fibonacci = analyzer.project_fibonacci(dealing_range)

    assert analyzer.derive_ote(dealing_range, fibonacci, []) is None


def test_supports_trend_bearish_and_range() -> None:
    analyzer = BearishPremiumDiscountAnalyzer(premium_config())
    assert analyzer.supports_trend(TrendDirection.BEARISH) is True
    assert analyzer.supports_trend(TrendDirection.RANGE) is True
    assert analyzer.supports_trend(TrendDirection.BULLISH) is False


def test_fib_labels_bearish_orientation() -> None:
    analyzer = BearishPremiumDiscountAnalyzer(premium_config())
    assert analyzer._fib_label(Decimal("0")) == "range_high"
    assert analyzer._fib_label(Decimal("1")) == "range_low"
    assert analyzer._fib_label(Decimal("0.5")) == "equilibrium"
