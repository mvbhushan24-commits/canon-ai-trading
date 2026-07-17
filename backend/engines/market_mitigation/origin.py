"""Mitigation block origin and confluence-derived formation."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_breaker.schemas import BreakerBlock, BreakerBlockStatus
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGap, FairValueGapStatus
from backend.engines.market_mitigation.bearish import BearishMitigationDetector
from backend.engines.market_mitigation.bullish import BullishMitigationDetector
from backend.engines.market_mitigation.config import MitigationBlockConfig
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockDirection,
    MitigationBlockStatus,
    MitigationCandidate,
    MitigationSourceType,
)
from backend.engines.market_order_block.schemas import OrderBlock
from backend.engines.market_structure import MarketStructure


class OriginDetector:
    """Derive mitigation candidates from displacement and upstream zones."""

    def __init__(self, config: MitigationBlockConfig) -> None:
        self._config = config
        self._bullish = BullishMitigationDetector(config)
        self._bearish = BearishMitigationDetector(config)

    def derive_from_displacement(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
    ) -> list[MitigationCandidate]:
        """Map displacement legs to mitigation block candidates."""
        bullish = self._bullish.find_formations(candles, structure)
        bearish = self._bearish.find_formations(candles, structure)
        candidates = bullish + bearish

        if not self._config.deduplicate_by_origin:
            return candidates

        seen: set[tuple[int, str]] = set()
        deduplicated: list[MitigationCandidate] = []
        for candidate in candidates:
            key = (candidate.origin_bar_index, candidate.direction.value)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(candidate)
        return deduplicated

    def derive_from_confluence(
        self,
        candles: list[NormalizedCandle],
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gaps: list[FairValueGap] | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
    ) -> list[MitigationCandidate]:
        """Map upstream zone overlap to nested mitigation candidates."""
        if not self._config.confluence_formation_enabled:
            return []

        displacement_candidates = self.derive_from_displacement(candles)
        if not displacement_candidates:
            return []

        nested: list[MitigationCandidate] = []
        for candidate in displacement_candidates:
            parent = self._find_parent_zone(
                candidate,
                order_blocks=order_blocks,
                fair_value_gaps=fair_value_gaps,
                breaker_blocks=breaker_blocks,
                mitigation_blocks=mitigation_blocks,
            )
            if parent is None:
                continue

            parent_id, parent_type = parent
            nested.append(
                candidate.model_copy(
                    update={
                        "source_type": parent_type,
                        "parent_zone_id": parent_id,
                        "evidence": candidate.evidence
                        + [f"Nested within {parent_type.value} {parent_id}"],
                    },
                ),
            )
        return nested

    def _find_parent_zone(
        self,
        candidate: MitigationCandidate,
        *,
        order_blocks: list[OrderBlock] | None,
        fair_value_gaps: list[FairValueGap] | None,
        breaker_blocks: list[BreakerBlock] | None,
        mitigation_blocks: list[MitigationBlock] | None,
    ) -> tuple[str, MitigationSourceType] | None:
        min_containment = Decimal(str(self._config.nest_overlap_min_percent))
        best: tuple[str, MitigationSourceType, Decimal] | None = None

        for block in order_blocks or []:
            containment = self._containment_percent(candidate, block.high, block.low)
            if containment >= min_containment:
                if best is None or containment > best[2]:
                    best = (block.block_id, MitigationSourceType.ORDER_BLOCK, containment)

        for gap in fair_value_gaps or []:
            if gap.status in {FairValueGapStatus.INVALIDATED, FairValueGapStatus.EXPIRED}:
                continue
            containment = self._containment_percent(candidate, gap.high, gap.low)
            if containment >= min_containment:
                if best is None or containment > best[2]:
                    best = (gap.gap_id, MitigationSourceType.FAIR_VALUE_GAP, containment)

        for breaker in breaker_blocks or []:
            if breaker.status in {
                BreakerBlockStatus.INVALIDATED,
                BreakerBlockStatus.EXPIRED,
            }:
                continue
            containment = self._containment_percent(candidate, breaker.high, breaker.low)
            if containment >= min_containment:
                if best is None or containment > best[2]:
                    best = (
                        breaker.breaker_id,
                        MitigationSourceType.BREAKER_BLOCK,
                        containment,
                    )

        for block in mitigation_blocks or []:
            if block.status in {
                MitigationBlockStatus.INVALIDATED,
                MitigationBlockStatus.EXPIRED,
                MitigationBlockStatus.USED,
            }:
                continue
            containment = self._containment_percent(candidate, block.high, block.low)
            if containment >= min_containment:
                if best is None or containment > best[2]:
                    best = (
                        block.block_id,
                        MitigationSourceType.MITIGATION_BLOCK,
                        containment,
                    )

        if best is None:
            return None
        return best[0], best[1]

    @staticmethod
    def _containment_percent(
        candidate: MitigationCandidate,
        parent_high: Decimal,
        parent_low: Decimal,
    ) -> Decimal:
        overlap_low = max(candidate.low, parent_low)
        overlap_high = min(candidate.high, parent_high)
        if overlap_high <= overlap_low:
            return Decimal("0")

        overlap_size = overlap_high - overlap_low
        block_size = candidate.high - candidate.low
        if block_size <= 0:
            return Decimal("0")
        return (overlap_size / block_size) * Decimal("100")

    @staticmethod
    def zone_bounds(candle: NormalizedCandle, mode: str) -> tuple[Decimal, Decimal]:
        """Return zone bounds for an opposing candle."""
        if mode == "body":
            return max(candle.open, candle.close), min(candle.open, candle.close)
        return candle.high, candle.low

    @staticmethod
    def _bar_time(candles: list[NormalizedCandle], index: int) -> datetime:
        if index < 0 or index >= len(candles):
            return datetime.now(tz=UTC)
        return candles[index].close_time_utc
