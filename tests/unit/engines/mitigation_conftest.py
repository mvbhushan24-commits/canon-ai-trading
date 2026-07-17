"""Shared helpers for mitigation block engine tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.engines.market_mitigation.config import MitigationBlockConfig
from backend.engines.market_mitigation.publisher import MitigationBlockEventPublisher
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockDirection,
    MitigationBlockQuality,
    MitigationBlockStatus,
)
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockQuality,
    OrderBlockStatus,
)


def mitigation_config(**overrides) -> MitigationBlockConfig:
    """Build a test MitigationBlockConfig with sensible defaults."""
    defaults = {
        "enabled": True,
        "timeframes": ["M15", "H1", "H4"],
        "min_candles": 10,
        "lookback": 50,
        "pip_size": 0.1,
        "min_displacement_pips": 5.0,
        "min_zone_size_pips": 1.5,
        "zone_bound_mode": "body",
        "require_bos_displacement": False,
        "deduplicate_by_origin": True,
        "mitigation_mode": "wick",
        "full_mitigation_percent": 75.0,
        "min_bars_between_touches": 1,
        "min_bars_after_formation": 1,
        "confirmation_mode": "wick_touch",
        "min_touch_count": 1,
        "max_block_age_bars": 150,
        "invalidation_mode": "close",
        "min_quality_score": 0.3,
        "require_structure_alignment": False,
        "use_liquidity_confluence": True,
        "use_order_block_confluence": True,
        "use_fvg_confluence": True,
        "use_breaker_confluence": True,
        "confluence_formation_enabled": True,
        "nest_overlap_min_percent": 80.0,
    }
    defaults.update(overrides)
    return MitigationBlockConfig(**defaults)


def build_bullish_mitigation_base_candles(count: int = 25) -> list:
    """Build candles with a bearish origin and bullish displacement (bullish mitigation)."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    price = Decimal("2300")

    for index in range(14):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=price,
                high=price + Decimal("2"),
                low=price - Decimal("2"),
                close=price + Decimal("1"),
            )
        )
        price += Decimal("1")

    origin_index = len(candles)
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index),
            open_price=Decimal("2315"),
            high=Decimal("2316"),
            low=Decimal("2308"),
            close=Decimal("2309"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index + 1),
            open_price=Decimal("2309"),
            high=Decimal("2320"),
            low=Decimal("2308"),
            close=Decimal("2318"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index + 2),
            open_price=Decimal("2318"),
            high=Decimal("2330"),
            low=Decimal("2317"),
            close=Decimal("2328"),
        )
    )

    while len(candles) < count:
        index = len(candles)
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2325"),
                high=Decimal("2328"),
                low=Decimal("2323"),
                close=Decimal("2326"),
            )
        )

    return candles


def build_bearish_mitigation_base_candles(count: int = 25) -> list:
    """Build candles with a bullish origin and bearish displacement (bearish mitigation)."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []

    for index in range(10):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2350"),
                high=Decimal("2352"),
                low=Decimal("2348"),
                close=Decimal("2349"),
            )
        )

    origin_index = len(candles)
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index),
            open_price=Decimal("2340"),
            high=Decimal("2347"),
            low=Decimal("2339"),
            close=Decimal("2346"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index + 1),
            open_price=Decimal("2346"),
            high=Decimal("2347"),
            low=Decimal("2330"),
            close=Decimal("2332"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index + 2),
            open_price=Decimal("2332"),
            high=Decimal("2333"),
            low=Decimal("2315"),
            close=Decimal("2317"),
        )
    )

    while len(candles) < count:
        index = len(candles)
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2345"),
                high=Decimal("2348"),
                low=Decimal("2343"),
                close=Decimal("2346"),
            )
        )

    return candles


def primary_bullish_mitigation_origin_index(candles: list | None = None) -> int:
    """Return the origin bar index for the primary bullish mitigation formation."""
    candles = candles or build_bullish_mitigation_base_candles()
    return 14


def primary_bearish_mitigation_origin_index(candles: list | None = None) -> int:
    """Return the origin bar index for the primary bearish mitigation formation."""
    candles = candles or build_bearish_mitigation_base_candles()
    return 10


def build_bullish_mitigation_touch_candles() -> list:
    """Extend base candles with a wick retest into the bullish mitigation zone."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_mitigation_base_candles(20)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2326"),
            high=Decimal("2328"),
            low=Decimal("2305"),
            close=Decimal("2310"),
        )
    )
    return candles


def build_bullish_mitigation_partial_candles() -> list:
    """Extend base candles with a shallow wick retest (partial mitigation only)."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_mitigation_base_candles(20)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2326"),
            high=Decimal("2328"),
            low=Decimal("2312"),
            close=Decimal("2320"),
        )
    )
    return candles


def build_bearish_mitigation_touch_candles() -> list:
    """Extend base candles with a wick retest into the bearish mitigation zone."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bearish_mitigation_base_candles(20)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2346"),
            high=Decimal("2348"),
            low=Decimal("2335"),
            close=Decimal("2342"),
        )
    )
    return candles


def build_bullish_mitigation_full_candles() -> list:
    """Build candles where a bullish mitigation block is fully mitigated by deep wick."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_mitigation_base_candles(18)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2326"),
            high=Decimal("2328"),
            low=Decimal("2308"),
            close=Decimal("2312"),
        )
    )
    return candles


def build_bullish_mitigation_invalidation_candles() -> list:
    """Build candles where a bullish mitigation block is invalidated by close break."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_mitigation_touch_candles()
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2310"),
            high=Decimal("2312"),
            low=Decimal("2300"),
            close=Decimal("2302"),
        )
    )
    return candles


def build_mitigation_expiry_candles() -> tuple[list, MitigationBlockConfig]:
    """Build candles where a fresh mitigation block expires without retest."""
    from tests.unit.engines.conftest import make_candle

    config = mitigation_config(max_block_age_bars=3, min_candles=10)
    candles = build_bullish_mitigation_base_candles(18)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    for offset in range(5):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=offset),
                open_price=Decimal("2340"),
                high=Decimal("2345"),
                low=Decimal("2338"),
                close=Decimal("2342"),
            )
        )
    return candles, config


def parent_order_block_for_bullish_mitigation(candles: list) -> OrderBlock:
    """Return a synthetic order block enclosing the primary bullish mitigation zone."""
    origin_index = primary_bullish_mitigation_origin_index(candles)
    return OrderBlock(
        block_id="ob-bull-parent-test",
        direction=OrderBlockDirection.BULLISH,
        status=OrderBlockStatus.FRESH,
        high=Decimal("2318"),
        low=Decimal("2305"),
        origin_bar_index=origin_index,
        origin_time_utc=candles[origin_index].close_time_utc,
        displacement_bar_index=origin_index + 1,
        quality=OrderBlockQuality.HIGH,
        strength=Decimal("0.75"),
        structure_alignment=True,
        liquidity_confluence=False,
    )


def sample_htf_mitigation_block() -> MitigationBlock:
    """Return a synthetic HTF mitigation block for alignment tests."""
    return MitigationBlock(
        block_id="mb-htf-test",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("2318"),
        low=Decimal("2305"),
        origin_bar_index=5,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=7,
        displacement_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        formation_bar_index=7,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=MitigationBlockQuality.HIGH,
        strength=Decimal("0.8"),
        is_confirmed=False,
        confirmation_reason="HTF context block",
    )


@pytest.fixture
def mitigation_block_config() -> MitigationBlockConfig:
    return mitigation_config()


@pytest.fixture
def mitigation_publisher() -> MitigationBlockEventPublisher:
    return MitigationBlockEventPublisher()


@pytest.fixture
def mitigation_candles() -> list:
    return build_bullish_mitigation_base_candles(25)
