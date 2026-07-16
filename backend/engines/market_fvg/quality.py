"""Fair value gap quality and multi-timeframe alignment scoring."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.config import FairValueGapConfig
from backend.engines.market_fvg.mitigation import MitigationManager
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapQuality,
    FairValueGapStatus,
    MTFGapAlignment,
    PremiumDiscountZone,
)
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_order_block import OrderBlockState
from backend.engines.market_structure import BOSDirection, CHoCHDirection, MarketStructure, TrendDirection


class MTFAlignmentScorer:
    """Score multi-timeframe fair value gap alignment."""

    def __init__(self, config: FairValueGapConfig) -> None:
        self._config = config

    def score(
        self,
        gap: FairValueGap,
        higher_timeframe_gaps: list[FairValueGap] | None,
        *,
        timeframe: str,
    ) -> MTFGapAlignment | None:
        """Return MTF alignment metadata when confluence criteria are met."""
        if not self._config.mtf_enabled or not higher_timeframe_gaps:
            return None

        best: MTFGapAlignment | None = None

        for parent in higher_timeframe_gaps:
            if parent.direction is not gap.direction:
                continue
            if parent.status not in {
                FairValueGapStatus.OPEN,
                FairValueGapStatus.PARTIAL,
            }:
                continue
            if not self._zones_overlap(gap, parent):
                continue

            overlap_ratio = self._overlap_ratio(gap, parent)
            alignment_score = min(Decimal("1"), max(Decimal("0"), overlap_ratio))
            if alignment_score < Decimal(str(self._config.min_mtf_alignment_score)):
                continue

            parent_timeframe = self._parent_timeframe(timeframe)
            aligned = []
            if parent_timeframe:
                aligned.append(parent_timeframe)
            aligned.append(timeframe.upper())

            candidate = MTFGapAlignment(
                aligned_timeframes=aligned,
                alignment_direction=gap.direction,
                alignment_score=alignment_score,
                parent_timeframe=parent_timeframe or timeframe.upper(),
                parent_gap_id=parent.gap_id,
            )
            if best is None or candidate.alignment_score > best.alignment_score:
                best = candidate

        return best

    @staticmethod
    def _zones_overlap(gap: FairValueGap, parent: FairValueGap) -> bool:
        return gap.low <= parent.high and gap.high >= parent.low

    def _parent_timeframe(self, timeframe: str) -> str | None:
        hierarchy = [item.upper() for item in self._config.mtf_timeframe_hierarchy]
        current = timeframe.upper()
        if current not in hierarchy:
            return hierarchy[0] if hierarchy else None
        index = hierarchy.index(current)
        if index == 0:
            return None
        return hierarchy[index - 1]

    @staticmethod
    def _overlap_ratio(gap: FairValueGap, parent: FairValueGap) -> Decimal:
        overlap_low = max(gap.low, parent.low)
        overlap_high = min(gap.high, parent.high)
        if overlap_high <= overlap_low:
            return Decimal("0")
        overlap_size = overlap_high - overlap_low
        if gap.gap_size <= 0:
            return Decimal("0")
        return overlap_size / gap.gap_size


class QualityScorer:
    """Compute composite strength and quality classification."""

    def __init__(self, config: FairValueGapConfig) -> None:
        self._config = config
        self._mitigation = MitigationManager(config)
        self._mtf = MTFAlignmentScorer(config)

    def score(
        self,
        gap: FairValueGap,
        *,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_block_state: OrderBlockState | None = None,
        higher_timeframe_gaps: list[FairValueGap] | None = None,
        timeframe: str,
        premium_discount: PremiumDiscountZone,
    ) -> tuple[Decimal, FairValueGapQuality, bool, bool, bool, MTFGapAlignment | None, list[str]]:
        """Return strength, quality tier, confluence flags, MTF alignment, and evidence."""
        evidence: list[str] = []
        weights = self._config.quality_weights

        impulse_score = self._impulse_score(gap, candles, evidence)
        gap_size_score = self._gap_size_score(gap, evidence)
        structure_score, structure_alignment = self._structure_score(gap, structure, evidence)
        bos_score = self._bos_score(gap, structure, evidence)
        liquidity_score, liquidity_confluence = self._liquidity_score(
            gap,
            liquidity_state,
            evidence,
        )
        order_block_score, order_block_confluence = self._order_block_score(
            gap,
            order_block_state,
            evidence,
        )
        premium_score = self._premium_discount_score(gap, premium_discount, evidence)

        mtf_alignment = self._mtf.score(
            gap,
            higher_timeframe_gaps,
            timeframe=timeframe,
        )
        mtf_score = mtf_alignment.alignment_score if mtf_alignment else Decimal("0.3")
        if mtf_alignment:
            evidence.append(
                f"MTF alignment score {mtf_alignment.alignment_score} with parent {mtf_alignment.parent_gap_id}",
            )

        strength = (
            impulse_score * Decimal(str(weights.impulse))
            + gap_size_score * Decimal(str(weights.gap_size))
            + structure_score * Decimal(str(weights.structure))
            + bos_score * Decimal(str(weights.bos))
            + liquidity_score * Decimal(str(weights.liquidity))
            + order_block_score * Decimal(str(weights.order_block))
            + premium_score * Decimal(str(weights.premium_discount))
            + mtf_score * Decimal(str(weights.mtf))
        )
        strength = min(Decimal("1"), max(Decimal("0"), strength))
        quality = self._quality_tier(strength)

        return (
            strength,
            quality,
            structure_alignment,
            liquidity_confluence,
            order_block_confluence,
            mtf_alignment,
            evidence,
        )

    def passes_minimum(self, strength: Decimal) -> bool:
        return strength >= Decimal(str(self._config.min_quality_score))

    def has_counter_trend_choch(
        self,
        gap: FairValueGap,
        structure: MarketStructure,
    ) -> bool:
        for event in structure.choch_events:
            if event.bar_index < gap.origin_bar_index:
                continue
            if gap.direction is FairValueGapDirection.BULLISH:
                if event.direction is CHoCHDirection.BULLISH:
                    return True
            elif event.direction is CHoCHDirection.BEARISH:
                return True
        return False

    def _impulse_score(
        self,
        gap: FairValueGap,
        candles: list[NormalizedCandle],
        evidence: list[str],
    ) -> Decimal:
        if gap.candle_b_index < 0 or gap.candle_b_index >= len(candles):
            return Decimal("0.3")

        candle = candles[gap.candle_b_index]
        candle_range = candle.high - candle.low
        if candle_range <= 0:
            evidence.append("Impulse candle has zero range")
            return Decimal("0")

        body = abs(candle.close - candle.open)
        ratio = body / candle_range
        minimum = Decimal(str(self._config.min_impulse_body_ratio))
        if ratio >= minimum:
            evidence.append(f"Impulse body ratio {ratio:.2f} meets threshold")
            return min(Decimal("1"), ratio / max(minimum, Decimal("0.01")))

        evidence.append(f"Impulse body ratio {ratio:.2f} below threshold")
        return max(Decimal("0"), ratio / max(minimum, Decimal("0.01")))

    def _gap_size_score(self, gap: FairValueGap, evidence: list[str]) -> Decimal:
        minimum = Decimal(str(self._config.min_gap_size_pips))
        if minimum <= 0:
            return Decimal("0")
        ratio = gap.gap_size_pips / minimum
        score = min(Decimal("1"), ratio / Decimal("3"))
        evidence.append(f"Gap size {gap.gap_size_pips} pips scored {score:.2f}")
        return score

    def _structure_score(
        self,
        gap: FairValueGap,
        structure: MarketStructure | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool]:
        if structure is None:
            evidence.append("Structure context unavailable")
            return Decimal("0.3"), False

        trend = structure.current_trend
        aligned = (
            gap.direction is FairValueGapDirection.BULLISH
            and trend is TrendDirection.BULLISH
        ) or (
            gap.direction is FairValueGapDirection.BEARISH
            and trend is TrendDirection.BEARISH
        )

        if aligned:
            evidence.append(f"Aligned with {trend.value} structure trend")
            return Decimal("1"), True

        if self.has_counter_trend_choch(gap, structure):
            evidence.append("Counter-trend gap supported by CHoCH")
            return Decimal("0.7"), False

        if trend is TrendDirection.RANGE:
            evidence.append("Structure in range — neutral alignment")
            return Decimal("0.5"), False

        evidence.append(f"Counter to {trend.value} structure trend")
        return Decimal("0.2"), False

    def _bos_score(
        self,
        gap: FairValueGap,
        structure: MarketStructure | None,
        evidence: list[str],
    ) -> Decimal:
        if structure is None:
            return Decimal("0.3")

        for event in structure.bos_events:
            if event.bar_index < gap.origin_bar_index:
                continue
            if gap.direction is FairValueGapDirection.BULLISH:
                if event.direction is BOSDirection.BULLISH:
                    evidence.append("Recent bullish BOS confirms gap direction")
                    return Decimal("1")
            elif event.direction is BOSDirection.BEARISH:
                evidence.append("Recent bearish BOS confirms gap direction")
                return Decimal("1")

        evidence.append("No confirming BOS near gap formation")
        return Decimal("0.3")

    def _liquidity_score(
        self,
        gap: FairValueGap,
        liquidity_state: LiquidityState | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool]:
        if not self._config.use_liquidity_confluence or liquidity_state is None:
            if liquidity_state is None:
                evidence.append("Liquidity state unavailable")
            return Decimal("0.3"), False

        tolerance = Decimal(str(self._config.pip_size * 5))
        for zone in liquidity_state.active_zones:
            if zone.lower_bound <= gap.high and zone.upper_bound >= gap.low:
                evidence.append("Gap overlaps active liquidity zone")
                return Decimal("1"), True

        for sweep in liquidity_state.recent_sweeps:
            if abs(sweep.swept_level - gap.high) <= tolerance:
                evidence.append("Recent liquidity sweep near gap boundary")
                return Decimal("0.9"), True
            if abs(sweep.swept_level - gap.low) <= tolerance:
                evidence.append("Recent liquidity sweep near gap boundary")
                return Decimal("0.9"), True

        return Decimal("0.4"), False

    def _order_block_score(
        self,
        gap: FairValueGap,
        order_block_state: OrderBlockState | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool]:
        if not self._config.use_order_block_confluence or order_block_state is None:
            if order_block_state is None:
                evidence.append("Order block state unavailable")
            return Decimal("0.3"), False

        for block in order_block_state.active_blocks:
            if block.low <= gap.high and block.high >= gap.low:
                evidence.append("Gap overlaps active order block zone")
                return Decimal("1"), True

        return Decimal("0.4"), False

    def _premium_discount_score(
        self,
        gap: FairValueGap,
        zone: PremiumDiscountZone,
        evidence: list[str],
    ) -> Decimal:
        score = MitigationManager.premium_discount_alignment_score(gap, zone)
        evidence.append(f"Premium/discount placement scored {score:.2f}")
        return score

    @staticmethod
    def _quality_tier(strength: Decimal) -> FairValueGapQuality:
        if strength >= Decimal("0.7"):
            return FairValueGapQuality.HIGH
        if strength >= Decimal("0.4"):
            return FairValueGapQuality.MEDIUM
        return FairValueGapQuality.LOW
