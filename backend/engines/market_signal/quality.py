"""Signal quality scoring."""

from datetime import UTC, datetime

from backend.engines.market_decision import QualityTier, TradeDecision
from backend.engines.market_signal.config import MarketSignalConfig
from backend.engines.market_signal.schemas import EXPECTED_EVIDENCE_ENGINES, NormalizedLevels


class SignalQualityScorer:
    """Weighted signal quality model separate from decision confidence."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def score(
        self,
        decision: TradeDecision,
        levels: NormalizedLevels,
        *,
        now_utc: datetime,
        near_duplicate: bool = False,
    ) -> tuple[int, QualityTier]:
        weights = self._config.quality.weights
        adjustments = self._config.quality.adjustments
        entry_scores = self._config.quality.entry_precision_scores
        target_scores = self._config.quality.target_structure_scores

        confidence_score = float(decision.confidence)
        quality_score = float(decision.quality_score)
        risk_score = self._risk_clarity(decision)
        entry_score = self._entry_precision(levels.entry_type, entry_scores)
        target_score = self._target_structure(levels.tp_count, target_scores)
        evidence_score = self._evidence_completeness(decision)
        explain_score = min(len(decision.reasons) * 20, 100)

        raw = (
            weights.decision_confidence * confidence_score
            + weights.decision_quality * quality_score
            + weights.risk_clarity * risk_score
            + weights.entry_precision * entry_score
            + weights.target_structure * target_score
            + weights.evidence_completeness * evidence_score
            + weights.explainability * explain_score
        )
        score = int(round(raw))

        if near_duplicate:
            score -= adjustments.duplicate_proximity_penalty

        score -= self._stale_penalty(decision, now_utc, adjustments.stale_decision_penalty_max)

        warning_penalty = min(
            len(decision.warnings) * adjustments.warning_penalty_per_item,
            adjustments.warning_penalty_max,
        )
        score -= warning_penalty

        if levels.tp_count >= 3:
            score += adjustments.multi_tp_bonus

        score = max(0, min(score, 100))
        tier = self._tier(score)
        return score, tier

    def meets_minimum(self, signal_quality: int) -> bool:
        minimum = self._config.quality.min_signal_quality
        return minimum <= 0 or signal_quality >= minimum

    def _tier(self, score: int) -> QualityTier:
        thresholds = self._config.quality.tiers
        if score >= thresholds.high:
            return QualityTier.HIGH
        if score >= thresholds.medium:
            return QualityTier.MEDIUM
        return QualityTier.LOW

    def _risk_clarity(self, decision: TradeDecision) -> float:
        outcomes = decision.risk_summary.rule_outcomes
        if not outcomes:
            checks = [
                decision.risk_summary.min_rr_met,
                decision.risk_summary.max_rr_met,
                decision.risk_summary.spread_acceptable,
                decision.risk_summary.stop_size_acceptable,
                decision.risk_summary.confidence_acceptable,
                decision.risk_summary.session_allowed,
            ]
            passed = sum(1 for item in checks if item)
            total = len(checks)
        else:
            passed = sum(1 for item in outcomes if item.passed)
            total = len(outcomes)
        if total == 0:
            return 0.0
        return (passed / total) * 100

    def _entry_precision(self, entry_type: str, scores) -> float:
        mapping = {
            "point": scores.point,
            "ote": scores.ote,
            "zone": scores.zone,
        }
        return float(mapping.get(entry_type, scores.zone))

    def _target_structure(self, tp_count: int, scores) -> float:
        if tp_count >= 3:
            return float(scores.three_tp)
        if tp_count == 2:
            return float(scores.two_tp)
        return float(scores.one_tp)

    def _evidence_completeness(self, decision: TradeDecision) -> float:
        available = sum(1 for item in decision.evidence_summary if item.available)
        return (available / EXPECTED_EVIDENCE_ENGINES) * 100

    def _stale_penalty(
        self,
        decision: TradeDecision,
        now_utc: datetime,
        max_penalty: int,
    ) -> int:
        if decision.valid_until_utc is None:
            return 0

        decision_ts = decision.timestamp_utc
        if decision_ts.tzinfo is None:
            decision_ts = decision_ts.replace(tzinfo=UTC)
        valid_until = decision.valid_until_utc
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=UTC)

        validity_seconds = (valid_until - decision_ts).total_seconds()
        if validity_seconds <= 0:
            return 0

        age_seconds = (now_utc - decision_ts).total_seconds()
        age_ratio = age_seconds / validity_seconds
        if age_ratio <= 0.5:
            return 0

        scaled = int(round((age_ratio - 0.5) * 2 * max_penalty))
        return min(scaled, max_penalty)
