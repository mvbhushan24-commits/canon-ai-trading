"""Evidence weighting and confidence scoring."""

from decimal import Decimal

from backend.engines.market_decision.config import MarketDecisionConfig
from backend.engines.market_decision.schemas import (
    ConflictReport,
    ConflictSeverity,
    DirectionBias,
    EvidenceSummaryItem,
    NormalizedEvidence,
    WeightedEvidenceResult,
)


class EvidenceWeighter:
    """Apply configurable per-engine weights to normalized evidence."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config
        self._weight_map = {
            "market_structure": Decimal(str(config.weights.market_structure)),
            "market_liquidity": Decimal(str(config.weights.market_liquidity)),
            "order_block": Decimal(str(config.weights.order_block)),
            "fair_value_gap": Decimal(str(config.weights.fair_value_gap)),
            "market_breaker": Decimal(str(config.weights.market_breaker)),
            "market_mitigation": Decimal(str(config.weights.market_mitigation)),
            "market_premium_discount": Decimal(str(config.weights.market_premium_discount)),
            "market_sessions": Decimal(str(config.weights.market_sessions)),
        }

    def weight(self, normalized: list[NormalizedEvidence]) -> WeightedEvidenceResult:
        summary: list[EvidenceSummaryItem] = []
        bullish_weight = Decimal("0")
        bearish_weight = Decimal("0")
        warnings: list[str] = []
        stale_factor = Decimal(str(self._config.evidence.stale_weight_factor))

        for item in normalized:
            base_weight = self._weight_map.get(item.engine_id, Decimal("0"))
            if not item.available:
                summary.append(
                    EvidenceSummaryItem(
                        engine_id=item.engine_id,
                        available=False,
                        stale=item.stale,
                        direction_bias=item.direction_bias.value,
                        confidence=item.confidence,
                        weight=base_weight,
                        weighted_contribution=Decimal("0"),
                        quality_tier=item.quality_tier,
                        key_evidence=item.evidence[:3],
                    ),
                )
                continue

            availability_factor = Decimal("1")
            if item.stale:
                availability_factor = stale_factor
                warnings.append(f"{item.engine_id} evidence stale — weight reduced")

            contribution = (
                base_weight * item.confidence * item.strength * availability_factor
            )
            summary.append(
                EvidenceSummaryItem(
                    engine_id=item.engine_id,
                    available=True,
                    stale=item.stale,
                    direction_bias=item.direction_bias.value,
                    confidence=item.confidence,
                    weight=base_weight,
                    weighted_contribution=contribution.quantize(Decimal("0.001")),
                    quality_tier=item.quality_tier,
                    key_evidence=item.evidence[:3],
                ),
            )

            if item.direction_bias is DirectionBias.BULLISH:
                bullish_weight += contribution
            elif item.direction_bias is DirectionBias.BEARISH:
                bearish_weight += contribution

        confidence = ConfidenceScorer(self._config).score_from_contributions(
            summary,
            bullish_weight=bullish_weight,
            bearish_weight=bearish_weight,
        )

        return WeightedEvidenceResult(
            normalized=normalized,
            summary=summary,
            bullish_weight=bullish_weight,
            bearish_weight=bearish_weight,
            confidence=confidence,
            warnings=warnings,
        )


class ConfidenceScorer:
    """Aggregate weighted evidence into 0–100 confidence."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def score(
        self,
        weighted: WeightedEvidenceResult,
        conflict: ConflictReport,
        *,
        zone_confluence_count: int = 0,
        stale_engine_count: int = 0,
    ) -> int:
        base = self.score_from_contributions(
            weighted.summary,
            bullish_weight=weighted.bullish_weight,
            bearish_weight=weighted.bearish_weight,
        )
        penalty = self._conflict_penalty(conflict.severity)
        stale_penalty = stale_engine_count * self._config.confidence.stale_penalty_per_engine
        confluence_bonus = min(
            zone_confluence_count * self._config.confidence.confluence_bonus_per_zone,
            self._config.confidence.max_confluence_bonus,
        )
        final = base - penalty - stale_penalty + confluence_bonus
        return max(0, min(100, final))

    def score_from_contributions(
        self,
        summary: list[EvidenceSummaryItem],
        *,
        bullish_weight: Decimal,
        bearish_weight: Decimal,
    ) -> int:
        active_weights = sum(
            item.weight for item in summary if item.available and item.weighted_contribution > 0
        )
        if active_weights <= 0:
            return 0

        total_contribution = sum(item.weighted_contribution for item in summary if item.available)
        raw = (total_contribution / active_weights) * Decimal("100")
        directional_total = bullish_weight + bearish_weight
        if directional_total > 0:
            dominance = max(bullish_weight, bearish_weight) / directional_total
            raw *= dominance
        return int(raw.quantize(Decimal("1")))

    def meets_minimum(self, confidence: int) -> bool:
        return confidence >= self._config.confidence.min_confidence

    def _conflict_penalty(self, severity: ConflictSeverity) -> int:
        penalties = self._config.confidence.conflict_penalty
        mapping = {
            ConflictSeverity.NONE: penalties.none,
            ConflictSeverity.LOW: penalties.low,
            ConflictSeverity.MEDIUM: penalties.medium,
            ConflictSeverity.HIGH: penalties.high,
        }
        return mapping.get(severity, 0)
