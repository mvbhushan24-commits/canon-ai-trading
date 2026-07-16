"""Shared fixtures for engine unit tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.config import MarketLiquidityConfig
from backend.engines.market_liquidity.publisher import LiquidityEventPublisher
from backend.engines.market_order_block.config import OrderBlockConfig
from backend.engines.market_order_block.publisher import OrderBlockEventPublisher
from backend.engines.market_structure.config import MarketStructureConfig
from backend.engines.market_structure.publisher import StructureEventPublisher
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.order_block_conftest import build_bullish_order_block_candles


def make_candle(
    *,
    symbol: str = "XAUUSD",
    timeframe: str = "H1",
    open_time: datetime,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    is_closed: bool = True,
) -> NormalizedCandle:
    return NormalizedCandle(
        symbol=symbol,
        timeframe=timeframe,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100,
        open_time_utc=open_time,
        close_time_utc=open_time + timedelta(hours=1),
        is_closed=is_closed,
    )


def build_bullish_structure_candles(count: int = 30) -> list[NormalizedCandle]:
    """Build synthetic candles with swing-friendly price action."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[NormalizedCandle] = []
    price = Decimal("2300")

    for index in range(count):
        wave = index % 6
        if wave in {0, 1}:
            open_p = price
            close_p = price + Decimal("5")
            high_p = close_p + Decimal("2")
            low_p = open_p - Decimal("1")
            price = close_p
        elif wave in {2, 3}:
            open_p = price
            close_p = price - Decimal("4")
            high_p = open_p + Decimal("1")
            low_p = close_p - Decimal("2")
            price = close_p
        else:
            open_p = price
            close_p = price + Decimal("6")
            high_p = close_p + Decimal("3")
            low_p = open_p - Decimal("1")
            price = close_p

        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
            )
        )

    return candles


@pytest.fixture
def structure_config() -> MarketStructureConfig:
    return MarketStructureConfig(
        enabled=True,
        timeframes=["H1", "H4"],
        swing_lookback=2,
        internal_swing_lookback=1,
        external_swing_lookback=2,
        min_confidence=0.3,
        min_candles=10,
    )


@pytest.fixture
def structure_publisher() -> StructureEventPublisher:
    return StructureEventPublisher()


@pytest.fixture
def bullish_candles() -> list[NormalizedCandle]:
    return build_bullish_structure_candles(30)


@pytest.fixture
def liquidity_config() -> MarketLiquidityConfig:
    return MarketLiquidityConfig(
        enabled=True,
        timeframes=["H1", "H4"],
        equal_high_tolerance=10.0,
        equal_low_tolerance=10.0,
        pip_size=0.1,
        minimum_cluster_size=2,
        lookback=50,
        min_candles=10,
        session_filter=["asian", "london", "new_york"],
        sweep_rejection_ratio=0.4,
        zone_buffer_pips=2.0,
    )


@pytest.fixture
def liquidity_publisher() -> LiquidityEventPublisher:
    return LiquidityEventPublisher()


@pytest.fixture
def sample_structure():
    return build_sample_structure()


@pytest.fixture
def liquidity_candles() -> list[NormalizedCandle]:
    return build_bullish_structure_candles(30)


@pytest.fixture
def order_block_config() -> OrderBlockConfig:
    return OrderBlockConfig(
        enabled=True,
        timeframes=["H1", "H4"],
        min_candles=10,
        lookback=50,
        zone_mode="body",
        min_displacement_pips=5.0,
        min_impulse_candles=2,
        pip_size=0.1,
        max_block_age_bars=200,
        min_quality_score=0.4,
        require_structure_alignment=False,
        use_liquidity_confluence=True,
        mitigation_touch_mode="wick",
        invalidation_mode="close",
    )


@pytest.fixture
def order_block_publisher() -> OrderBlockEventPublisher:
    return OrderBlockEventPublisher()


@pytest.fixture
def order_block_candles() -> list[NormalizedCandle]:
    return build_bullish_order_block_candles(25)
