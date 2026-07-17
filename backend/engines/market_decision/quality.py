"""Decision quality scoring."""

from decimal import Decimal

from backend.engines.market_decision.config import MarketDecisionConfig
from backend.engines.market_decision.schemas import (
    EvidenceBundle,
    QualityTier,
    TradeDirection,
    WeightedEvidenceResult,
)
from backend.engines.market_decision.validator import session_quality_rank


class DecisionQualityScorer:
    """Weighted decision quality model separate from confidence."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def score(
        self,
        bundle: EvidenceBundle,
        weighted: WeightedEvidenceResult,
        *,
        zone_confluence_count: int,
        direction: TradeDirection,
    ) -> tuple[int, QualityTier]:
        if not self._config.quality.enabled:
            return 0, QualityTier.LOW

        weights = self._config.quality.dimension_weights
        completeness = bundle.availability.available_count / 8
        zone_score = min(zone_confluence_count / 4, 1.0)
        structure_score = self._structure_clarity(bundle, direction)
        liquidity_score = self._liquidity_confirmation(bundle)
        pd_score = self._premium_discount_alignment(bundle, direction)
        session_score = self._session_quality(bundle)

        raw = (
            weights.evidence_completeness * completeness
            + weights.zone_confluence * zone_score
            + weights.structure_clarity * structure_score
            + weights.liquidity_confirmation * liquidity_score
            + weights.premium_discount_alignment * pd_score
            + weights.session_quality * session_score
        )
        quality_score = int(round(raw * 100))
        tier = self._tier(quality_score)
        return quality_score, tier

    def meets_minimum(self, quality_score: int) -> bool:
        minimum = self._config.quality.min_quality_score
        return minimum <= 0 or quality_score >= minimum

    def _tier(self, score: int) -> QualityTier:
        thresholds = self._config.quality.tier_thresholds
        if score >= thresholds.high:
            return QualityTier.HIGH
        if score >= thresholds.medium:
            return QualityTier.MEDIUM
        return QualityTier.LOW

    def _structure_clarity(self, bundle: EvidenceBundle, direction: TradeDirection) -> float:
        structure = bundle.structure
        if structure is None:
            return 0.0
        score = float(min(max(structure.confidence, Decimal("0")), Decimal("1")))
        if structure.bos_events:
            score = min(score + 0.2, 1.0)
        if direction is TradeDirection.BUY and structure.current_trend.value == "bullish":
            score = min(score + 0.1, 1.0)
        if direction is TradeDirection.SELL and structure.current_trend.value == "bearish":
            score = min(score + 0.1, 1.0)
        return score

    def _liquidity_confirmation(self, bundle: EvidenceBundle) -> float:
        liquidity = bundle.liquidity
        if liquidity is None:
            return 0.0
        score = float(min(max(liquidity.confidence, Decimal("0")), Decimal("1")))
        if liquidity.sweeps:
            score = min(score + 0.2, 1.0)
        if liquidity.grabs:
            score = min(score + 0.1, 1.0)
        return score

    def _premium_discount_alignment(self, bundle: EvidenceBundle, direction: TradeDirection) -> float:
        pd = bundle.premium_discount
        if pd is None:
            return 0.0
        score = float(min(max(pd.confidence, Decimal("0")), Decimal("1")))
        if pd.ote_zone is not None:
            score = min(score + 0.15, 1.0)
        if pd.institutional_context.mtf_aligned:
            score = min(score + 0.15, 1.0)
        if direction is TradeDirection.BUY and pd.price_location.value == "discount":
            score = min(score + 0.1, 1.0)
        if direction is TradeDirection.SELL and pd.price_location.value == "premium":
            score = min(score + 0.1, 1.0)
        return score

    def _session_quality(self, bundle: EvidenceBundle) -> float:
        sessions = bundle.sessions
        if sessions is None:
            return 0.0
        base = session_quality_rank(sessions.quality) / 2
        if sessions.active_kill_zones:
            best = max(session_quality_rank(kz.quality) for kz in sessions.active_kill_zones)
            base = max(base, best / 2)
        if sessions.overlaps:
            base = min(base + 0.1, 1.0)
        return min(base, 1.0)
