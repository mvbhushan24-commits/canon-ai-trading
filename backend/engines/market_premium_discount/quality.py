"""Premium / discount quality scoring and confluence analysis."""

from decimal import Decimal
from uuid import uuid4

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_mitigation.schemas import MitigationBlock
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_premium_discount.config import PremiumDiscountConfig
from backend.engines.market_premium_discount.lifecycle import LifecycleManager
from backend.engines.market_premium_discount.schemas import (
    ArrayZoneEntry,
    DealingRange,
    FibDirection,
    HTFPricingContext,
    InstitutionalArray,
    InstitutionalZoneType,
    MTFPremiumDiscountAlignment,
    NestedZoneContext,
    PremiumDiscountBias,
    PremiumDiscountContext,
    PremiumDiscountQuality,
    PremiumDiscountZone,
)
from backend.engines.market_structure import MarketStructure, TrendDirection


class QualityScorer:
    """Compute composite strength, quality tier, and alignment scores."""

    def __init__(self, config: PremiumDiscountConfig) -> None:
        self._config = config
        self._lifecycle = LifecycleManager(config)

    def score_range(
        self,
        dealing_range: DealingRange,
        structure: MarketStructure | None,
    ) -> DealingRange:
        """Score dealing range strength and quality tier."""
        if not dealing_range.is_valid:
            return dealing_range

        swing_score = (dealing_range.swing_high.quality_score + dealing_range.swing_low.quality_score) / Decimal("2")
        structure_score = structure.confidence if structure is not None else Decimal("0.3")
        strength = swing_score * Decimal("0.6") + structure_score * Decimal("0.4")
        strength = min(Decimal("1"), max(Decimal("0"), strength))
        quality = self._quality_tier(strength)
        return dealing_range.model_copy(update={"strength": strength, "quality": quality})

    def score_analysis(
        self,
        *,
        dealing_range: DealingRange,
        structure: MarketStructure | None,
        price_location: PremiumDiscountZone,
        current_price: Decimal,
        liquidity_state: LiquidityState | None,
        zone_entries: list[ArrayZoneEntry],
        htf_context: PremiumDiscountContext | None,
        mtf_premium: MTFPremiumDiscountAlignment | None,
        mtf_discount: MTFPremiumDiscountAlignment | None,
        bar_count: int,
    ) -> tuple[Decimal, PremiumDiscountQuality, PremiumDiscountBias, Decimal]:
        """Return strength, quality tier, bias, and confidence."""
        weights = self._config.quality_weights

        swing_score = (
            dealing_range.swing_high.quality_score + dealing_range.swing_low.quality_score
        ) / Decimal("2")
        structure_score = structure.confidence if structure is not None else Decimal("0")
        liquidity_score = self._liquidity_score(dealing_range, liquidity_state)
        htf_score = self._htf_score(mtf_premium, mtf_discount)
        fvg_score = self._alignment_score(zone_entries, InstitutionalZoneType.FAIR_VALUE_GAP, price_location)
        ob_score = self._alignment_score(zone_entries, InstitutionalZoneType.ORDER_BLOCK, price_location)
        breaker_score = self._alignment_score(zone_entries, InstitutionalZoneType.BREAKER_BLOCK, price_location)
        mitigation_score = self._alignment_score(
            zone_entries,
            InstitutionalZoneType.MITIGATION_BLOCK,
            price_location,
        )
        freshness_score = self._freshness_score(dealing_range, bar_count)
        distance_score = self._distance_score(dealing_range, current_price)

        strength = (
            swing_score * Decimal(str(weights.swing_quality))
            + structure_score * Decimal(str(weights.structure_quality))
            + liquidity_score * Decimal(str(weights.liquidity_confirmation))
            + htf_score * Decimal(str(weights.htf_alignment))
            + fvg_score * Decimal(str(weights.fvg_alignment))
            + ob_score * Decimal(str(weights.order_block_alignment))
            + breaker_score * Decimal(str(weights.breaker_alignment))
            + mitigation_score * Decimal(str(weights.mitigation_alignment))
            + freshness_score * Decimal(str(weights.freshness))
            + distance_score * Decimal(str(weights.distance_from_equilibrium))
        )
        strength = min(Decimal("1"), max(Decimal("0"), strength))
        quality = self._quality_tier(strength)
        bias = self._derive_bias(dealing_range, price_location, structure)
        confidence = strength if dealing_range.is_valid else Decimal("0")
        return strength, quality, bias, confidence

    def collect_zone_entries(
        self,
        *,
        order_blocks: list[OrderBlock] | None,
        fair_value_gap_state: FairValueGapState | None,
        breaker_blocks: list[BreakerBlock] | None,
        mitigation_blocks: list[MitigationBlock] | None,
        liquidity_state: LiquidityState | None,
        dealing_range: DealingRange,
    ) -> list[ArrayZoneEntry]:
        """Normalize upstream zones into array entries."""
        entries: list[ArrayZoneEntry] = []
        filters = self._config.zone_filters

        if order_blocks:
            allowed = set(filters.order_block_statuses)
            for block in order_blocks:
                if block.status.value not in allowed:
                    continue
                entries.append(self._entry_from_bounds(
                    block.block_id,
                    InstitutionalZoneType.ORDER_BLOCK,
                    block.low,
                    block.high,
                    direction=block.direction.value,
                    status=block.status.value,
                    strength=block.strength,
                    dealing_range=dealing_range,
                ))

        if fair_value_gap_state:
            allowed = set(filters.fvg_statuses)
            for gap in fair_value_gap_state.active_gaps:
                if gap.status.value not in allowed:
                    continue
                entries.append(self._entry_from_bounds(
                    gap.gap_id,
                    InstitutionalZoneType.FAIR_VALUE_GAP,
                    gap.low,
                    gap.high,
                    direction=gap.direction.value,
                    status=gap.status.value,
                    strength=gap.strength,
                    dealing_range=dealing_range,
                ))

        if breaker_blocks:
            allowed = set(filters.breaker_statuses)
            for block in breaker_blocks:
                if block.status.value not in allowed:
                    continue
                entries.append(self._entry_from_bounds(
                    block.breaker_id,
                    InstitutionalZoneType.BREAKER_BLOCK,
                    block.low,
                    block.high,
                    direction=block.direction.value,
                    status=block.status.value,
                    strength=block.strength,
                    dealing_range=dealing_range,
                ))

        if mitigation_blocks:
            allowed = set(filters.mitigation_statuses)
            for block in mitigation_blocks:
                if block.status.value not in allowed:
                    continue
                entries.append(self._entry_from_bounds(
                    block.block_id,
                    InstitutionalZoneType.MITIGATION_BLOCK,
                    block.low,
                    block.high,
                    direction=block.direction.value,
                    status=block.status.value,
                    strength=block.strength,
                    dealing_range=dealing_range,
                ))

        if self._config.include_liquidity_zones and liquidity_state:
            for zone in liquidity_state.active_zones:
                if not zone.is_active:
                    continue
                entries.append(self._entry_from_bounds(
                    zone.zone_id,
                    InstitutionalZoneType.LIQUIDITY,
                    zone.lower_bound,
                    zone.upper_bound,
                    direction=zone.side.value,
                    status="active",
                    strength=Decimal("0.5"),
                    dealing_range=dealing_range,
                ))

        return entries

    def assemble_arrays(
        self,
        entries: list[ArrayZoneEntry],
        dealing_range: DealingRange,
        territory: PremiumDiscountZone,
    ) -> list[InstitutionalArray]:
        """Cluster zone entries into institutional arrays."""
        classified = [
            entry
            for entry in entries
            if self._lifecycle.classify_price(entry.midpoint, dealing_range) is territory
        ]
        if not classified:
            return []

        sorted_entries = sorted(classified, key=lambda entry: entry.midpoint)
        clusters: list[list[ArrayZoneEntry]] = []
        current: list[ArrayZoneEntry] = []

        for entry in sorted_entries:
            if not current:
                current = [entry]
                continue
            if abs(entry.midpoint - current[-1].midpoint) <= self._config.array_cluster_price:
                current.append(entry)
            else:
                clusters.append(current)
                current = [entry]
        if current:
            clusters.append(current)

        arrays: list[InstitutionalArray] = []
        for cluster in clusters:
            if len(cluster) < self._config.min_array_entries:
                continue
            cluster_high = max(entry.high for entry in cluster)
            cluster_low = min(entry.low for entry in cluster)
            strengths = [entry.strength for entry in cluster]
            confluence = sum(strengths) / Decimal(str(len(strengths)))
            directions = [entry.direction for entry in cluster if entry.direction]
            dominant = max(set(directions), key=directions.count) if directions else None
            arrays.append(
                InstitutionalArray(
                    array_id=f"array-{territory.value}-{uuid4().hex[:10]}",
                    territory=territory,
                    scope=dealing_range.scope,
                    zone_entries=list(cluster),
                    cluster_high=cluster_high,
                    cluster_low=cluster_low,
                    entry_count=len(cluster),
                    dominant_direction=dominant,
                    confluence_score=min(Decimal("1"), confluence),
                    evidence=[f"{len(cluster)} zones clustered in {territory.value}"],
                ),
            )

        arrays.sort(key=lambda item: item.confluence_score, reverse=True)
        return arrays[: self._config.max_arrays_per_territory]

    def detect_nested_zones(
        self,
        entries: list[ArrayZoneEntry],
        dealing_range: DealingRange,
    ) -> tuple[list[NestedZoneContext], list[NestedZoneContext]]:
        """Detect nested premium and discount zone relationships."""
        if not self._config.nesting_enabled:
            return [], []

        nested_premium: list[NestedZoneContext] = []
        nested_discount: list[NestedZoneContext] = []

        for child in entries:
            child_territory = self._lifecycle.classify_price(child.midpoint, dealing_range)
            for parent in entries:
                if child.zone_id == parent.zone_id:
                    continue
                parent_territory = self._lifecycle.classify_price(parent.midpoint, dealing_range)
                if child_territory != parent_territory:
                    continue
                containment = self._containment_percent(child, parent)
                if containment < Decimal(str(self._config.nest_overlap_min_percent)):
                    continue
                context = NestedZoneContext(
                    child_zone_id=child.zone_id,
                    child_zone_type=child.zone_type,
                    parent_zone_id=parent.zone_id,
                    parent_zone_type=parent.zone_type,
                    territory=child_territory,
                    containment_percent=containment,
                    evidence=[
                        f"{child.zone_id} nested {containment}% within {parent.zone_id}",
                    ],
                )
                if child_territory is PremiumDiscountZone.PREMIUM:
                    nested_premium.append(context)
                elif child_territory is PremiumDiscountZone.DISCOUNT:
                    nested_discount.append(context)

        return nested_premium, nested_discount

    def score_mtf_premium_alignment(
        self,
        *,
        ltf_timeframe: str,
        ltf_range: DealingRange,
        ltf_location: PremiumDiscountZone,
        ltf_arrays: list[InstitutionalArray],
        htf_context: PremiumDiscountContext,
        structure: MarketStructure | None,
    ) -> MTFPremiumDiscountAlignment | None:
        """Score LTF/HTF premium alignment."""
        return self._score_mtf_alignment(
            territory=PremiumDiscountZone.PREMIUM,
            ltf_timeframe=ltf_timeframe,
            ltf_range=ltf_range,
            ltf_location=ltf_location,
            ltf_arrays=ltf_arrays,
            htf_context=htf_context,
            structure=structure,
        )

    def score_mtf_discount_alignment(
        self,
        *,
        ltf_timeframe: str,
        ltf_range: DealingRange,
        ltf_location: PremiumDiscountZone,
        ltf_arrays: list[InstitutionalArray],
        htf_context: PremiumDiscountContext,
        structure: MarketStructure | None,
    ) -> MTFPremiumDiscountAlignment | None:
        """Score LTF/HTF discount alignment."""
        return self._score_mtf_alignment(
            territory=PremiumDiscountZone.DISCOUNT,
            ltf_timeframe=ltf_timeframe,
            ltf_range=ltf_range,
            ltf_location=ltf_location,
            ltf_arrays=ltf_arrays,
            htf_context=htf_context,
            structure=structure,
        )

    def build_htf_contexts(
        self,
        htf_context: PremiumDiscountContext,
    ) -> tuple[HTFPricingContext | None, HTFPricingContext | None]:
        """Build HTF premium and discount pricing contexts."""
        premium_count = len(htf_context.premium_arrays)
        discount_count = len(htf_context.discount_arrays)

        htf_premium = None
        htf_discount = None

        if htf_context.price_location in {
            PremiumDiscountZone.PREMIUM,
            PremiumDiscountZone.EQUILIBRIUM,
        }:
            htf_premium = HTFPricingContext(
                timeframe=htf_context.timeframe,
                territory=PremiumDiscountZone.PREMIUM,
                dealing_range=htf_context.dealing_range,
                array_count=premium_count,
                equilibrium=htf_context.equilibrium,
                evidence=[f"HTF premium context on {htf_context.timeframe}"],
            )
        if htf_context.price_location in {
            PremiumDiscountZone.DISCOUNT,
            PremiumDiscountZone.EQUILIBRIUM,
        }:
            htf_discount = HTFPricingContext(
                timeframe=htf_context.timeframe,
                territory=PremiumDiscountZone.DISCOUNT,
                dealing_range=htf_context.dealing_range,
                array_count=discount_count,
                equilibrium=htf_context.equilibrium,
                evidence=[f"HTF discount context on {htf_context.timeframe}"],
            )

        return htf_premium, htf_discount

    def resolve_fib_direction(
        self,
        structure: MarketStructure | None,
    ) -> FibDirection:
        """Resolve Fibonacci projection direction from configuration."""
        mode = self._config.fibonacci_direction_mode
        if mode == "bullish":
            return FibDirection.BULLISH
        if mode == "bearish":
            return FibDirection.BEARISH
        if mode == "auto" and structure and structure.bos_events:
            latest = structure.bos_events[-1]
            return (
                FibDirection.BULLISH
                if latest.direction.value == "bullish"
                else FibDirection.BEARISH
            )
        if structure and structure.current_trend is TrendDirection.BEARISH:
            return FibDirection.BEARISH
        if self._config.ote_default_direction == "bearish":
            return FibDirection.BEARISH
        return FibDirection.BULLISH

    def _score_mtf_alignment(
        self,
        *,
        territory: PremiumDiscountZone,
        ltf_timeframe: str,
        ltf_range: DealingRange,
        ltf_location: PremiumDiscountZone,
        ltf_arrays: list[InstitutionalArray],
        htf_context: PremiumDiscountContext,
        structure: MarketStructure | None,
    ) -> MTFPremiumDiscountAlignment | None:
        territory_match = Decimal("1") if ltf_location is territory and htf_context.price_location is territory else Decimal("0")
        range_overlap = self._range_overlap_percent(ltf_range, htf_context.dealing_range)
        htf_arrays = (
            htf_context.premium_arrays
            if territory is PremiumDiscountZone.PREMIUM
            else htf_context.discount_arrays
        )
        array_overlap = self._array_overlap_count(ltf_arrays, htf_arrays)
        trend_support = Decimal("0")
        if structure:
            if territory is PremiumDiscountZone.PREMIUM and structure.current_trend is TrendDirection.BEARISH:
                trend_support = Decimal("1")
            elif territory is PremiumDiscountZone.DISCOUNT and structure.current_trend is TrendDirection.BULLISH:
                trend_support = Decimal("1")
            elif structure.current_trend is TrendDirection.RANGE:
                trend_support = Decimal("0.5")

        score = (
            territory_match * Decimal("0.4")
            + (range_overlap / Decimal("100")) * Decimal("0.3")
            + (Decimal(str(min(array_overlap, 3))) / Decimal("3")) * Decimal("0.2")
            + trend_support * Decimal("0.1")
        )
        score = min(Decimal("1"), max(Decimal("0"), score))
        if score < Decimal(str(self._config.mtf_alignment_min_score)):
            return None

        return MTFPremiumDiscountAlignment(
            territory=territory,
            aligned_timeframes=[ltf_timeframe, htf_context.timeframe],
            alignment_score=score,
            ltf_timeframe=ltf_timeframe,
            htf_timeframe=htf_context.timeframe,
            range_overlap_percent=range_overlap,
            array_overlap_count=array_overlap,
            evidence=[f"MTF {territory.value} alignment score {score}"],
        )

    def _entry_from_bounds(
        self,
        zone_id: str,
        zone_type: InstitutionalZoneType,
        low: Decimal,
        high: Decimal,
        *,
        direction: str | None,
        status: str | None,
        strength: Decimal,
        dealing_range: DealingRange,
    ) -> ArrayZoneEntry:
        midpoint = (high + low) / Decimal("2")
        distance_pips = abs(midpoint - dealing_range.equilibrium) / Decimal(str(self._config.pip_size))
        territory = self._lifecycle.classify_price(midpoint, dealing_range)
        placement = Decimal("1") if territory in {PremiumDiscountZone.PREMIUM, PremiumDiscountZone.DISCOUNT} else Decimal("0.3")
        return ArrayZoneEntry(
            zone_id=zone_id,
            zone_type=zone_type,
            high=high,
            low=low,
            midpoint=midpoint,
            direction=direction,
            status=status,
            strength=strength,
            distance_from_equilibrium_pips=distance_pips,
            placement_score=placement,
        )

    @staticmethod
    def _quality_tier(strength: Decimal) -> PremiumDiscountQuality:
        if strength >= Decimal("0.7"):
            return PremiumDiscountQuality.HIGH
        if strength >= Decimal("0.45"):
            return PremiumDiscountQuality.MEDIUM
        return PremiumDiscountQuality.LOW

    @staticmethod
    def _derive_bias(
        dealing_range: DealingRange,
        price_location: PremiumDiscountZone,
        structure: MarketStructure | None,
    ) -> PremiumDiscountBias:
        if not dealing_range.is_valid:
            return PremiumDiscountBias.UNDETERMINED
        if price_location is PremiumDiscountZone.PREMIUM:
            return PremiumDiscountBias.PREMIUM
        if price_location is PremiumDiscountZone.DISCOUNT:
            return PremiumDiscountBias.DISCOUNT
        if price_location is PremiumDiscountZone.EQUILIBRIUM:
            return PremiumDiscountBias.EQUILIBRIUM
        return PremiumDiscountBias.NEUTRAL

    def _liquidity_score(
        self,
        dealing_range: DealingRange,
        liquidity_state: LiquidityState | None,
    ) -> Decimal:
        if liquidity_state is None:
            return Decimal("0.3")
        if liquidity_state.recent_sweeps:
            for sweep in liquidity_state.recent_sweeps[-3:]:
                if abs(sweep.sweep_price - dealing_range.equilibrium) <= self._config.equilibrium_tolerance_price * 2:
                    return Decimal("0.8")
        return Decimal("0.4") if liquidity_state.active_zones else Decimal("0.3")

    @staticmethod
    def _htf_score(
        mtf_premium: MTFPremiumDiscountAlignment | None,
        mtf_discount: MTFPremiumDiscountAlignment | None,
    ) -> Decimal:
        scores = [
            item.alignment_score
            for item in (mtf_premium, mtf_discount)
            if item is not None
        ]
        if not scores:
            return Decimal("0.3")
        return max(scores)

    @staticmethod
    def _alignment_score(
        entries: list[ArrayZoneEntry],
        zone_type: InstitutionalZoneType,
        territory: PremiumDiscountZone,
    ) -> Decimal:
        matched = [
            entry
            for entry in entries
            if entry.zone_type is zone_type
            and (
                territory is PremiumDiscountZone.EQUILIBRIUM
                or entry.placement_score >= Decimal("0.5")
            )
        ]
        if not matched:
            return Decimal("0.2")
        return min(Decimal("1"), sum(entry.strength for entry in matched) / Decimal(str(len(matched))))

    @staticmethod
    def _freshness_score(dealing_range: DealingRange, bar_count: int) -> Decimal:
        if bar_count <= 0:
            return Decimal("0.5")
        age = bar_count - dealing_range.formation_bar_index
        ratio = Decimal(str(max(0, age))) / Decimal(str(bar_count))
        return max(Decimal("0.1"), Decimal("1") - ratio)

    def _distance_score(self, dealing_range: DealingRange, current_price: Decimal) -> Decimal:
        distance_pips = abs(current_price - dealing_range.equilibrium) / Decimal(str(self._config.pip_size))
        tolerance = Decimal(str(self._config.equilibrium_tolerance_pips))
        if distance_pips >= tolerance * 2:
            return Decimal("1")
        if distance_pips <= tolerance:
            return Decimal("0.3")
        span = tolerance * 2 - tolerance
        if span <= 0:
            return Decimal("0.3")
        progress = (distance_pips - tolerance) / span
        return Decimal("0.3") + progress * Decimal("0.7")

    @staticmethod
    def _containment_percent(child: ArrayZoneEntry, parent: ArrayZoneEntry) -> Decimal:
        overlap_low = max(child.low, parent.low)
        overlap_high = min(child.high, parent.high)
        if overlap_high <= overlap_low:
            return Decimal("0")
        child_size = child.high - child.low
        if child_size <= 0:
            return Decimal("0")
        return ((overlap_high - overlap_low) / child_size) * Decimal("100")

    @staticmethod
    def _range_overlap_percent(ltf: DealingRange, htf: DealingRange) -> Decimal:
        overlap_low = max(ltf.low, htf.low)
        overlap_high = min(ltf.high, htf.high)
        if overlap_high <= overlap_low:
            return Decimal("0")
        ltf_size = ltf.high - ltf.low
        if ltf_size <= 0:
            return Decimal("0")
        return ((overlap_high - overlap_low) / ltf_size) * Decimal("100")

    @staticmethod
    def _array_overlap_count(
        ltf_arrays: list[InstitutionalArray],
        htf_arrays: list[InstitutionalArray],
    ) -> int:
        count = 0
        for ltf in ltf_arrays:
            for htf in htf_arrays:
                if ltf.cluster_low <= htf.cluster_high and ltf.cluster_high >= htf.cluster_low:
                    count += 1
        return count
