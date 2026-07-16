"""Unit tests for fair value gap quality scoring."""

from decimal import Decimal

from backend.engines.market_fvg.engine import FairValueGapEngine
from backend.engines.market_fvg.quality import MTFAlignmentScorer, QualityScorer
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapQuality,
    FairValueGapStatus,
)
from tests.unit.engines.fvg_conftest import build_bullish_fvg_candles
from tests.unit.engines.liquidity_conftest import build_sample_structure


def test_passes_minimum(fvg_config) -> None:
    scorer = QualityScorer(fvg_config)
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_bullish_fvg_candles()
    gaps = engine.detect_bullish_gaps(candles, build_sample_structure())

    assert gaps
    assert scorer.passes_minimum(gaps[0].strength)


def test_structure_alignment_scoring(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_bullish_fvg_candles()
    structure = build_sample_structure()

    with_structure = engine.detect_bullish_gaps(candles, structure)
    without_structure = engine.detect_bullish_gaps(candles)

    assert with_structure
    assert without_structure
    assert with_structure[0].structure_alignment is True
    assert without_structure[0].structure_alignment is False


def test_quality_tier_classification(fvg_config) -> None:
    engine = FairValueGapEngine(config=fvg_config)
    candles = build_bullish_fvg_candles()
    gaps = engine.detect_bullish_gaps(candles, build_sample_structure())

    assert gaps
    assert gaps[0].quality in {
        FairValueGapQuality.HIGH,
        FairValueGapQuality.MEDIUM,
        FairValueGapQuality.LOW,
    }
    assert gaps[0].strength >= Decimal(str(fvg_config.min_quality_score))


def test_mtf_alignment_scoring(fvg_config) -> None:
    from datetime import UTC, datetime

    from backend.engines.market_fvg.detector import FairValueGapDetector

    detector = FairValueGapDetector(fvg_config)
    candles = build_bullish_fvg_candles()
    child_gaps = detector.detect_bullish_gaps(candles, timeframe="H1")

    parent_gap = FairValueGap(
        gap_id="parent",
        direction=FairValueGapDirection.BULLISH,
        status=FairValueGapStatus.OPEN,
        high=Decimal("2310"),
        low=Decimal("2295"),
        ce_price=Decimal("2302.5"),
        gap_size=Decimal("15"),
        gap_size_pips=Decimal("150"),
        origin_bar_index=8,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        candle_a_index=8,
        candle_b_index=9,
        candle_c_index=10,
        quality=FairValueGapQuality.HIGH,
        strength=Decimal("0.8"),
    )

    assert child_gaps
    alignment = detector.score_mtf_alignment(
        child_gaps[0],
        [parent_gap],
        timeframe="H1",
    )
    assert alignment is not None
    assert alignment.alignment_score > Decimal("0")


def test_mtf_scorer_overlap_ratio(fvg_config) -> None:
    from datetime import UTC, datetime

    scorer = MTFAlignmentScorer(fvg_config)
    child = FairValueGap(
        gap_id="child",
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
    parent = child.model_copy(
        update={
            "gap_id": "parent",
            "high": Decimal("2310"),
            "low": Decimal("2295"),
            "gap_size": Decimal("15"),
        },
    )

    ratio = MTFAlignmentScorer._overlap_ratio(child, parent)
    assert ratio == Decimal("1")


def test_min_quality_gate_filters_weak_gaps(fvg_config) -> None:
    config = fvg_config.model_copy(update={"min_quality_score": 0.99})
    engine = FairValueGapEngine(config=config)
    candles = build_bullish_fvg_candles()
    gaps = engine.detect_bullish_gaps(candles)

    assert not gaps
