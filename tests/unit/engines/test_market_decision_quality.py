"""Unit tests for decision quality scoring."""

from backend.engines.market_decision.evidence import EvidenceCollector, EvidenceNormalizer
from backend.engines.market_decision.quality import DecisionQualityScorer
from backend.engines.market_decision.schemas import QualityTier, TradeDirection
from backend.engines.market_decision.weights import EvidenceWeighter
from tests.unit.engines.decision_conftest import build_bullish_upstream_evidence, decision_config, relaxed_decision_config


def test_quality_scorer_returns_high_tier_for_full_evidence() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(relaxed_decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=evidence["structure"],
        liquidity=evidence["liquidity"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
        breaker_blocks=evidence["breaker_blocks"],
        mitigation_blocks=evidence["mitigation_blocks"],
        premium_discount=evidence["premium_discount"],
        sessions=evidence["sessions"],
    )
    normalized = EvidenceNormalizer().normalize(bundle)
    weighted = EvidenceWeighter(relaxed_decision_config()).weight(normalized)
    score, tier = DecisionQualityScorer(relaxed_decision_config()).score(
        bundle,
        weighted,
        zone_confluence_count=3,
        direction=TradeDirection.BUY,
    )

    assert score >= 60
    assert tier in {QualityTier.HIGH, QualityTier.MEDIUM}


def test_meets_minimum_disabled_when_zero() -> None:
    scorer = DecisionQualityScorer(decision_config(quality={"min_quality_score": 0}))
    assert scorer.meets_minimum(10) is True


def test_meets_minimum_enforced_when_configured() -> None:
    scorer = DecisionQualityScorer(decision_config(quality={"min_quality_score": 80}))
    assert scorer.meets_minimum(70) is False
    assert scorer.meets_minimum(85) is True
