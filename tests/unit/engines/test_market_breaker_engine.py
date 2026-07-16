"""Unit tests for BreakerBlockEngine."""

import pytest

pytest_plugins = ["tests.unit.engines.order_breaker_conftest"]

from backend.engines.market_breaker import (
    BreakerBlockBias,
    BreakerBlockEngine,
    BreakerBlockStatus,
    load_market_breaker_config,
)
from backend.engines.market_breaker.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
    ValidationError,
)
from tests.unit.engines.conftest import build_bullish_structure_candles, make_candle
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.order_breaker_conftest import (
    build_bearish_breaker_confirmation_candles,
    build_breaker_base_candles,
    invalidated_bullish_order_block,
)


def test_engine_analyze_returns_breaker_block_analysis(
    breaker_block_config,
    breaker_candles,
    sample_structure,
) -> None:
    block = invalidated_bullish_order_block(breaker_candles)
    engine = BreakerBlockEngine(config=breaker_block_config)
    result = engine.analyze(
        breaker_candles,
        sample_structure,
        invalidated_order_blocks=[block],
        timeframe="H1",
    )

    assert result.symbol == "XAUUSD"
    assert result.timeframe == "H1"
    assert len(result.breaker_blocks) > 0
    assert result.bias in BreakerBlockBias
    assert result.state.bar_count >= 10


def test_engine_insufficient_data(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    with pytest.raises(InsufficientDataError):
        engine.analyze([])


def test_engine_unsupported_timeframe(
    breaker_block_config,
    breaker_candles,
    sample_structure,
) -> None:
    block = invalidated_bullish_order_block(breaker_candles)
    engine = BreakerBlockEngine(config=breaker_block_config)
    with pytest.raises(UnsupportedTimeframeError):
        engine.analyze(
            breaker_candles,
            sample_structure,
            invalidated_order_blocks=[block],
            timeframe="M1",
        )


def test_engine_validation_failure(breaker_block_config, sample_structure) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    engine = BreakerBlockEngine(config=breaker_block_config)
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
    breaker_block_config,
    breaker_candles,
    sample_structure,
    breaker_publisher,
) -> None:
    block = invalidated_bullish_order_block(breaker_candles)
    events: list[str] = []
    breaker_publisher.subscribe("*", lambda event: events.append(event.event_type))
    engine = BreakerBlockEngine(
        config=breaker_block_config,
        publisher=breaker_publisher,
    )
    engine.analyze(
        breaker_candles,
        sample_structure,
        invalidated_order_blocks=[block],
        timeframe="H1",
    )

    assert "BreakerBlockDetected" in events
    assert "analysis.breaker.completed" in events


def test_engine_detect_methods(breaker_block_config, sample_structure, breaker_candles) -> None:
    block = invalidated_bullish_order_block(breaker_candles)
    engine = BreakerBlockEngine(config=breaker_block_config)
    bearish = engine.detect_bearish_breakers(breaker_candles, [block], sample_structure)
    bullish = engine.detect_bullish_breakers(breaker_candles, [block], sample_structure)
    classified = engine.classify_lifecycle(bearish + bullish, breaker_candles)

    assert bearish or bullish
    assert classified
    assert all(b.status in BreakerBlockStatus for b in classified)


def test_engine_reset_state(breaker_block_config, breaker_candles) -> None:
    block = invalidated_bullish_order_block(breaker_candles)
    engine = BreakerBlockEngine(config=breaker_block_config)
    engine.analyze(breaker_candles, invalidated_order_blocks=[block], timeframe="H1")
    assert engine.prior_state is not None

    engine.reset_state()
    assert engine.prior_state is None


def test_engine_handle_config_updated(breaker_block_config, breaker_candles) -> None:
    block = invalidated_bullish_order_block(breaker_candles)
    engine = BreakerBlockEngine(config=breaker_block_config)
    updated = breaker_block_config.model_copy(update={"min_quality_score": 0.9})
    engine.handle_config_updated(updated)

    assert engine.config.min_quality_score == 0.9


def test_engine_dependency_injection(breaker_block_config, breaker_publisher) -> None:
    from backend.engines.market_breaker.detector import BreakerBlockDetector
    from backend.engines.market_breaker.validator import BreakerBlockInputValidator

    detector = BreakerBlockDetector(breaker_block_config)
    validator = BreakerBlockInputValidator()
    engine = BreakerBlockEngine(
        config=breaker_block_config,
        detector=detector,
        validator=validator,
        publisher=breaker_publisher,
    )

    assert engine.config is breaker_block_config
    assert engine.publisher is breaker_publisher


def test_public_package_exports() -> None:
    import backend.engines.market_breaker as market_breaker

    assert hasattr(market_breaker, "BreakerBlockEngine")
    assert hasattr(market_breaker, "BreakerBlockAnalysis")
    assert hasattr(market_breaker, "load_market_breaker_config")


def test_engine_with_structure_candles(breaker_block_config) -> None:
    candles = build_bullish_structure_candles(30)
    engine = BreakerBlockEngine(config=breaker_block_config)
    structure = build_sample_structure()
    result = engine.analyze(candles, structure, timeframe="H1")

    assert result.symbol == candles[0].symbol
    assert result.bias in BreakerBlockBias


def test_load_market_breaker_config_from_project() -> None:
    config = load_market_breaker_config()
    assert config.timeframes
    assert config.min_candles >= 1


def test_validate_confirmation_method(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_bearish_breaker_confirmation_candles()
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block])

    assert breakers
    assert engine.validate_confirmation(breakers[0], candles) is True


def test_score_confluence_method(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block])

    assert breakers
    enriched = engine.score_confluence(breakers[0], None, None)
    assert enriched.breaker_id == breakers[0].breaker_id
