"""Shared helpers for breaker block engine tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.engines.market_breaker.config import BreakerBlockConfig
from backend.engines.market_breaker.publisher import BreakerBlockEventPublisher
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockQuality,
    OrderBlockStatus,
)


def breaker_config(**overrides) -> BreakerBlockConfig:
    """Build a test BreakerBlockConfig with sensible defaults."""
    defaults = {
        "enabled": True,
        "timeframes": ["M15", "H1", "H4"],
        "min_candles": 10,
        "lookback": 50,
        "pip_size": 0.1,
        "min_zone_size_pips": 2.0,
        "min_source_quality": "medium",
        "fvg_breaker_enabled": False,
        "deduplicate_by_source": True,
        "confirmation_mode": "wick_touch",
        "min_bars_after_invalidation": 1,
        "max_bars_after_invalidation": 50,
        "max_breaker_age_bars": 150,
        "invalidation_mode": "close",
        "mitigation_mode": "wick",
        "min_quality_score": 0.3,
        "require_structure_alignment": False,
        "use_liquidity_confluence": True,
        "use_fvg_confluence": True,
    }
    defaults.update(overrides)
    return BreakerBlockConfig(**defaults)


def build_breaker_base_candles(count: int = 25) -> list:
    """Build candles with an invalidated bullish order block (bearish breaker source)."""
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
    invalidation_index = len(candles)
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=invalidation_index),
            open_price=Decimal("2328"),
            high=Decimal("2330"),
            low=Decimal("2300"),
            close=Decimal("2302"),
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


def build_bearish_breaker_source_candles(count: int = 25) -> list:
    """Build candles with an invalidated bearish order block (bullish breaker source)."""
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
    invalidation_index = len(candles)
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=invalidation_index),
            open_price=Decimal("2317"),
            high=Decimal("2355"),
            low=Decimal("2316"),
            close=Decimal("2350"),
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


def invalidated_bullish_order_block(candles: list) -> OrderBlock:
    """Return a synthetic invalidated bullish order block for bearish breaker tests."""
    origin_index = 14
    invalidation_index = 17
    return OrderBlock(
        block_id="ob-bull-inv-test",
        direction=OrderBlockDirection.BULLISH,
        status=OrderBlockStatus.INVALIDATED,
        high=Decimal("2316"),
        low=Decimal("2308"),
        origin_bar_index=origin_index,
        origin_time_utc=candles[origin_index].close_time_utc,
        displacement_bar_index=origin_index + 1,
        invalidation_bar_index=invalidation_index,
        quality=OrderBlockQuality.HIGH,
        strength=Decimal("0.75"),
        structure_alignment=True,
        liquidity_confluence=False,
    )


def invalidated_bearish_order_block(candles: list) -> OrderBlock:
    """Return a synthetic invalidated bearish order block for bullish breaker tests."""
    origin_index = 10
    invalidation_index = 13
    return OrderBlock(
        block_id="ob-bear-inv-test",
        direction=OrderBlockDirection.BEARISH,
        status=OrderBlockStatus.INVALIDATED,
        high=Decimal("2347"),
        low=Decimal("2339"),
        origin_bar_index=origin_index,
        origin_time_utc=candles[origin_index].close_time_utc,
        displacement_bar_index=origin_index + 1,
        invalidation_bar_index=invalidation_index,
        quality=OrderBlockQuality.HIGH,
        strength=Decimal("0.75"),
        structure_alignment=True,
        liquidity_confluence=False,
    )


def build_bearish_breaker_confirmation_candles() -> list:
    """Extend base candles with a wick retest confirming a bearish breaker."""
    from tests.unit.engines.conftest import make_candle

    candles = build_breaker_base_candles(20)
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


def build_bullish_breaker_confirmation_candles() -> list:
    """Extend bearish-source candles with a wick retest confirming a bullish breaker."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bearish_breaker_source_candles(20)
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


def build_breaker_mitigation_candles() -> list:
    """Build candles where a confirmed bearish breaker is mitigated by wick touch."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bearish_breaker_confirmation_candles()
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2310"),
            high=Decimal("2315"),
            low=Decimal("2309"),
            close=Decimal("2312"),
        )
    )
    return candles


def build_breaker_invalidation_candles() -> list:
    """Build candles where a confirmed bullish breaker is invalidated by close break."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_breaker_confirmation_candles()
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2342"),
            high=Decimal("2343"),
            low=Decimal("2330"),
            close=Decimal("2331"),
        )
    )
    return candles


def build_breaker_expiry_candles() -> list:
    """Build candles where a candidate breaker expires without retest confirmation."""
    from tests.unit.engines.conftest import make_candle

    config = breaker_config(max_bars_after_invalidation=3)
    candles = build_breaker_base_candles(18)
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


@pytest.fixture
def breaker_block_config() -> BreakerBlockConfig:
    return breaker_config()


@pytest.fixture
def breaker_publisher() -> BreakerBlockEventPublisher:
    return BreakerBlockEventPublisher()


@pytest.fixture
def breaker_candles() -> list:
    return build_breaker_base_candles(25)
