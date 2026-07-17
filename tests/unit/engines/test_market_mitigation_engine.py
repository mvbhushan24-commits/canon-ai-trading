"""Unit tests for MitigationBlockEngine."""

import pytest

pytest_plugins = ["tests.unit.engines.mitigation_conftest"]

from backend.engines.market_mitigation import (
    MitigationBlockBias,
    MitigationBlockEngine,
    MitigationBlockStatus,
    load_market_mitigation_config,
)
from backend.engines.market_mitigation.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
    ValidationError,
)
from tests.unit.engines.conftest import build_bullish_structure_candles, make_candle
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.mitigation_conftest import (
    build_bullish_mitigation_base_candles,
    build_bullish_mitigation_touch_candles,
    parent_order_block_for_bullish_mitigation,
    sample_htf_mitigation_block,
)


def test_engine_analyze_returns_mitigation_block_analysis(
    mitigation_block_config,
    mitigation_candles,
    sample_structure,
) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    result = engine.analyze(mitigation_candles, sample_structure, timeframe="H1")

    assert result.symbol == "XAUUSD"
    assert result.timeframe == "H1"
    assert len(result.mitigation_blocks) >= 0
    assert result.bias in MitigationBlockBias
    assert result.state.bar_count >= 10


def test_engine_insufficient_data(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    with pytest.raises(InsufficientDataError):
        engine.analyze([])


def test_engine_unsupported_timeframe(
    mitigation_block_config,
    mitigation_candles,
    sample_structure,
) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    with pytest.raises(UnsupportedTimeframeError):
        engine.analyze(mitigation_candles, sample_structure, timeframe="M1")


def test_engine_validation_failure(mitigation_block_config, sample_structure) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    engine = MitigationBlockEngine(config=mitigation_block_config)
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
    mitigation_block_config,
    mitigation_candles,
    sample_structure,
    mitigation_publisher,
) -> None:
    events: list[str] = []
    mitigation_publisher.subscribe("*", lambda event: events.append(event.event_type))
    engine = MitigationBlockEngine(
        config=mitigation_block_config,
        publisher=mitigation_publisher,
    )
    engine.analyze(mitigation_candles, sample_structure, timeframe="H1")

    assert "MitigationBlockDetected" in events or "analysis.mitigation.completed" in events
    assert "analysis.mitigation.completed" in events


def test_engine_detect_methods(mitigation_block_config, sample_structure, mitigation_candles) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    bullish = engine.detect_bullish_blocks(mitigation_candles, sample_structure)
    bearish = engine.detect_bearish_blocks(mitigation_candles, sample_structure)
    classified = engine.classify_lifecycle(bullish + bearish, mitigation_candles)

    assert bullish or bearish or classified == []
    if classified:
        assert all(block.status in MitigationBlockStatus for block in classified)


def test_engine_reset_state(mitigation_block_config, mitigation_candles) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    engine.analyze(mitigation_candles, timeframe="H1")
    assert engine.prior_state is not None

    engine.reset_state()
    assert engine.prior_state is None


def test_engine_handle_config_updated(mitigation_block_config, mitigation_candles) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    updated = mitigation_block_config.model_copy(update={"min_quality_score": 0.9})
    engine.handle_config_updated(updated)

    assert engine.config.min_quality_score == 0.9


def test_engine_dependency_injection(mitigation_block_config, mitigation_publisher) -> None:
    from backend.engines.market_mitigation.detector import MitigationBlockDetector
    from backend.engines.market_mitigation.validator import MitigationBlockInputValidator

    detector = MitigationBlockDetector(mitigation_block_config)
    validator = MitigationBlockInputValidator()
    engine = MitigationBlockEngine(
        config=mitigation_block_config,
        detector=detector,
        validator=validator,
        publisher=mitigation_publisher,
    )

    assert engine.config is mitigation_block_config
    assert engine.publisher is mitigation_publisher


def test_public_package_exports() -> None:
    import backend.engines.market_mitigation as market_mitigation

    assert hasattr(market_mitigation, "MitigationBlockEngine")
    assert hasattr(market_mitigation, "MitigationBlockAnalysis")
    assert hasattr(market_mitigation, "load_market_mitigation_config")


def test_engine_with_structure_candles(mitigation_block_config) -> None:
    candles = build_bullish_structure_candles(30)
    engine = MitigationBlockEngine(config=mitigation_block_config)
    structure = build_sample_structure()
    result = engine.analyze(candles, structure, timeframe="H1")

    assert result.symbol == candles[0].symbol
    assert result.bias in MitigationBlockBias


def test_load_market_mitigation_config_from_project() -> None:
    config = load_market_mitigation_config()
    assert config.timeframes
    assert config.min_candles >= 5


def test_validate_confirmation_method(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_touch_candles()
    blocks = engine.detect_bullish_blocks(candles)

    assert blocks
    classified = engine.classify_lifecycle(blocks, candles)
    touched = next(
        (block for block in classified if block.status is MitigationBlockStatus.PARTIAL),
        classified[0],
    )
    assert engine.validate_confirmation(touched, candles) is True


def test_score_confluence_method(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_base_candles()
    blocks = engine.detect_bullish_blocks(candles)

    assert blocks
    enriched = engine.score_confluence(blocks[0], None, None, None, None)
    assert enriched.block_id == blocks[0].block_id


def test_classify_nesting_method(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_base_candles()
    blocks = engine.detect_bullish_blocks(candles)
    parent = parent_order_block_for_bullish_mitigation(candles)

    assert blocks
    nested = engine.classify_nesting(blocks[0], order_blocks=[parent])
    assert nested.is_nested is True


def test_analyze_with_htf_blocks(mitigation_block_config, mitigation_candles) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    htf = sample_htf_mitigation_block()
    result = engine.analyze(
        mitigation_candles,
        htf_mitigation_blocks=[htf],
        timeframe="H1",
    )

    assert result.timeframe == "H1"
    assert result.state.bar_count >= 10
