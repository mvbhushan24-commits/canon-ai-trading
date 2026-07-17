"""Unit tests for bullish premium / discount analysis."""

from decimal import Decimal

pytest_plugins = ["tests.unit.engines.premium_discount_conftest"]

from backend.engines.market_premium_discount.bullish import BullishPremiumDiscountAnalyzer
from backend.engines.market_premium_discount.schemas import (
    FibDirection,
    PremiumDiscountQuality,
    PremiumDiscountZone,
)
from backend.engines.market_structure.schemas import TrendDirection
from tests.unit.engines.premium_discount_conftest import (
    build_valid_dealing_range,
    discount_order_blocks,
    premium_config,
)


def test_project_fibonacci_bullish_from_low_to_high() -> None:
    config = premium_config()
    analyzer = BullishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range(low=Decimal("2300"), high=Decimal("2350"))

    fibonacci = analyzer.project_fibonacci(dealing_range)

    assert fibonacci.direction is FibDirection.BULLISH
    assert fibonacci.equilibrium_level == Decimal("2325")
    assert fibonacci.levels[0].price == dealing_range.low
    assert fibonacci.levels[-1].price == dealing_range.high
    assert any(level.label == "equilibrium" for level in fibonacci.levels)


def test_fibonacci_ote_levels_bullish_projection() -> None:
    config = premium_config(ote_fib_low=0.62, ote_fib_high=0.79)
    analyzer = BullishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range(low=Decimal("2300"), high=Decimal("2350"))

    fibonacci = analyzer.project_fibonacci(dealing_range)

    assert fibonacci.ote_low_level == dealing_range.low + (dealing_range.range_size * Decimal("0.62"))
    assert fibonacci.ote_high_level == dealing_range.low + (dealing_range.range_size * Decimal("0.79"))
    assert fibonacci.ote_low_level < fibonacci.ote_high_level


def test_derive_ote_discount_territory() -> None:
    config = premium_config()
    analyzer = BullishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range()
    fibonacci = analyzer.project_fibonacci(dealing_range)
    from backend.engines.market_premium_discount.quality import QualityScorer

    scorer = QualityScorer(config)
    zone_entries = scorer.collect_zone_entries(
        order_blocks=discount_order_blocks(dealing_range),
        fair_value_gap_state=None,
        breaker_blocks=None,
        mitigation_blocks=None,
        liquidity_state=None,
        dealing_range=dealing_range,
    )

    ote = analyzer.derive_ote(dealing_range, fibonacci, zone_entries)

    assert ote is not None
    assert ote.territory is PremiumDiscountZone.DISCOUNT
    assert ote.direction is FibDirection.BULLISH
    assert ote.low < ote.high


def test_derive_ote_disabled() -> None:
    config = premium_config(ote_enabled=False)
    analyzer = BullishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range()
    fibonacci = analyzer.project_fibonacci(dealing_range)

    assert analyzer.derive_ote(dealing_range, fibonacci, []) is None


def test_derive_ote_requires_overlap_when_configured() -> None:
    config = premium_config(ote_require_zone_overlap=True, ote_min_overlapping_zones=1)
    analyzer = BullishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range()
    fibonacci = analyzer.project_fibonacci(dealing_range)

    assert analyzer.derive_ote(dealing_range, fibonacci, []) is None


def test_derive_ote_invalid_range() -> None:
    config = premium_config()
    analyzer = BullishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range().model_copy(update={"is_valid": False})
    fibonacci = analyzer.project_fibonacci(build_valid_dealing_range())

    assert analyzer.derive_ote(dealing_range, fibonacci, []) is None


def test_supports_trend_bullish_and_range() -> None:
    analyzer = BullishPremiumDiscountAnalyzer(premium_config())
    assert analyzer.supports_trend(TrendDirection.BULLISH) is True
    assert analyzer.supports_trend(TrendDirection.RANGE) is True
    assert analyzer.supports_trend(TrendDirection.BEARISH) is False


def test_ote_quality_tiers() -> None:
    config = premium_config()
    analyzer = BullishPremiumDiscountAnalyzer(config)
    dealing_range = build_valid_dealing_range()
    fibonacci = analyzer.project_fibonacci(dealing_range)
    from backend.engines.market_premium_discount.schemas import ArrayZoneEntry, InstitutionalZoneType

    overlapping_entries = [
        ArrayZoneEntry(
            zone_id=f"zone-{index}",
            zone_type=InstitutionalZoneType.ORDER_BLOCK,
            high=fibonacci.ote_high_level,
            low=fibonacci.ote_low_level,
            midpoint=(fibonacci.ote_high_level + fibonacci.ote_low_level) / Decimal("2"),
            strength=Decimal("0.8"),
        )
        for index in range(5)
    ]
    ote = analyzer.derive_ote(dealing_range, fibonacci, overlapping_entries)
    assert ote is not None
    assert ote.quality in {PremiumDiscountQuality.HIGH, PremiumDiscountQuality.MEDIUM, PremiumDiscountQuality.LOW}
