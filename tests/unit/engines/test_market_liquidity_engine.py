"""Unit tests for LiquidityEngine."""

import pytest

from backend.engines.market_liquidity import LiquidityEngine, LiquidityKind, LiquiditySide
from backend.engines.market_liquidity.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
    ValidationError,
)
from tests.unit.engines.conftest import build_bullish_structure_candles, make_candle


def test_engine_analyze_returns_liquidity_analysis(
    liquidity_config,
    liquidity_candles,
    sample_structure,
) -> None:
    engine = LiquidityEngine(config=liquidity_config)
    result = engine.analyze(liquidity_candles, sample_structure, timeframe="H1")

    assert result.symbol == "XAUUSD"
    assert result.timeframe == "H1"
    assert len(result.external_liquidity) > 0
    assert len(result.internal_liquidity) > 0
    assert result.bias in LiquiditySide


def test_engine_insufficient_data(liquidity_config) -> None:
    engine = LiquidityEngine(config=liquidity_config)
    with pytest.raises(InsufficientDataError):
        engine.analyze([])


def test_engine_unsupported_timeframe(
    liquidity_config, liquidity_candles, sample_structure,
) -> None:
    engine = LiquidityEngine(config=liquidity_config)
    with pytest.raises(UnsupportedTimeframeError):
        engine.analyze(liquidity_candles, sample_structure, timeframe="M1")


def test_engine_validation_failure(liquidity_config, sample_structure) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    engine = LiquidityEngine(config=liquidity_config)
    bad = make_candle(
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    with pytest.raises(ValidationError):
        engine.analyze([bad] * 12, sample_structure, timeframe="H1")


def test_engine_publishes_events(
    liquidity_config,
    liquidity_candles,
    sample_structure,
    liquidity_publisher,
) -> None:
    events: list[str] = []
    liquidity_publisher.subscribe("*", lambda e: events.append(e.event_type))
    engine = LiquidityEngine(config=liquidity_config, publisher=liquidity_publisher)
    engine.analyze(liquidity_candles, sample_structure, timeframe="H1")

    assert "LiquidityDetectedEvent" in events
    assert "analysis.liquidity.completed" in events


def test_engine_detect_methods(liquidity_config, sample_structure, liquidity_candles) -> None:
    engine = LiquidityEngine(config=liquidity_config)
    equal_highs = engine.detect_equal_highs(sample_structure)
    equal_lows = engine.detect_equal_lows(sample_structure)
    buy_side = engine.detect_buy_side(equal_highs)
    sell_side = engine.detect_sell_side(equal_lows)

    assert buy_side or equal_highs == []
    assert sell_side or equal_lows == []
    sweeps = engine.detect_sweeps(
        liquidity_candles,
        buy_side + sell_side,
        "H1",
    )
    engine.detect_grabs(liquidity_candles, sweeps, "H1")


def test_public_package_exports() -> None:
    import backend.engines.market_liquidity as market_liquidity

    assert hasattr(market_liquidity, "LiquidityEngine")
    assert hasattr(market_liquidity, "LiquidityAnalysis")
    assert hasattr(market_liquidity, "load_market_liquidity_config")


def test_internal_liquidity_from_structure(liquidity_config, sample_structure) -> None:
    engine = LiquidityEngine(config=liquidity_config)
    result = engine.analyze(
        build_bullish_structure_candles(30),
        sample_structure,
        timeframe="H1",
    )
    internal_kinds = {level.kind for level in result.internal_liquidity}
    assert LiquidityKind.INTERNAL_SWING_HIGH in internal_kinds
    assert LiquidityKind.INTERNAL_SWING_LOW in internal_kinds
