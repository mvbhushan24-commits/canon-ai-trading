"""Unit tests for evidence conflict detection."""

from decimal import Decimal

from backend.engines.market_decision.conflicts import ConflictDetector
from backend.engines.market_decision.schemas import (
    ConflictSeverity,
    DirectionBias,
    NormalizedEvidence,
    TradeDirection,
    WeightedEvidenceResult,
)
from tests.unit.engines.decision_conftest import decision_config


def _normalized(engine_id: str, bias: DirectionBias) -> NormalizedEvidence:
    return NormalizedEvidence(
        engine_id=engine_id,
        direction_bias=bias,
        confidence=Decimal("0.8"),
        strength=Decimal("0.8"),
        available=True,
        stale=False,
    )


def test_detect_no_conflict_when_single_direction() -> None:
    weighted = WeightedEvidenceResult(
        normalized=[
            _normalized("market_structure", DirectionBias.BULLISH),
            _normalized("order_block", DirectionBias.BULLISH),
        ],
        bullish_weight=Decimal("0.6"),
        bearish_weight=Decimal("0"),
    )
    report = ConflictDetector(decision_config()).detect(weighted)

    assert report.conflict_ratio == Decimal("0")
    assert report.severity is ConflictSeverity.NONE
    assert report.dominant_direction is TradeDirection.BUY


def test_detect_medium_conflict_at_warn_threshold() -> None:
    weighted = WeightedEvidenceResult(
        normalized=[
            _normalized("market_structure", DirectionBias.BULLISH),
            _normalized("market_liquidity", DirectionBias.BEARISH),
        ],
        bullish_weight=Decimal("0.40"),
        bearish_weight=Decimal("0.20"),
    )
    detector = ConflictDetector(decision_config())
    report = detector.detect(weighted)

    assert report.conflict_ratio == Decimal("0.5")
    assert report.severity is ConflictSeverity.MEDIUM
    assert detector.should_warn(report) is True
    assert detector.should_reject(report) is False


def test_reject_high_conflict() -> None:
    weighted = WeightedEvidenceResult(
        normalized=[
            _normalized("market_structure", DirectionBias.BULLISH),
            _normalized("market_liquidity", DirectionBias.BEARISH),
        ],
        bullish_weight=Decimal("0.45"),
        bearish_weight=Decimal("0.40"),
    )
    detector = ConflictDetector(decision_config())
    report = detector.detect(weighted)

    assert report.severity is ConflictSeverity.HIGH
    assert detector.should_reject(report) is True
    assert len(report.conflicting_engines) >= 1
