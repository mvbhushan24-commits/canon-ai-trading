"""Mitigation block quality, confluence, nesting, and MTF scoring."""

from decimal import Decimal

from backend.engines.market_breaker.schemas import BreakerBlock, BreakerBlockStatus
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapState,
    FairValueGapStatus,
    PremiumDiscountZone,
)
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_liquidity.schemas import SweepDirection
from backend.engines.market_mitigation.config import MitigationBlockConfig
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockDirection,
    MitigationBlockQuality,
    MitigationBlockStatus,
    MitigationSourceType,
    MTFMitigationAlignment,
    StructureScope,
)
from backend.engines.market_order_block.schemas import OrderBlock
from backend.engines.market_structure import CHoCHDirection, MarketStructure, SwingPoint, TrendDirection


class QualityScorer:
    """Compute composite strength, confluence, nesting, and quality classification."""

    def __init__(self, config: MitigationBlockConfig) -> None:
        self._config = config

    def score(
        self,
        block: MitigationBlock,
        *,
        candles_count: int,
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        htf_mitigation_blocks: list[MitigationBlock] | None = None,
        ltf_mitigation_blocks: list[MitigationBlock] | None = None,
        displacement_magnitude: Decimal | None = None,
    ) -> MitigationBlock:
        """Return enriched block with strength, quality, and confluence fields."""
        evidence = list(block.evidence)
        weights = self._config.quality_weights

        displacement_score = self._displacement_score(
            block,
            displacement_magnitude,
            evidence,
        )
        structure_score, structure_alignment = self._structure_score(
            block,
            structure,
            evidence,
        )
        scope, scope_score, scope_evidence = self.classify_structure_scope(block, structure)
        evidence.extend(scope_evidence)

        liquidity_score, liquidity_confluence, liquidity_ids = self._liquidity_score(
            block,
            liquidity_state,
            evidence,
        )
        ob_score, ob_confluence, ob_ids = self._order_block_score(
            block,
            order_blocks,
            evidence,
        )
        fvg_score, fvg_confluence, fvg_ids = self._fvg_score(
            block,
            fair_value_gap_state,
            evidence,
        )
        breaker_score, breaker_confluence, breaker_ids = self._breaker_score(
            block,
            breaker_blocks,
            evidence,
        )

        htf_score, htf_aligned, htf_ids = self._htf_score(
            block,
            htf_mitigation_blocks,
            evidence,
        )
        ltf_ids = self.detect_ltf_nesting(block, ltf_mitigation_blocks)
        ltf_nested = bool(ltf_ids)
        if ltf_nested:
            evidence.append(f"LTF nesting: {len(ltf_ids)} blocks within zone")

        confirmation_score = self._confirmation_score(block, evidence)
        freshness_score = self._freshness_score(block, candles_count, evidence)

        strength = (
            displacement_score * Decimal(str(weights.displacement))
            + structure_score * Decimal(str(weights.structure))
            + scope_score * Decimal(str(weights.structure_scope))
            + liquidity_score * Decimal(str(weights.liquidity))
            + ob_score * Decimal(str(weights.order_block))
            + fvg_score * Decimal(str(weights.fvg))
            + breaker_score * Decimal(str(weights.breaker))
            + htf_score * Decimal(str(weights.htf_alignment))
            + confirmation_score * Decimal(str(weights.confirmation))
            + freshness_score * Decimal(str(weights.freshness))
        )
        strength = min(Decimal("1"), max(Decimal("0"), strength))
        quality = self._quality_tier(strength)

        premium_zone, range_high, range_low, premium_evidence = (
            self.classify_premium_discount(block, structure)
        )
        evidence.extend(premium_evidence)

        nested_block, nest_evidence = self.classify_nesting(
            block,
            order_blocks=order_blocks,
            fair_value_gaps=(
                fair_value_gap_state.active_gaps if fair_value_gap_state else None
            ),
            breaker_blocks=breaker_blocks,
            mitigation_blocks=htf_mitigation_blocks,
        )
        evidence.extend(nest_evidence)

        confluence_ids = sorted(
            set(liquidity_ids + ob_ids + fvg_ids + breaker_ids + htf_ids + ltf_ids),
        )

        updates = {
            "quality": quality,
            "strength": strength,
            "structure_scope": scope,
            "structure_alignment": structure_alignment,
            "liquidity_confluence": liquidity_confluence,
            "order_block_confluence": ob_confluence,
            "fvg_confluence": fvg_confluence,
            "breaker_confluence": breaker_confluence,
            "htf_aligned": htf_aligned,
            "htf_block_ids": htf_ids,
            "ltf_nested": ltf_nested,
            "ltf_block_ids": ltf_ids,
            "confluence_ids": confluence_ids,
            "premium_discount": premium_zone,
            "dealing_range_high": range_high,
            "dealing_range_low": range_low,
            "evidence": evidence,
        }
        if nested_block.is_nested:
            updates.update(
                {
                    "is_nested": nested_block.is_nested,
                    "parent_zone_id": nested_block.parent_zone_id,
                    "parent_zone_type": nested_block.parent_zone_type,
                },
            )

        if not block.is_confirmed and block.status not in {
            MitigationBlockStatus.CONFIRMED,
            MitigationBlockStatus.USED,
        }:
            cap = Decimal("0.75")
            updates["strength"] = min(strength, cap)
            updates["quality"] = self._quality_tier(updates["strength"])

        return block.model_copy(update=updates)

    def score_confluence(
        self,
        block: MitigationBlock,
        liquidity_state: LiquidityState | None,
        order_blocks: list[OrderBlock] | None,
        fair_value_gap_state: FairValueGapState | None,
        breaker_blocks: list[BreakerBlock] | None,
    ) -> MitigationBlock:
        """Enrich block with upstream confluence fields."""
        return self.score(
            block,
            candles_count=0,
            liquidity_state=liquidity_state,
            order_blocks=order_blocks,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
        )

    def classify_structure_scope(
        self,
        block: MitigationBlock,
        structure: MarketStructure | None,
    ) -> tuple[StructureScope, Decimal, list[str]]:
        """Classify internal or external structure placement."""
        evidence: list[str] = []
        if structure is None:
            evidence.append("Structure context unavailable for scope")
            return StructureScope.UNDETERMINED, Decimal("0.3"), evidence

        mode = self._config.structure_scope_mode
        midpoint = (block.high + block.low) / Decimal("2")
        internal_match = self._in_structure_range(
            midpoint,
            structure,
            internal=True,
        )
        external_match = self._in_structure_range(
            midpoint,
            structure,
            internal=False,
        )

        if mode == "internal":
            if internal_match:
                evidence.append("Block within internal structure range")
                return StructureScope.INTERNAL, Decimal("1"), evidence
            return StructureScope.UNDETERMINED, Decimal("0.3"), evidence

        if mode == "external":
            if external_match:
                evidence.append("Block within external structure range")
                return StructureScope.EXTERNAL, Decimal("1"), evidence
            return StructureScope.UNDETERMINED, Decimal("0.3"), evidence

        if external_match:
            evidence.append("Block within external structure range")
            return StructureScope.EXTERNAL, Decimal("1"), evidence
        if internal_match:
            evidence.append("Block within internal structure range")
            return StructureScope.INTERNAL, Decimal("0.8"), evidence

        evidence.append("Block outside classified structure ranges")
        return StructureScope.UNDETERMINED, Decimal("0.3"), evidence

    def classify_nesting(
        self,
        block: MitigationBlock,
        *,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gaps: list[FairValueGap] | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
    ) -> tuple[MitigationBlock, list[str]]:
        """Detect parent-child nesting relationships."""
        evidence: list[str] = []
        if block.is_nested and block.parent_zone_id:
            return block, evidence

        min_containment = Decimal(str(self._config.nest_overlap_min_percent))
        best: tuple[str, MitigationSourceType, Decimal] | None = None

        for ob in order_blocks or []:
            containment = self._containment_percent(block, ob.high, ob.low)
            if containment >= min_containment and (best is None or containment > best[2]):
                best = (ob.block_id, MitigationSourceType.ORDER_BLOCK, containment)

        for gap in fair_value_gaps or []:
            if gap.status in {FairValueGapStatus.INVALIDATED, FairValueGapStatus.EXPIRED}:
                continue
            containment = self._containment_percent(block, gap.high, gap.low)
            if containment >= min_containment and (best is None or containment > best[2]):
                best = (gap.gap_id, MitigationSourceType.FAIR_VALUE_GAP, containment)

        for breaker in breaker_blocks or []:
            if breaker.status in {BreakerBlockStatus.INVALIDATED, BreakerBlockStatus.EXPIRED}:
                continue
            containment = self._containment_percent(block, breaker.high, breaker.low)
            if containment >= min_containment and (best is None or containment > best[2]):
                best = (breaker.breaker_id, MitigationSourceType.BREAKER_BLOCK, containment)

        for parent in mitigation_blocks or []:
            if parent.block_id == block.block_id:
                continue
            containment = self._containment_percent(block, parent.high, parent.low)
            if containment >= min_containment and (best is None or containment > best[2]):
                best = (
                    parent.block_id,
                    MitigationSourceType.MITIGATION_BLOCK,
                    containment,
                )

        if best is None:
            return block, evidence

        evidence.append(
            f"Nested within {best[1].value} {best[0]} ({best[2]:.1f}% containment)",
        )
        return block.model_copy(
            update={
                "is_nested": True,
                "parent_zone_id": best[0],
                "parent_zone_type": best[1],
            },
        ), evidence

    def score_htf_alignment(
        self,
        block: MitigationBlock,
        htf_blocks: list[MitigationBlock] | None,
    ) -> MTFMitigationAlignment | None:
        """Score overlap with higher-timeframe mitigation blocks."""
        if not htf_blocks:
            return None

        min_overlap = Decimal(str(self._config.htf_overlap_min_percent))
        best_score = Decimal("0")
        best_id = ""
        best_timeframe = ""

        for htf in htf_blocks:
            if htf.direction is not block.direction:
                continue
            if htf.status in {
                MitigationBlockStatus.INVALIDATED,
                MitigationBlockStatus.EXPIRED,
                MitigationBlockStatus.USED,
            }:
                continue

            overlap = self._overlap_percent(block, htf.high, htf.low)
            if overlap >= min_overlap and overlap > best_score:
                best_score = overlap / Decimal("100")
                best_id = htf.block_id
                best_timeframe = "HTF"

        if not best_id:
            return None

        return MTFMitigationAlignment(
            aligned_timeframes=[best_timeframe],
            alignment_direction=block.direction,
            alignment_score=min(Decimal("1"), best_score),
            parent_timeframe=best_timeframe,
            parent_block_id=best_id,
        )

    def detect_ltf_nesting(
        self,
        block: MitigationBlock,
        ltf_blocks: list[MitigationBlock] | None,
    ) -> list[str]:
        """Detect lower-timeframe blocks nested within current zone."""
        if not self._config.ltf_nesting_enabled or not ltf_blocks:
            return []

        matched: list[str] = []
        for ltf in ltf_blocks:
            if ltf.block_id == block.block_id:
                continue
            if ltf.status not in {
                MitigationBlockStatus.FRESH,
                MitigationBlockStatus.PARTIAL,
                MitigationBlockStatus.CONFIRMED,
            }:
                continue
            containment = self._containment_percent(ltf, block.high, block.low)
            if containment >= Decimal(str(self._config.nest_overlap_min_percent)):
                matched.append(ltf.block_id)
        return sorted(set(matched))

    def classify_premium_discount(
        self,
        block: MitigationBlock,
        structure: MarketStructure | None,
    ) -> tuple[PremiumDiscountZone, Decimal | None, Decimal | None, list[str]]:
        """Classify block placement relative to structure dealing range."""
        evidence: list[str] = []
        if structure is None:
            evidence.append("Dealing range unavailable")
            return PremiumDiscountZone.EQUILIBRIUM, None, None, evidence

        range_high, range_low = self._dealing_range(structure)
        if range_high is None or range_low is None:
            evidence.append("Dealing range unavailable")
            return PremiumDiscountZone.EQUILIBRIUM, None, None, evidence

        midpoint = (block.high + block.low) / Decimal("2")
        equilibrium = (range_high + range_low) / Decimal("2")
        tolerance = Decimal(str(self._config.equilibrium_tolerance_price))

        if midpoint > equilibrium + tolerance:
            evidence.append("Block midpoint above equilibrium — premium")
            return PremiumDiscountZone.PREMIUM, range_high, range_low, evidence

        if midpoint < equilibrium - tolerance:
            evidence.append("Block midpoint below equilibrium — discount")
            return PremiumDiscountZone.DISCOUNT, range_high, range_low, evidence

        evidence.append("Block midpoint near equilibrium")
        return PremiumDiscountZone.EQUILIBRIUM, range_high, range_low, evidence

    def passes_minimum(self, strength: Decimal) -> bool:
        return strength >= Decimal(str(self._config.min_quality_score))

    def has_counter_trend_choch(
        self,
        block: MitigationBlock,
        structure: MarketStructure,
    ) -> bool:
        for event in structure.choch_events:
            if event.bar_index < block.formation_bar_index:
                continue
            if block.direction is MitigationBlockDirection.BULLISH:
                if event.direction is CHoCHDirection.BULLISH:
                    return True
            elif event.direction is CHoCHDirection.BEARISH:
                return True
        return False

    def _displacement_score(
        self,
        block: MitigationBlock,
        magnitude: Decimal | None,
        evidence: list[str],
    ) -> Decimal:
        if magnitude is None or magnitude <= 0:
            for item in block.evidence:
                if "Displacement magnitude" in item:
                    try:
                        magnitude = Decimal(item.split()[-1])
                    except (IndexError, ValueError):
                        magnitude = Decimal("0")
                    break
            else:
                magnitude = Decimal("0")

        minimum = self._config.min_displacement_price
        if minimum <= 0 or magnitude <= 0:
            evidence.append("Displacement strength minimal")
            return Decimal("0.3")

        ratio = magnitude / minimum
        score = min(Decimal("1"), max(Decimal("0"), ratio / Decimal("2")))
        evidence.append(f"Displacement strength scored {score:.2f}")
        return score

    def _structure_score(
        self,
        block: MitigationBlock,
        structure: MarketStructure | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool]:
        if structure is None:
            evidence.append("Structure context unavailable")
            return Decimal("0.3"), False

        trend = structure.current_trend
        aligned = (
            block.direction is MitigationBlockDirection.BULLISH
            and trend is TrendDirection.BULLISH
        ) or (
            block.direction is MitigationBlockDirection.BEARISH
            and trend is TrendDirection.BEARISH
        )

        if aligned:
            evidence.append(f"Aligned with {trend.value} structure trend")
            return Decimal("1"), True

        if self.has_counter_trend_choch(block, structure):
            evidence.append("Counter-trend block supported by CHoCH")
            return Decimal("0.7"), False

        if trend is TrendDirection.RANGE:
            evidence.append("Structure in range — neutral alignment")
            return Decimal("0.5"), False

        evidence.append(f"Counter to {trend.value} structure trend")
        return Decimal("0.2"), False

    def _liquidity_score(
        self,
        block: MitigationBlock,
        liquidity_state: LiquidityState | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool, list[str]]:
        if not self._config.use_liquidity_confluence or liquidity_state is None:
            if liquidity_state is None:
                evidence.append("Liquidity state unavailable")
            return Decimal("0.3"), False, []

        matched_ids: list[str] = []
        proximity = self._config.liquidity_proximity_price

        for zone in liquidity_state.active_zones:
            if zone.lower_bound <= block.high and zone.upper_bound >= block.low:
                matched_ids.append(zone.zone_id)
                evidence.append(f"Overlaps liquidity zone {zone.zone_id}")

        for sweep in liquidity_state.recent_sweeps:
            sweep_id = f"liq-sweep-{sweep.swept_level}-{sweep.bar_index}"
            midpoint = (block.high + block.low) / Decimal("2")
            if abs(sweep.swept_level - midpoint) <= proximity:
                matched_ids.append(sweep_id)
                evidence.append("Near recent liquidity sweep")

        if matched_ids:
            return Decimal("1"), True, sorted(set(matched_ids))
        return Decimal("0.4"), False, []

    def _order_block_score(
        self,
        block: MitigationBlock,
        order_blocks: list[OrderBlock] | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool, list[str]]:
        if not self._config.use_order_block_confluence or not order_blocks:
            return Decimal("0.3"), False, []

        min_overlap = Decimal(str(self._config.ob_overlap_min_percent))
        matched: list[str] = []
        for ob in order_blocks:
            overlap = self._overlap_percent(block, ob.high, ob.low)
            if overlap >= min_overlap:
                matched.append(ob.block_id)
                evidence.append(f"Order block confluence {ob.block_id} ({overlap:.1f}%)")

        if matched:
            return Decimal("1"), True, sorted(set(matched))
        return Decimal("0.4"), False, []

    def _fvg_score(
        self,
        block: MitigationBlock,
        fair_value_gap_state: FairValueGapState | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool, list[str]]:
        if not self._config.use_fvg_confluence or fair_value_gap_state is None:
            if fair_value_gap_state is None:
                evidence.append("FVG state unavailable")
            return Decimal("0.3"), False, []

        matched: list[str] = []
        ce_proximity = self._config.fvg_ce_proximity_price
        min_overlap = Decimal(str(self._config.fvg_overlap_min_percent))
        midpoint = (block.high + block.low) / Decimal("2")

        for gap in fair_value_gap_state.active_gaps:
            if gap.status not in {FairValueGapStatus.OPEN, FairValueGapStatus.PARTIAL}:
                continue
            overlap = self._overlap_percent(block, gap.high, gap.low)
            ce_near = abs(gap.ce_price - midpoint) <= ce_proximity
            direction_aligned = (
                block.direction is MitigationBlockDirection.BULLISH
                and gap.direction is FairValueGapDirection.BULLISH
            ) or (
                block.direction is MitigationBlockDirection.BEARISH
                and gap.direction is FairValueGapDirection.BEARISH
            )
            if overlap >= min_overlap or (ce_near and direction_aligned):
                matched.append(gap.gap_id)
                evidence.append(f"FVG confluence {gap.gap_id}")

        if matched:
            return Decimal("1"), True, sorted(set(matched))
        return Decimal("0.4"), False, []

    def _breaker_score(
        self,
        block: MitigationBlock,
        breaker_blocks: list[BreakerBlock] | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool, list[str]]:
        if not self._config.use_breaker_confluence or not breaker_blocks:
            return Decimal("0.3"), False, []

        min_overlap = Decimal(str(self._config.breaker_overlap_min_percent))
        matched: list[str] = []
        for breaker in breaker_blocks:
            if breaker.status not in {
                BreakerBlockStatus.CANDIDATE,
                BreakerBlockStatus.CONFIRMED,
                BreakerBlockStatus.MITIGATED,
            }:
                continue
            overlap = self._overlap_percent(block, breaker.high, breaker.low)
            if overlap >= min_overlap:
                matched.append(breaker.breaker_id)
                evidence.append(f"Breaker confluence {breaker.breaker_id}")

        if matched:
            return Decimal("1"), True, sorted(set(matched))
        return Decimal("0.4"), False, []

    def _htf_score(
        self,
        block: MitigationBlock,
        htf_blocks: list[MitigationBlock] | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool, list[str]]:
        alignment = self.score_htf_alignment(block, htf_blocks)
        if alignment is None:
            return Decimal("0.3"), False, []

        evidence.append(
            f"HTF aligned with {alignment.parent_block_id} "
            f"(score {alignment.alignment_score:.2f})",
        )
        return alignment.alignment_score, True, [alignment.parent_block_id]

    def _confirmation_score(
        self,
        block: MitigationBlock,
        evidence: list[str],
    ) -> Decimal:
        if block.is_confirmed or block.status in {
            MitigationBlockStatus.CONFIRMED,
            MitigationBlockStatus.USED,
        }:
            evidence.append("Mitigation confirmed — full confirmation score")
            return Decimal("1")
        if block.status is MitigationBlockStatus.PARTIAL:
            evidence.append("Partial mitigation — reduced confirmation score")
            return Decimal("0.5")
        if block.status is MitigationBlockStatus.FRESH:
            evidence.append("Fresh block — no confirmation score")
            return Decimal("0.2")
        return Decimal("0.1")

    def _freshness_score(
        self,
        block: MitigationBlock,
        bar_count: int,
        evidence: list[str],
    ) -> Decimal:
        if block.status in {
            MitigationBlockStatus.INVALIDATED,
            MitigationBlockStatus.EXPIRED,
            MitigationBlockStatus.USED,
        }:
            return Decimal("0")

        age = bar_count - block.formation_bar_index
        max_age = self._config.max_block_age_bars
        if age <= 0:
            evidence.append("Freshly formed block")
            return Decimal("1")
        if age >= max_age:
            return Decimal("0.1")

        ratio = Decimal(str(age)) / Decimal(str(max_age))
        score = max(Decimal("0.2"), Decimal("1") - ratio)
        evidence.append(f"Freshness scored {score:.2f} ({age} bars since formation)")
        return score

    def _in_structure_range(
        self,
        midpoint: Decimal,
        structure: MarketStructure,
        *,
        internal: bool,
    ) -> bool:
        state = (
            structure.internal_structure if internal else structure.external_structure
        )
        range_high = self._latest_swing_price(
            structure.swing_highs,
            fallback=state.last_swing_high,
        )
        range_low = self._latest_swing_price(
            structure.swing_lows,
            fallback=state.last_swing_low,
        )
        if range_high is None or range_low is None:
            return False
        return range_low <= midpoint <= range_high

    def _dealing_range(
        self,
        structure: MarketStructure,
    ) -> tuple[Decimal | None, Decimal | None]:
        state = (
            structure.external_structure
            if self._config.dealing_range_mode == "external"
            else structure.internal_structure
        )
        range_high = self._latest_swing_price(
            structure.swing_highs,
            fallback=state.last_swing_high,
        )
        range_low = self._latest_swing_price(
            structure.swing_lows,
            fallback=state.last_swing_low,
        )
        return range_high, range_low

    @staticmethod
    def _latest_swing_price(
        swings: list[SwingPoint],
        *,
        fallback: SwingPoint | None,
    ) -> Decimal | None:
        if swings:
            return swings[-1].price
        if fallback is not None:
            return fallback.price
        return None

    @staticmethod
    def _overlap_percent(
        block: MitigationBlock,
        zone_high: Decimal,
        zone_low: Decimal,
    ) -> Decimal:
        overlap_low = max(block.low, zone_low)
        overlap_high = min(block.high, zone_high)
        if overlap_high <= overlap_low:
            return Decimal("0")

        overlap_size = overlap_high - overlap_low
        block_size = block.high - block.low
        zone_size = zone_high - zone_low
        denominator = min(block_size, zone_size)
        if denominator <= 0:
            return Decimal("0")
        return (overlap_size / denominator) * Decimal("100")

    @staticmethod
    def _containment_percent(
        inner: MitigationBlock,
        outer_high: Decimal,
        outer_low: Decimal,
    ) -> Decimal:
        overlap_low = max(inner.low, outer_low)
        overlap_high = min(inner.high, outer_high)
        if overlap_high <= overlap_low:
            return Decimal("0")

        overlap_size = overlap_high - overlap_low
        inner_size = inner.high - inner.low
        if inner_size <= 0:
            return Decimal("0")
        return (overlap_size / inner_size) * Decimal("100")

    @staticmethod
    def _quality_tier(strength: Decimal) -> MitigationBlockQuality:
        if strength >= Decimal("0.7"):
            return MitigationBlockQuality.HIGH
        if strength >= Decimal("0.4"):
            return MitigationBlockQuality.MEDIUM
        return MitigationBlockQuality.LOW
