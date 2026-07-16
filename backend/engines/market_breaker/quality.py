"""Breaker block quality, confluence, and premium/discount scoring."""

from decimal import Decimal

from backend.engines.market_breaker.config import BreakerBlockConfig
from backend.engines.market_breaker.schemas import (
    BreakerBlock,
    BreakerBlockDirection,
    BreakerBlockQuality,
    BreakerBlockStatus,
)
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapState,
    FairValueGapStatus,
    PremiumDiscountZone,
)
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_liquidity.schemas import SweepDirection
from backend.engines.market_structure import CHoCHDirection, MarketStructure, SwingPoint, TrendDirection


class QualityScorer:
    """Compute composite strength, confluence, and quality classification."""

    def __init__(self, config: BreakerBlockConfig) -> None:
        self._config = config

    def score(
        self,
        breaker: BreakerBlock,
        *,
        candles_count: int,
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        invalidation_displacement: Decimal | None = None,
    ) -> tuple[
        Decimal,
        BreakerBlockQuality,
        bool,
        bool,
        bool,
        list[str],
        list[str],
        list[str],
        PremiumDiscountZone,
        Decimal | None,
        Decimal | None,
    ]:
        """Return strength, quality, flags, confluence IDs, zone, and evidence."""
        evidence: list[str] = []
        weights = self._config.quality_weights

        source_score = self._source_quality_score(breaker, evidence)
        invalidation_score = self._invalidation_strength_score(
            breaker,
            invalidation_displacement,
            evidence,
        )
        confirmation_score = self._confirmation_score(breaker, evidence)
        structure_score, structure_alignment = self._structure_score(
            breaker,
            structure,
            evidence,
        )

        liquidity_score, liquidity_confluence, liquidity_ids = self._liquidity_score(
            breaker,
            liquidity_state,
            evidence,
        )
        fvg_score, fvg_confluence, fvg_ids = self._fvg_score(
            breaker,
            fair_value_gap_state,
            evidence,
        )

        premium_zone, range_high, range_low, premium_evidence = (
            self.classify_premium_discount(breaker, structure)
        )
        evidence.extend(premium_evidence)
        premium_score = self._premium_discount_score(breaker, premium_zone, evidence)
        freshness_score = self._freshness_score(breaker, candles_count, evidence)

        strength = (
            source_score * Decimal(str(weights.source_quality))
            + invalidation_score * Decimal(str(weights.invalidation_strength))
            + confirmation_score * Decimal(str(weights.confirmation))
            + structure_score * Decimal(str(weights.structure))
            + liquidity_score * Decimal(str(weights.liquidity))
            + fvg_score * Decimal(str(weights.fvg))
            + premium_score * Decimal(str(weights.premium_discount))
            + freshness_score * Decimal(str(weights.freshness))
        )
        strength = min(Decimal("1"), max(Decimal("0"), strength))
        quality = self._quality_tier(strength)

        return (
            strength,
            quality,
            structure_alignment,
            liquidity_confluence,
            fvg_confluence,
            liquidity_ids,
            fvg_ids,
            evidence,
            premium_zone,
            range_high,
            range_low,
        )

    def score_confluence(
        self,
        breaker: BreakerBlock,
        liquidity_state: LiquidityState | None,
        fair_value_gap_state: FairValueGapState | None,
    ) -> BreakerBlock:
        """Enrich breaker with liquidity and FVG confluence fields."""
        evidence = list(breaker.evidence)
        _, liquidity_confluence, liquidity_ids = self._liquidity_score(
            breaker,
            liquidity_state,
            evidence,
        )
        _, fvg_confluence, fvg_ids = self._fvg_score(
            breaker,
            fair_value_gap_state,
            evidence,
        )
        return breaker.model_copy(
            update={
                "liquidity_confluence": liquidity_confluence,
                "fvg_confluence": fvg_confluence,
                "liquidity_confluence_ids": liquidity_ids,
                "fvg_confluence_ids": fvg_ids,
            },
        )

    def classify_premium_discount(
        self,
        breaker: BreakerBlock,
        structure: MarketStructure | None,
    ) -> tuple[PremiumDiscountZone, Decimal | None, Decimal | None, list[str]]:
        """Classify breaker placement relative to structure dealing range."""
        evidence: list[str] = []
        if structure is None:
            evidence.append("Dealing range unavailable")
            return PremiumDiscountZone.EQUILIBRIUM, None, None, evidence

        range_high, range_low = self._dealing_range(structure)
        if range_high is None or range_low is None:
            evidence.append("Dealing range unavailable")
            return PremiumDiscountZone.EQUILIBRIUM, None, None, evidence

        midpoint = (breaker.high + breaker.low) / Decimal("2")
        equilibrium = (range_high + range_low) / Decimal("2")
        tolerance = Decimal(str(self._config.equilibrium_tolerance_price))

        if midpoint > equilibrium + tolerance:
            evidence.append("Breaker midpoint above dealing range equilibrium — premium")
            return PremiumDiscountZone.PREMIUM, range_high, range_low, evidence

        if midpoint < equilibrium - tolerance:
            evidence.append("Breaker midpoint below dealing range equilibrium — discount")
            return PremiumDiscountZone.DISCOUNT, range_high, range_low, evidence

        evidence.append("Breaker midpoint near dealing range equilibrium")
        return PremiumDiscountZone.EQUILIBRIUM, range_high, range_low, evidence

    def passes_minimum(self, strength: Decimal) -> bool:
        return strength >= Decimal(str(self._config.min_quality_score))

    def has_counter_trend_choch(
        self,
        breaker: BreakerBlock,
        structure: MarketStructure,
    ) -> bool:
        for event in structure.choch_events:
            if event.bar_index < breaker.formation_bar_index:
                continue
            if breaker.direction is BreakerBlockDirection.BULLISH:
                if event.direction is CHoCHDirection.BULLISH:
                    return True
            elif event.direction is CHoCHDirection.BEARISH:
                return True
        return False

    def compute_invalidation_displacement(
        self,
        breaker: BreakerBlock,
        candles: list,
    ) -> Decimal:
        """Compute displacement beyond invalidation boundary at invalidation bar."""
        index = breaker.invalidation_bar_index
        if index < 0 or index >= len(candles):
            return Decimal("0")

        candle = candles[index]
        if breaker.direction is BreakerBlockDirection.BEARISH:
            if candle.close < breaker.low:
                return breaker.low - candle.close
            return Decimal("0")

        if candle.close > breaker.high:
            return candle.close - breaker.high
        return Decimal("0")

    def _source_quality_score(
        self,
        breaker: BreakerBlock,
        evidence: list[str],
    ) -> Decimal:
        tier_scores = {"high": Decimal("1"), "medium": Decimal("0.6"), "low": Decimal("0.3")}
        source_quality = "medium"
        for item in breaker.evidence:
            if item.startswith("Source quality:"):
                source_quality = item.split(":", 1)[1].strip().lower()
                break
        score = tier_scores.get(source_quality, Decimal("0.5"))
        evidence.append(f"Source quality contributes {score:.2f}")
        return score

    def _invalidation_strength_score(
        self,
        breaker: BreakerBlock,
        displacement: Decimal | None,
        evidence: list[str],
    ) -> Decimal:
        if displacement is None or displacement <= 0:
            evidence.append("Invalidation displacement minimal")
            return Decimal("0.3")

        minimum = self._config.min_zone_size_price
        if minimum <= 0:
            return Decimal("0.5")

        ratio = displacement / minimum
        score = min(Decimal("1"), max(Decimal("0"), ratio / Decimal("2")))
        evidence.append(f"Invalidation strength scored {score:.2f}")
        return score

    def _confirmation_score(
        self,
        breaker: BreakerBlock,
        evidence: list[str],
    ) -> Decimal:
        if breaker.is_confirmed or breaker.status is BreakerBlockStatus.CONFIRMED:
            evidence.append("Breaker confirmed — full confirmation score")
            return Decimal("1")
        if breaker.status is BreakerBlockStatus.CANDIDATE:
            evidence.append("Breaker awaiting retest confirmation")
            return Decimal("0.2")
        if breaker.status is BreakerBlockStatus.MITIGATED:
            evidence.append("Breaker mitigated after confirmation")
            return Decimal("0.8")
        return Decimal("0.1")

    def _structure_score(
        self,
        breaker: BreakerBlock,
        structure: MarketStructure | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool]:
        if structure is None:
            evidence.append("Structure context unavailable")
            return Decimal("0.3"), False

        trend = structure.current_trend
        aligned = (
            breaker.direction is BreakerBlockDirection.BULLISH
            and trend is TrendDirection.BULLISH
        ) or (
            breaker.direction is BreakerBlockDirection.BEARISH
            and trend is TrendDirection.BEARISH
        )

        if aligned:
            evidence.append(f"Aligned with {trend.value} structure trend")
            return Decimal("1"), True

        if self.has_counter_trend_choch(breaker, structure):
            evidence.append("Counter-trend breaker supported by CHoCH")
            return Decimal("0.7"), False

        if trend is TrendDirection.RANGE:
            evidence.append("Structure in range — neutral alignment")
            return Decimal("0.5"), False

        evidence.append(f"Counter to {trend.value} structure trend")
        return Decimal("0.2"), False

    def _liquidity_score(
        self,
        breaker: BreakerBlock,
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
            if zone.lower_bound <= breaker.high and zone.upper_bound >= breaker.low:
                matched_ids.append(zone.zone_id)
                evidence.append(f"Breaker overlaps liquidity zone {zone.zone_id}")

        for sweep in liquidity_state.recent_sweeps:
            sweep_id = f"liq-sweep-{sweep.swept_level}-{sweep.bar_index}"
            midpoint = (breaker.high + breaker.low) / Decimal("2")
            if abs(sweep.swept_level - midpoint) <= proximity:
                matched_ids.append(sweep_id)
                evidence.append("Breaker near recent liquidity sweep")

            if breaker.direction is BreakerBlockDirection.BULLISH:
                if (
                    sweep.direction is SweepDirection.BULLISH
                    and abs(sweep.swept_level - breaker.low) <= proximity
                ):
                    matched_ids.append(sweep_id)
            elif (
                sweep.direction is SweepDirection.BEARISH
                and abs(sweep.swept_level - breaker.high) <= proximity
            ):
                matched_ids.append(sweep_id)

        if matched_ids:
            return Decimal("1"), True, sorted(set(matched_ids))

        return Decimal("0.4"), False, []

    def _fvg_score(
        self,
        breaker: BreakerBlock,
        fair_value_gap_state: FairValueGapState | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool, list[str]]:
        if not self._config.use_fvg_confluence or fair_value_gap_state is None:
            if fair_value_gap_state is None:
                evidence.append("FVG state unavailable")
            return Decimal("0.3"), False, []

        matched_ids: list[str] = []
        ce_proximity = self._config.fvg_ce_proximity_price
        midpoint = (breaker.high + breaker.low) / Decimal("2")
        min_overlap = Decimal(str(self._config.fvg_overlap_min_percent))

        for gap in fair_value_gap_state.active_gaps:
            if gap.status not in {FairValueGapStatus.OPEN, FairValueGapStatus.PARTIAL}:
                continue

            overlap_percent = self._overlap_percent(breaker, gap)
            ce_near = abs(gap.ce_price - midpoint) <= ce_proximity

            if overlap_percent >= min_overlap or ce_near:
                direction_aligned = (
                    breaker.direction is BreakerBlockDirection.BULLISH
                    and gap.direction is FairValueGapDirection.BULLISH
                ) or (
                    breaker.direction is BreakerBlockDirection.BEARISH
                    and gap.direction is FairValueGapDirection.BEARISH
                )
                if direction_aligned or overlap_percent >= min_overlap:
                    matched_ids.append(gap.gap_id)
                    evidence.append(
                        f"FVG confluence with {gap.gap_id} ({overlap_percent:.1f}% overlap)",
                    )

        if matched_ids:
            return Decimal("1"), True, sorted(set(matched_ids))

        return Decimal("0.4"), False, []

    def _premium_discount_score(
        self,
        breaker: BreakerBlock,
        zone: PremiumDiscountZone,
        evidence: list[str],
    ) -> Decimal:
        if zone is PremiumDiscountZone.EQUILIBRIUM:
            score = Decimal("0.5")
        elif breaker.direction is BreakerBlockDirection.BULLISH:
            score = Decimal("1") if zone is PremiumDiscountZone.DISCOUNT else Decimal("0.2")
        else:
            score = Decimal("1") if zone is PremiumDiscountZone.PREMIUM else Decimal("0.2")
        evidence.append(f"Premium/discount placement scored {score:.2f}")
        return score

    def _freshness_score(
        self,
        breaker: BreakerBlock,
        bar_count: int,
        evidence: list[str],
    ) -> Decimal:
        if breaker.status in {
            BreakerBlockStatus.INVALIDATED,
            BreakerBlockStatus.EXPIRED,
        }:
            return Decimal("0")

        if breaker.confirmation_bar_index is None:
            evidence.append("Unconfirmed breaker — reduced freshness")
            return Decimal("0.3")

        age = bar_count - breaker.confirmation_bar_index
        max_age = self._config.max_breaker_age_bars
        if age <= 0:
            evidence.append("Freshly confirmed breaker")
            return Decimal("1")
        if age >= max_age:
            return Decimal("0.1")

        ratio = Decimal(str(age)) / Decimal(str(max_age))
        score = max(Decimal("0.2"), Decimal("1") - ratio)
        evidence.append(f"Freshness scored {score:.2f} ({age} bars since confirmation)")
        return score

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
    def _overlap_percent(breaker: BreakerBlock, gap: FairValueGap) -> Decimal:
        overlap_low = max(breaker.low, gap.low)
        overlap_high = min(breaker.high, gap.high)
        if overlap_high <= overlap_low:
            return Decimal("0")

        overlap_size = overlap_high - overlap_low
        breaker_size = breaker.high - breaker.low
        gap_size = gap.high - gap.low
        denominator = min(breaker_size, gap_size)
        if denominator <= 0:
            return Decimal("0")
        return (overlap_size / denominator) * Decimal("100")

    @staticmethod
    def _quality_tier(strength: Decimal) -> BreakerBlockQuality:
        if strength >= Decimal("0.7"):
            return BreakerBlockQuality.HIGH
        if strength >= Decimal("0.4"):
            return BreakerBlockQuality.MEDIUM
        return BreakerBlockQuality.LOW
