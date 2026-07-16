"""Unit tests for fair value gap lifecycle classification."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_fvg.engine import FairValueGapEngine
from backend.engines.market_fvg.mitigation import MitigationManager
from backend.engines.market_fvg.schemas import FairValueGapStatus
from tests.unit.engines.fvg_conftest import (
    build_bullish_fvg_candles,
    build_ce_mitigation_candles,
    build_full_fill_candles,
    build_invalidation_candles,
    build_partial_fill_candles,
    primary_bullish_gap,
)


def test_open_gap_status(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_bullish_fvg_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    assert analysis.open_gaps or analysis.fair_value_gaps
    assert any(
        gap.status is FairValueGapStatus.OPEN for gap in analysis.fair_value_gaps
    )


def test_partial_fill_status(fvg_config) -> None:
    config = fvg_config.model_copy(update={"mitigation_mode": "partial"})
    engine = FairValueGapEngine(config=config)
    candles = build_partial_fill_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    assert any(gap.status is FairValueGapStatus.PARTIAL for gap in analysis.fair_value_gaps)


def test_ce_mitigation(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_ce_mitigation_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    mitigated = [gap for gap in analysis.fair_value_gaps if gap.status is FairValueGapStatus.MITIGATED]
    assert mitigated
    assert mitigated[0].mitigation_bar_index is not None


def test_full_fill_status(fvg_config) -> None:
    config = fvg_config.model_copy(update={"mitigation_mode": "full_fill", "fill_mode": "wick"})
    engine = FairValueGapEngine(config=config)
    candles = build_full_fill_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    filled = [gap for gap in analysis.fair_value_gaps if gap.status is FairValueGapStatus.FILLED]
    assert filled
    assert filled[0].fill_percent == Decimal("100")
    assert filled[0].fill_bar_index is not None


def test_invalidation_on_close_break(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_invalidation_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    invalidated = [
        gap for gap in analysis.fair_value_gaps if gap.status is FairValueGapStatus.INVALIDATED
    ]
    assert invalidated
    assert invalidated[0].invalidation_bar_index is not None


def test_gap_expiration(fvg_config) -> None:
    config = fvg_config.model_copy(update={"max_gap_age_bars": 5})
    engine = FairValueGapEngine(config=config)
    candles = build_bullish_fvg_candles(25)
    analysis = engine.analyze(candles, timeframe="H1")

    expired = [gap for gap in analysis.fair_value_gaps if gap.status is FairValueGapStatus.EXPIRED]
    assert expired
    assert expired[0].expiration_bar_index is not None


def test_compute_fill_percent(fvg_config) -> None:
    from tests.unit.engines.conftest import make_candle

    config = fvg_config.model_copy(update={"mitigation_mode": "partial"})
    engine = FairValueGapEngine(config=config)
    candles = build_bullish_fvg_candles(15)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2323"),
            high=Decimal("2324"),
            low=Decimal("2303"),
            close=Decimal("2308"),
        )
    )
    gap = primary_bullish_gap(engine, candles)

    fill_percent = engine.compute_fill_percent(gap, candles)
    assert fill_percent > Decimal("0")
    assert fill_percent < Decimal("100")


def test_classify_lifecycle_method(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_ce_mitigation_candles()
    gaps = engine.detect_bullish_gaps(candles)
    classified = engine.classify_lifecycle(gaps, candles)

    assert classified
    assert any(gap.status is FairValueGapStatus.MITIGATED for gap in classified)


def test_premium_discount_classification(fvg_config, sample_structure) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_bullish_fvg_candles()
    gaps = engine.detect_bullish_gaps(candles, sample_structure)

    assert gaps
    zone = engine.classify_premium_discount(gaps[0], sample_structure)
    assert zone.value in {"premium", "discount", "equilibrium"}


def test_nesting_resolution(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_bullish_fvg_candles(25)
    analysis = engine.analyze(candles, timeframe="H1")
    nested = engine.resolve_nesting(analysis.fair_value_gaps)

    assert len(nested) == len(analysis.fair_value_gaps)


def test_mitigation_manager_premium_discount_score(fvg_config) -> None:
    from backend.engines.market_fvg.schemas import (
        FairValueGap,
        FairValueGapDirection,
        FairValueGapQuality,
        FairValueGapStatus,
        PremiumDiscountZone,
    )
    from datetime import UTC, datetime

    manager = MitigationManager(fvg_config)
    gap = FairValueGap(
        gap_id="test",
        direction=FairValueGapDirection.BULLISH,
        status=FairValueGapStatus.OPEN,
        high=Decimal("2305"),
        low=Decimal("2300"),
        ce_price=Decimal("2302.5"),
        gap_size=Decimal("5"),
        gap_size_pips=Decimal("50"),
        origin_bar_index=10,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        candle_a_index=10,
        candle_b_index=11,
        candle_c_index=12,
        quality=FairValueGapQuality.MEDIUM,
        strength=Decimal("0.6"),
    )

    discount_score = MitigationManager.premium_discount_alignment_score(
        gap,
        PremiumDiscountZone.DISCOUNT,
    )
    premium_score = MitigationManager.premium_discount_alignment_score(
        gap,
        PremiumDiscountZone.PREMIUM,
    )
    assert discount_score > premium_score
