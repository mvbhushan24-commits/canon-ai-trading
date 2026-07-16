"""Unit tests for MarketStructureEngine."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure import MarketStructureEngine, TrendDirection
from backend.engines.market_structure.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
    ValidationError,
)
from tests.unit.engines.conftest import build_bullish_structure_candles, make_candle


def test_engine_analyze_returns_market_structure(
    structure_config,
    bullish_candles: list[NormalizedCandle],
) -> None:
    engine = MarketStructureEngine(config=structure_config)
    result = engine.analyze(bullish_candles)

    assert result.symbol == "XAUUSD"
    assert result.timeframe == "H1"
    assert result.current_trend in TrendDirection
    assert isinstance(result.swing_highs, list)
    assert isinstance(result.swing_lows, list)
    assert result.internal_structure is not None
    assert result.external_structure is not None
    assert result.structure_events


def test_engine_insufficient_data(structure_config) -> None:
    engine = MarketStructureEngine(config=structure_config)
    with pytest.raises(InsufficientDataError):
        engine.analyze([])


def test_engine_unsupported_timeframe(
    structure_config,
    bullish_candles: list[NormalizedCandle],
) -> None:
    engine = MarketStructureEngine(config=structure_config)
    with pytest.raises(UnsupportedTimeframeError):
        engine.analyze(bullish_candles, timeframe="M1")


def test_engine_validation_failure(structure_config) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bad = make_candle(
        open_time=start,
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("100"),
    )
    candles = build_bullish_structure_candles(12) + [bad]
    engine = MarketStructureEngine(config=structure_config)
    with pytest.raises(ValidationError):
        engine.analyze(candles)


def test_engine_publishes_events(
    structure_config,
    structure_publisher,
    bullish_candles: list[NormalizedCandle],
) -> None:
    received: list[str] = []
    structure_publisher.subscribe("*", lambda e: received.append(e.event_type))
    engine = MarketStructureEngine(
        config=structure_config,
        publisher=structure_publisher,
    )
    engine.analyze(bullish_candles)

    assert "StructureUpdated" in received
    assert "analysis.structure.completed" in received


def test_engine_state_continuity(
    structure_config,
    bullish_candles: list[NormalizedCandle],
) -> None:
    engine = MarketStructureEngine(config=structure_config)
    first = engine.analyze(bullish_candles[:20])
    second = engine.analyze(bullish_candles, prior_state=first.current_structure_state)

    assert second.current_structure_state.bar_count >= first.current_structure_state.bar_count


def test_engine_reset_state(
    structure_config,
    bullish_candles: list[NormalizedCandle],
) -> None:
    engine = MarketStructureEngine(config=structure_config)
    engine.analyze(bullish_candles)
    assert engine.prior_state is not None
    engine.reset_state()
    assert engine.prior_state is None


def test_public_package_exports() -> None:
    from backend.engines import market_structure

    assert hasattr(market_structure, "MarketStructureEngine")
    assert hasattr(market_structure, "MarketStructure")


def test_regression_undetermined_with_few_swings(structure_config) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    flat = [
        make_candle(
            open_time=start + timedelta(hours=i),
            open_price=Decimal("100"),
            high=Decimal("100.5"),
            low=Decimal("99.5"),
            close=Decimal("100"),
        )
        for i in range(12)
    ]
    engine = MarketStructureEngine(config=structure_config)
    result = engine.analyze(flat)
    assert result.current_trend == TrendDirection.UNDETERMINED
