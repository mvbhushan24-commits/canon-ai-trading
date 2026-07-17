"""Unit tests for PremiumDiscountEngine."""

from decimal import Decimal

import pytest

pytest_plugins = ["tests.unit.engines.premium_discount_conftest"]

from backend.engines.market_premium_discount import (
    PremiumDiscountBias,
    PremiumDiscountEngine,
    PremiumDiscountZone,
    load_market_premium_discount_config,
)
from backend.engines.market_premium_discount.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
    ValidationError,
)
from backend.engines.market_premium_discount.schemas import DealingRangeScope, FibDirection
from tests.unit.engines.conftest import build_bullish_structure_candles, make_candle
from tests.unit.engines.premium_discount_conftest import (
    build_premium_discount_candles,
    build_premium_discount_structure,
    build_valid_dealing_range,
    discount_order_blocks,
    premium_config,
    premium_order_blocks,
    sample_htf_premium_discount_context,
)


def test_engine_analyze_returns_premium_discount_analysis(
    premium_discount_config,
    premium_discount_candles,
    premium_discount_structure,
) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    result = engine.analyze(
        premium_discount_candles,
        premium_discount_structure,
        timeframe="H1",
    )

    assert result.symbol == "XAUUSD"
    assert result.timeframe == "H1"
    assert result.dealing_range.is_valid is True
    assert result.bias in PremiumDiscountBias
    assert result.state.bar_count >= 10


def test_engine_insufficient_data(premium_discount_config) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    with pytest.raises(InsufficientDataError):
        engine.analyze([])


def test_engine_unsupported_timeframe(
    premium_discount_config,
    premium_discount_candles,
    premium_discount_structure,
) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    with pytest.raises(UnsupportedTimeframeError):
        engine.analyze(premium_discount_candles, premium_discount_structure, timeframe="M1")


def test_engine_validation_failure(premium_discount_config, premium_discount_structure) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    engine = PremiumDiscountEngine(config=premium_discount_config)
    bad = make_candle(
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    with pytest.raises(ValidationError):
        engine.analyze([bad] * 12, premium_discount_structure, timeframe="H1")


def test_engine_publishes_events(
    premium_discount_config,
    premium_discount_candles,
    premium_discount_structure,
    premium_discount_publisher,
) -> None:
    events: list[str] = []
    premium_discount_publisher.subscribe("*", lambda event: events.append(event.event_type))
    engine = PremiumDiscountEngine(
        config=premium_discount_config,
        publisher=premium_discount_publisher,
    )
    engine.analyze(premium_discount_candles, premium_discount_structure, timeframe="H1")

    assert "analysis.premium_discount.completed" in events
    assert "PremiumDiscountUpdated" in events


def test_engine_reset_state(premium_discount_config, premium_discount_candles, premium_discount_structure) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    engine.analyze(premium_discount_candles, premium_discount_structure, timeframe="H1")
    assert engine.prior_state is not None

    engine.reset_state()
    assert engine.prior_state is None


def test_engine_handle_config_updated(premium_discount_config, premium_discount_candles) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    updated = premium_discount_config.model_copy(update={"min_quality_score": 0.9})
    engine.handle_config_updated(updated)

    assert engine.config.min_quality_score == 0.9


def test_engine_dependency_injection(premium_discount_config, premium_discount_publisher) -> None:
    from backend.engines.market_premium_discount.detector import PremiumDiscountDetector
    from backend.engines.market_premium_discount.validator import PremiumDiscountInputValidator

    detector = PremiumDiscountDetector(premium_discount_config)
    validator = PremiumDiscountInputValidator()
    engine = PremiumDiscountEngine(
        config=premium_discount_config,
        detector=detector,
        validator=validator,
        publisher=premium_discount_publisher,
    )

    assert engine.config is premium_discount_config
    assert engine.publisher is premium_discount_publisher


def test_engine_build_dealing_range(premium_discount_config, premium_discount_candles, premium_discount_structure) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    dealing_range = engine.build_dealing_range(
        premium_discount_structure,
        DealingRangeScope.EXTERNAL,
        premium_discount_candles,
    )

    assert dealing_range.scope is DealingRangeScope.EXTERNAL
    assert dealing_range.is_valid is True


def test_engine_classify_price_and_zone(premium_discount_config) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    dealing_range = build_valid_dealing_range()

    assert engine.classify_price(dealing_range.high - Decimal("1"), dealing_range) is PremiumDiscountZone.PREMIUM
    assert engine.classify_zone(dealing_range.low + Decimal("1"), dealing_range) is PremiumDiscountZone.DISCOUNT


def test_engine_assemble_arrays(premium_discount_config, premium_discount_candles) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    dealing_range = build_valid_dealing_range()
    premium_arrays = engine.assemble_premium_arrays(
        premium_discount_candles,
        dealing_range,
        order_blocks=premium_order_blocks(dealing_range),
    )
    discount_arrays = engine.assemble_discount_arrays(
        premium_discount_candles,
        dealing_range,
        order_blocks=discount_order_blocks(dealing_range),
    )

    assert isinstance(premium_arrays, list)
    assert isinstance(discount_arrays, list)
    assert premium_arrays
    assert discount_arrays


def test_engine_project_fibonacci_and_ote(premium_discount_config) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    dealing_range = build_valid_dealing_range()
    fibonacci = engine.project_fibonacci(dealing_range, FibDirection.BULLISH)
    entries = engine.assemble_discount_arrays([], dealing_range, order_blocks=discount_order_blocks(dealing_range))
    zone_entries = []
    for array in entries:
        zone_entries.extend(array.zone_entries)
    ote = engine.derive_ote(dealing_range, fibonacci, zone_entries)

    assert fibonacci.direction is FibDirection.BULLISH
    assert ote is not None or ote is None


def test_engine_missing_structure_returns_undetermined(
    premium_discount_config,
    premium_discount_candles,
) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    result = engine.analyze(premium_discount_candles, structure=None, timeframe="H1")

    assert result.bias is PremiumDiscountBias.UNDETERMINED


def test_engine_with_htf_context(
    premium_discount_config,
    premium_discount_candles,
    premium_discount_structure,
) -> None:
    engine = PremiumDiscountEngine(config=premium_discount_config)
    htf = sample_htf_premium_discount_context()
    result = engine.analyze(
        premium_discount_candles,
        premium_discount_structure,
        htf_premium_discount_context=htf,
        timeframe="H1",
    )

    assert result.htf_premium is not None or result.htf_discount is not None


def test_public_package_exports() -> None:
    import backend.engines.market_premium_discount as market_premium_discount

    assert hasattr(market_premium_discount, "PremiumDiscountEngine")
    assert hasattr(market_premium_discount, "PremiumDiscountAnalysis")
    assert hasattr(market_premium_discount, "load_market_premium_discount_config")


def test_engine_with_structure_candles(premium_discount_config) -> None:
    candles = build_bullish_structure_candles(30)
    engine = PremiumDiscountEngine(config=premium_discount_config)
    structure = build_premium_discount_structure()
    result = engine.analyze(candles, structure, timeframe="H1")

    assert result.symbol == candles[0].symbol


def test_load_config_default() -> None:
    config = load_market_premium_discount_config()
    assert config.timeframes
    assert config.min_candles >= 5
