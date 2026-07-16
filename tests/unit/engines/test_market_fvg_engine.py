"""Unit tests for FairValueGapEngine."""

import pytest

from backend.engines.market_fvg import (
    FairValueGapBias,
    FairValueGapEngine,
    FairValueGapStatus,
    load_fair_value_gap_config,
)
from backend.engines.market_fvg.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
    ValidationError,
)
from tests.unit.engines.conftest import build_bullish_structure_candles, make_candle
from tests.unit.engines.fvg_conftest import build_bullish_fvg_candles
from tests.unit.engines.liquidity_conftest import build_sample_structure


def test_engine_analyze_returns_fair_value_gap_analysis(
    fvg_config,
    fvg_candles,
    sample_structure,
) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    result = engine.analyze(fvg_candles, sample_structure, timeframe="H1")

    assert result.symbol == "XAUUSD"
    assert result.timeframe == "H1"
    assert len(result.fair_value_gaps) > 0
    assert result.bias in FairValueGapBias
    assert result.state.bar_count >= 10


def test_engine_insufficient_data(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    with pytest.raises(InsufficientDataError):
        engine.analyze([])


def test_engine_unsupported_timeframe(fvg_config, fvg_candles, sample_structure) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    with pytest.raises(UnsupportedTimeframeError):
        engine.analyze(fvg_candles, sample_structure, timeframe="M1")


def test_engine_validation_failure(fvg_config, sample_structure) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    engine = FairValueGapEngine(config=fvg_config)
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
    fvg_config,
    fvg_candles,
    sample_structure,
    fvg_publisher,
) -> None:
    events: list[str] = []
    fvg_publisher.subscribe("*", lambda event: events.append(event.event_type))
    engine = FairValueGapEngine(config=fvg_config, publisher=fvg_publisher)
    engine.analyze(fvg_candles, sample_structure, timeframe="H1")

    assert "FairValueGapDetected" in events
    assert "BullishFairValueGapDetected" in events
    assert "analysis.fvg.completed" in events


def test_engine_detect_methods(fvg_config, sample_structure, fvg_candles) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    bullish = engine.detect_bullish_gaps(fvg_candles, sample_structure)
    bearish = engine.detect_bearish_gaps(fvg_candles, sample_structure)
    classified = engine.classify_lifecycle(bullish + bearish, fvg_candles)

    assert bullish
    assert classified
    assert all(gap.status in FairValueGapStatus for gap in classified)


def test_engine_reset_state(fvg_config, fvg_candles) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    engine.analyze(fvg_candles, timeframe="H1")
    assert engine.prior_state is not None

    engine.reset_state()
    assert engine.prior_state is None


def test_engine_handle_config_updated(fvg_config, fvg_candles) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    updated = fvg_config.model_copy(update={"min_quality_score": 0.9})
    engine.handle_config_updated(updated)

    assert engine.config.min_quality_score == 0.9


def test_engine_dependency_injection(fvg_config, fvg_publisher) -> None:
    from backend.engines.market_fvg.detector import FairValueGapDetector
    from backend.engines.market_fvg.validator import FairValueGapInputValidator

    detector = FairValueGapDetector(fvg_config)
    validator = FairValueGapInputValidator()
    engine = FairValueGapEngine(
        config=fvg_config,
        detector=detector,
        validator=validator,
        publisher=fvg_publisher,
    )

    assert engine.config is fvg_config
    assert engine.publisher is fvg_publisher


def test_engine_state_persistence(fvg_config, fvg_candles) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    first = engine.analyze(fvg_candles, timeframe="H1")
    second = engine.analyze(fvg_candles, timeframe="H1")

    assert engine.prior_state is not None
    assert second.state.bar_count == first.state.bar_count


def test_engine_with_structure_candles(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_bullish_structure_candles(30)
    structure = build_sample_structure()
    result = engine.analyze(candles, structure, timeframe="H1")

    assert result.symbol == candles[0].symbol


def test_public_package_exports() -> None:
    import backend.engines.market_fvg as market_fvg

    assert hasattr(market_fvg, "FairValueGapEngine")
    assert hasattr(market_fvg, "FairValueGapAnalysis")
    assert hasattr(market_fvg, "load_fair_value_gap_config")


def test_load_fair_value_gap_config_from_project() -> None:
    config = load_fair_value_gap_config()
    assert config.timeframes
    assert config.min_candles >= 1
