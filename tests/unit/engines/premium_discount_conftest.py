"""Shared helpers for premium / discount engine tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.engines.market_liquidity.schemas import LiquiditySide, LiquidityState, LiquidityZone
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockQuality,
    OrderBlockStatus,
)
from backend.engines.market_premium_discount.config import PremiumDiscountConfig
from backend.engines.market_premium_discount.publisher import PremiumDiscountEventPublisher
from backend.engines.market_premium_discount.schemas import (
    DealingRange,
    DealingRangeScope,
    PremiumDiscountContext,
    PremiumDiscountQuality,
    PremiumDiscountZone,
    SwingAnchor,
)
from backend.engines.market_structure.schemas import (
    MarketStructure,
    StructureState,
    SwingKind,
    SwingLabel,
    SwingPoint,
    TrendDirection,
)


def premium_config(**overrides) -> PremiumDiscountConfig:
    """Build a test PremiumDiscountConfig with sensible defaults."""
    defaults = {
        "enabled": True,
        "timeframes": ["M15", "H1", "H4"],
        "min_candles": 10,
        "lookback": 50,
        "pip_size": 0.1,
        "primary_range_mode": "external",
        "min_range_size_pips": 10.0,
        "max_range_age_bars": 200,
        "allow_same_bar_range": False,
        "invalidate_on_bos": True,
        "invalidate_on_choch": False,
        "swing_selection_mode": "latest_confirmed",
        "swing_lookback_bars": 100,
        "min_swing_quality_score": 0.3,
        "prefer_labeled_swings": True,
        "equilibrium_tolerance_pips": 3.0,
        "price_reference": "close",
        "array_cluster_pips": 8.0,
        "min_array_entries": 2,
        "max_arrays_per_territory": 5,
        "include_liquidity_zones": True,
        "compute_internal_bands": True,
        "mtf_alignment_min_score": 0.5,
        "nest_overlap_min_percent": 80.0,
        "nesting_enabled": True,
        "fibonacci_enabled": True,
        "fibonacci_direction_mode": "structure_trend",
        "ote_enabled": True,
        "ote_fib_low": 0.62,
        "ote_fib_high": 0.79,
        "ote_default_direction": "bullish",
        "ote_require_zone_overlap": False,
        "min_quality_score": 0.4,
    }
    defaults.update(overrides)
    return PremiumDiscountConfig(**defaults)


def build_premium_discount_candles(count: int = 30) -> list:
    """Build synthetic candles spanning a wide external dealing range."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    prices = [
        Decimal("2305"),
        Decimal("2310"),
        Decimal("2318"),
        Decimal("2325"),
        Decimal("2335"),
        Decimal("2342"),
        Decimal("2348"),
        Decimal("2350"),
        Decimal("2345"),
        Decimal("2338"),
        Decimal("2330"),
        Decimal("2320"),
        Decimal("2300"),
        Decimal("2308"),
        Decimal("2315"),
        Decimal("2325"),
        Decimal("2330"),
        Decimal("2338"),
        Decimal("2345"),
        Decimal("2348"),
        Decimal("2340"),
        Decimal("2332"),
        Decimal("2325"),
        Decimal("2318"),
        Decimal("2310"),
        Decimal("2305"),
        Decimal("2312"),
        Decimal("2320"),
        Decimal("2328"),
        Decimal("2335"),
    ]
    for index in range(count):
        base = prices[index % len(prices)]
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=base,
                high=base + Decimal("2"),
                low=base - Decimal("2"),
                close=base + Decimal("1"),
            )
        )
    return candles


def build_premium_discount_structure() -> MarketStructure:
    """Return structure with labeled external and internal swings."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    external_high = SwingPoint(
        price=Decimal("2350"),
        timestamp_utc=start + timedelta(hours=8),
        bar_index=8,
        kind=SwingKind.SWING_HIGH,
        label=SwingLabel.HH,
    )
    external_low = SwingPoint(
        price=Decimal("2300"),
        timestamp_utc=start + timedelta(hours=12),
        bar_index=12,
        kind=SwingKind.SWING_LOW,
        label=SwingLabel.LL,
    )
    internal_high = SwingPoint(
        price=Decimal("2335"),
        timestamp_utc=start + timedelta(hours=20),
        bar_index=20,
        kind=SwingKind.SWING_HIGH,
        label=SwingLabel.LH,
    )
    internal_low = SwingPoint(
        price=Decimal("2315"),
        timestamp_utc=start + timedelta(hours=18),
        bar_index=18,
        kind=SwingKind.SWING_LOW,
        label=SwingLabel.HL,
    )
    external_state = StructureState(
        trend=TrendDirection.BULLISH,
        last_swing_high=external_high,
        last_swing_low=external_low,
        bar_count=30,
    )
    internal_state = StructureState(
        trend=TrendDirection.BULLISH,
        last_swing_high=internal_high,
        last_swing_low=internal_low,
        bar_count=30,
    )
    return MarketStructure(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp_utc=start + timedelta(hours=30),
        current_trend=TrendDirection.BULLISH,
        swing_highs=[external_high, internal_high],
        swing_lows=[external_low, internal_low],
        internal_structure=internal_state,
        external_structure=external_state,
        current_structure_state=external_state,
        confidence=Decimal("0.75"),
    )


def build_valid_dealing_range(
    *,
    scope: DealingRangeScope = DealingRangeScope.EXTERNAL,
    high: Decimal = Decimal("2350"),
    low: Decimal = Decimal("2300"),
) -> DealingRange:
    """Return a synthetic valid dealing range."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    swing_high = SwingAnchor(
        price=high,
        timestamp_utc=start + timedelta(hours=8),
        bar_index=8,
        kind=SwingKind.SWING_HIGH,
        label=SwingLabel.HH,
        quality_score=Decimal("0.8"),
    )
    swing_low = SwingAnchor(
        price=low,
        timestamp_utc=start + timedelta(hours=12),
        bar_index=12,
        kind=SwingKind.SWING_LOW,
        label=SwingLabel.LL,
        quality_score=Decimal("0.8"),
    )
    equilibrium = (high + low) / Decimal("2")
    return DealingRange(
        range_id=f"dr-{scope.value}-test",
        scope=scope,
        high=high,
        low=low,
        equilibrium=equilibrium,
        range_size=high - low,
        swing_high=swing_high,
        swing_low=swing_low,
        formation_bar_index=12,
        formation_time_utc=start + timedelta(hours=12),
        is_valid=True,
        quality=PremiumDiscountQuality.HIGH,
        strength=Decimal("0.75"),
        evidence=["Synthetic dealing range for tests"],
    )


def premium_order_blocks(dealing_range: DealingRange | None = None) -> list[OrderBlock]:
    """Return order blocks clustered in premium territory."""
    dealing_range = dealing_range or build_valid_dealing_range()
    premium_low = dealing_range.equilibrium + Decimal("0.5")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        OrderBlock(
            block_id="ob-premium-1",
            direction=OrderBlockDirection.BEARISH,
            status=OrderBlockStatus.FRESH,
            high=premium_low + Decimal("5.5"),
            low=premium_low + Decimal("4.5"),
            origin_bar_index=10,
            origin_time_utc=start,
            displacement_bar_index=11,
            quality=OrderBlockQuality.HIGH,
            strength=Decimal("0.7"),
            structure_alignment=True,
            liquidity_confluence=False,
        ),
        OrderBlock(
            block_id="ob-premium-2",
            direction=OrderBlockDirection.BEARISH,
            status=OrderBlockStatus.FRESH,
            high=premium_low + Decimal("6.2"),
            low=premium_low + Decimal("5.2"),
            origin_bar_index=11,
            origin_time_utc=start + timedelta(hours=1),
            displacement_bar_index=12,
            quality=OrderBlockQuality.MEDIUM,
            strength=Decimal("0.65"),
            structure_alignment=True,
            liquidity_confluence=False,
        ),
    ]


def discount_order_blocks(dealing_range: DealingRange | None = None) -> list[OrderBlock]:
    """Return order blocks clustered in discount territory."""
    dealing_range = dealing_range or build_valid_dealing_range()
    discount_high = dealing_range.equilibrium - Decimal("0.5")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        OrderBlock(
            block_id="ob-discount-1",
            direction=OrderBlockDirection.BULLISH,
            status=OrderBlockStatus.FRESH,
            high=discount_high - Decimal("4.5"),
            low=discount_high - Decimal("5.5"),
            origin_bar_index=10,
            origin_time_utc=start,
            displacement_bar_index=11,
            quality=OrderBlockQuality.HIGH,
            strength=Decimal("0.72"),
            structure_alignment=True,
            liquidity_confluence=False,
        ),
        OrderBlock(
            block_id="ob-discount-2",
            direction=OrderBlockDirection.BULLISH,
            status=OrderBlockStatus.FRESH,
            high=discount_high - Decimal("5.2"),
            low=discount_high - Decimal("6.2"),
            origin_bar_index=11,
            origin_time_utc=start + timedelta(hours=1),
            displacement_bar_index=12,
            quality=OrderBlockQuality.MEDIUM,
            strength=Decimal("0.6"),
            structure_alignment=True,
            liquidity_confluence=False,
        ),
    ]


def nested_order_blocks(dealing_range: DealingRange | None = None) -> list[OrderBlock]:
    """Return parent/child order blocks for nesting tests."""
    parent = premium_order_blocks(dealing_range)[0]
    child = parent.model_copy(
        update={
            "block_id": "ob-nested-child",
            "high": parent.low + Decimal("1"),
            "low": parent.low + Decimal("0.2"),
        },
    )
    return [parent, child]


def sample_liquidity_state(dealing_range: DealingRange | None = None) -> LiquidityState:
    """Return liquidity zones near equilibrium."""
    dealing_range = dealing_range or build_valid_dealing_range()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return LiquidityState(
        active_zones=[
            LiquidityZone(
                zone_id="lq-discount-1",
                side=LiquiditySide.BUY_SIDE,
                upper_bound=dealing_range.equilibrium - Decimal("2"),
                lower_bound=dealing_range.equilibrium - Decimal("6"),
                anchor_price=dealing_range.equilibrium - Decimal("4"),
                cluster_size=3,
                timestamp_utc=start,
                is_active=True,
            ),
        ],
        recent_sweeps=[],
        bar_count=25,
    )


def sample_htf_premium_discount_context(
    dealing_range: DealingRange | None = None,
) -> PremiumDiscountContext:
    """Return HTF context aligned with discount territory."""
    dealing_range = dealing_range or build_valid_dealing_range(scope=DealingRangeScope.EXTERNAL)
    return PremiumDiscountContext(
        timeframe="H4",
        dealing_range=dealing_range,
        price_location=PremiumDiscountZone.DISCOUNT,
        premium_arrays=[],
        discount_arrays=[],
        equilibrium=dealing_range.equilibrium,
    )


@pytest.fixture
def premium_discount_config() -> PremiumDiscountConfig:
    return premium_config()


@pytest.fixture
def premium_discount_publisher() -> PremiumDiscountEventPublisher:
    return PremiumDiscountEventPublisher()


@pytest.fixture
def premium_discount_candles() -> list:
    return build_premium_discount_candles(30)


@pytest.fixture
def premium_discount_structure() -> MarketStructure:
    return build_premium_discount_structure()
