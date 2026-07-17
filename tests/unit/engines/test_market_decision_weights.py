"""Unit tests for evidence weighting and confidence scoring."""

from decimal import Decimal

from backend.engines.market_decision.schemas import (
    ConflictReport,
    ConflictSeverity,
    DirectionBias,
    EvidenceSummaryItem,
    NormalizedEvidence,
)
from backend.engines.market_decision.weights import ConfidenceScorer, EvidenceWeighter
from tests.unit.engines.decision_conftest import decision_config


def _item(engine_id: str, bias: DirectionBias, *, stale: bool = False) -> NormalizedEvidence:
    return NormalizedEvidence(
        engine_id=engine_id,
        direction_bias=bias,
        confidence=Decimal("0.8"),
        strength=Decimal("0.8"),
        available=True,
        stale=stale,
    )


def test_weighter_accumulates_directional_contributions() -> None:
    normalized = [
        _item("market_structure", DirectionBias.BULLISH),
        _item("market_liquidity", DirectionBias.BULLISH),
        _item("market_sessions", DirectionBias.NEUTRAL),
    ]
    result = EvidenceWeighter(decision_config()).weight(normalized)

    assert result.bullish_weight > Decimal("0")
    assert result.bearish_weight == Decimal("0")
    assert result.confidence > 0
    assert len(result.summary) == 3


def test_weighter_reduces_stale_contribution() -> None:
    fresh = EvidenceWeighter(decision_config()).weight(
        [_item("market_structure", DirectionBias.BULLISH, stale=False)],
    )
    stale = EvidenceWeighter(decision_config()).weight(
        [_item("market_structure", DirectionBias.BULLISH, stale=True)],
    )

    assert stale.bullish_weight < fresh.bullish_weight
    assert any("stale" in warning for warning in stale.warnings)


def test_confidence_scorer_applies_conflict_and_confluence_adjustments() -> None:
    summary = [
        EvidenceSummaryItem(
            engine_id="market_structure",
            available=True,
            stale=False,
            direction_bias="bullish",
            confidence=Decimal("0.8"),
            weight=Decimal("0.2"),
            weighted_contribution=Decimal("0.12"),
        ),
    ]
    weighted_conflict = ConflictReport(severity=ConflictSeverity.MEDIUM)
    scorer = ConfidenceScorer(decision_config())

    base = scorer.score_from_contributions(
        summary,
        bullish_weight=Decimal("0.12"),
        bearish_weight=Decimal("0"),
    )
    adjusted = scorer.score(
        type("W", (), {"summary": summary, "bullish_weight": Decimal("0.12"), "bearish_weight": Decimal("0")})(),
        weighted_conflict,
        zone_confluence_count=3,
        stale_engine_count=1,
    )

    assert adjusted < base
    assert scorer.meets_minimum(50) is False
    assert scorer.meets_minimum(70) is True
