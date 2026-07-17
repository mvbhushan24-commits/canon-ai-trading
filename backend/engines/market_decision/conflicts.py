"""Evidence conflict detection for the Market Decision Engine."""

from decimal import Decimal

from backend.engines.market_decision.config import MarketDecisionConfig
from backend.engines.market_decision.schemas import (
    ConflictReport,
    ConflictSeverity,
    DirectionBias,
    NormalizedEvidence,
    TradeDirection,
    WeightedEvidenceResult,
)


class ConflictDetector:
    """Detect directional disagreement across evidence sources."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def detect(
        self,
        weighted: WeightedEvidenceResult,
        *,
        bullish_weight: Decimal | None = None,
        bearish_weight: Decimal | None = None,
    ) -> ConflictReport:
        bull = bullish_weight if bullish_weight is not None else weighted.bullish_weight
        bear = bearish_weight if bearish_weight is not None else weighted.bearish_weight

        conflicting: list[tuple[str, str]] = []
        bullish_engines = [
            item.engine_id
            for item in weighted.normalized
            if item.available
            and not item.stale
            and item.direction_bias is DirectionBias.BULLISH
            and item.confidence > Decimal("0")
        ]
        bearish_engines = [
            item.engine_id
            for item in weighted.normalized
            if item.available
            and not item.stale
            and item.direction_bias is DirectionBias.BEARISH
            and item.confidence > Decimal("0")
        ]

        for bull_engine in bullish_engines:
            for bear_engine in bearish_engines:
                if bull_engine != bear_engine:
                    pair = (bull_engine, bear_engine)
                    if pair not in conflicting:
                        conflicting.append(pair)

        conflict_ratio = Decimal("0")
        if bull > 0 and bear > 0:
            conflict_ratio = min(bull, bear) / max(bull, bear)

        severity = self._severity(conflict_ratio)
        dominant = TradeDirection.NONE
        if bull > bear:
            dominant = TradeDirection.BUY
        elif bear > bull:
            dominant = TradeDirection.SELL

        return ConflictReport(
            bullish_weight=bull,
            bearish_weight=bear,
            conflict_ratio=conflict_ratio,
            dominant_direction=dominant,
            conflicting_engines=conflicting,
            severity=severity,
        )

    def should_reject(self, report: ConflictReport) -> bool:
        return float(report.conflict_ratio) >= self._config.conflict.reject_threshold

    def should_warn(self, report: ConflictReport) -> bool:
        return float(report.conflict_ratio) >= self._config.conflict.warn_threshold

    def _severity(self, conflict_ratio: Decimal) -> ConflictSeverity:
        ratio = float(conflict_ratio)
        if ratio >= self._config.conflict.reject_threshold:
            return ConflictSeverity.HIGH
        if ratio >= self._config.conflict.warn_threshold:
            return ConflictSeverity.MEDIUM
        if ratio > 0:
            return ConflictSeverity.LOW
        return ConflictSeverity.NONE
