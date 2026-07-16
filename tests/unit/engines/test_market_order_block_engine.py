"""Unit tests for OrderBlockEngine."""

import pytest

from backend.engines.market_order_block import (
    OrderBlockBias,
    OrderBlockEngine,
    OrderBlockStatus,
    load_order_block_config,
)
from backend.engines.market_order_block.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
    ValidationError,
)
from tests.unit.engines.conftest import build_bullish_structure_candles, make_candle
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.order_block_conftest import build_bullish_order_block_candles


def test_engine_analyze_returns_order_block_analysis(
    order_block_config,
    order_block_candles,
    sample_structure,
) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    result = engine.analyze(order_block_candles, sample_structure, timeframe="H1")

    assert result.symbol == "XAUUSD"
    assert result.timeframe == "H1"
    assert len(result.order_blocks) > 0
    assert result.bias in OrderBlockBias
    assert result.state.active_blocks == result.order_blocks


def test_engine_insufficient_data(order_block_config) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    with pytest.raises(InsufficientDataError):
        engine.analyze([])


def test_engine_unsupported_timeframe(
    order_block_config,
    order_block_candles,
    sample_structure,
) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    with pytest.raises(UnsupportedTimeframeError):
        engine.analyze(order_block_candles, sample_structure, timeframe="M1")


def test_engine_validation_failure(order_block_config, sample_structure) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    engine = OrderBlockEngine(config=order_block_config)
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
    order_block_config,
    order_block_candles,
    sample_structure,
    order_block_publisher,
) -> None:
    events: list[str] = []
    order_block_publisher.subscribe("*", lambda event: events.append(event.event_type))
    engine = OrderBlockEngine(config=order_block_config, publisher=order_block_publisher)
    engine.analyze(order_block_candles, sample_structure, timeframe="H1")

    assert "OrderBlockDetected" in events
    assert "analysis.order_block.completed" in events


def test_engine_detect_methods(order_block_config, sample_structure, order_block_candles) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    bullish = engine.detect_bullish_blocks(order_block_candles, sample_structure)
    bearish = engine.detect_bearish_blocks(order_block_candles, sample_structure)
    classified = engine.classify_lifecycle(bullish + bearish, order_block_candles)

    assert bullish or bearish
    assert classified
    assert all(block.status in OrderBlockStatus for block in classified)


def test_engine_reset_state(order_block_config, order_block_candles) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    engine.analyze(order_block_candles, timeframe="H1")
    assert engine.prior_state is not None

    engine.reset_state()
    assert engine.prior_state is None


def test_engine_handle_config_updated(order_block_config, order_block_candles) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    updated = order_block_config.model_copy(update={"min_quality_score": 0.9})
    engine.handle_config_updated(updated)

    assert engine.config.min_quality_score == 0.9


def test_engine_dependency_injection(order_block_config, order_block_publisher) -> None:
    from backend.engines.market_order_block.detector import OrderBlockDetector
    from backend.engines.market_order_block.validator import OrderBlockInputValidator

    detector = OrderBlockDetector(order_block_config)
    validator = OrderBlockInputValidator()
    engine = OrderBlockEngine(
        config=order_block_config,
        detector=detector,
        validator=validator,
        publisher=order_block_publisher,
    )

    assert engine.config is order_block_config
    assert engine.publisher is order_block_publisher


def test_public_package_exports() -> None:
    import backend.engines.market_order_block as market_order_block

    assert hasattr(market_order_block, "OrderBlockEngine")
    assert hasattr(market_order_block, "OrderBlockAnalysis")
    assert hasattr(market_order_block, "load_order_block_config")


def test_engine_with_structure_candles(order_block_config) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    candles = build_bullish_structure_candles(30)
    structure = build_sample_structure()
    result = engine.analyze(candles, structure, timeframe="H1")

    assert result.symbol == candles[0].symbol
    assert len(result.order_blocks) > 0


def test_load_order_block_config_from_project() -> None:
    config = load_order_block_config()
    assert config.timeframes
    assert config.min_candles >= 1
