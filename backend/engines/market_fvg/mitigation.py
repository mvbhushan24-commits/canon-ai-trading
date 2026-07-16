"""Fill tracking, mitigation, lifecycle, and premium/discount classification."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.config import FairValueGapConfig
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapStatus,
    PremiumDiscountZone,
)
from backend.engines.market_structure import MarketStructure, SwingPoint, TrendDirection


class LifecycleUpdate:
    """Lifecycle evaluation result for a single gap."""

    def __init__(
        self,
        *,
        gap: FairValueGap,
        ce_encroached: bool = False,
        ce_encroachment_bar_index: int | None = None,
        ce_encroachment_price: Decimal | None = None,
    ) -> None:
        self.gap = gap
        self.ce_encroached = ce_encroached
        self.ce_encroachment_bar_index = ce_encroachment_bar_index
        self.ce_encroachment_price = ce_encroachment_price


class MitigationManager:
    """Track fills, mitigation, invalidation, expiration, and premium/discount."""

    def __init__(self, config: FairValueGapConfig) -> None:
        self._config = config

    def update_status(
        self,
        gap: FairValueGap,
        candles: list[NormalizedCandle],
        *,
        current_bar_count: int,
    ) -> LifecycleUpdate:
        """Evaluate lifecycle from formation through latest candle."""
        start_index = gap.candle_c_index + 1
        status = FairValueGapStatus.OPEN
        fill_percent = Decimal("0")
        fill_bar_index = gap.fill_bar_index
        mitigation_bar_index = gap.mitigation_bar_index
        invalidation_bar_index = gap.invalidation_bar_index
        expiration_bar_index = gap.expiration_bar_index
        ce_encroached = False
        ce_encroachment_bar_index: int | None = None
        ce_encroachment_price: Decimal | None = None

        entered = False
        deepest_bullish = gap.high
        highest_bearish = gap.low

        for index in range(start_index, len(candles)):
            candle = candles[index]

            if status in {
                FairValueGapStatus.INVALIDATED,
                FairValueGapStatus.EXPIRED,
                FairValueGapStatus.FILLED,
                FairValueGapStatus.MITIGATED,
            }:
                break

            age = current_bar_count - gap.origin_bar_index
            if age > self._config.max_gap_age_bars:
                status = FairValueGapStatus.EXPIRED
                expiration_bar_index = index
                break

            if self._is_invalidated(gap, candle):
                status = FairValueGapStatus.INVALIDATED
                invalidation_bar_index = index
                break

            if not entered and self._enters_gap(gap, candle):
                entered = True
                status = FairValueGapStatus.PARTIAL

            if entered:
                fill_percent = self._compute_fill_percent(
                    gap,
                    candle,
                    deepest_bullish=deepest_bullish,
                    highest_bearish=highest_bearish,
                )
                if gap.direction is FairValueGapDirection.BULLISH:
                    deepest_bullish = min(deepest_bullish, candle.low)
                else:
                    highest_bearish = max(highest_bearish, candle.high)

                if not ce_encroached and self._touches_ce(gap, candle):
                    ce_encroached = True
                    ce_encroachment_bar_index = index
                    ce_encroachment_price = gap.ce_price
                    if self._config.mitigation_mode == "ce":
                        status = FairValueGapStatus.MITIGATED
                        mitigation_bar_index = index
                        break

                if self._is_fully_filled(gap, candle):
                    if self._config.fill_mode == "ce":
                        status = FairValueGapStatus.MITIGATED
                        mitigation_bar_index = index
                    else:
                        status = FairValueGapStatus.FILLED
                        fill_bar_index = index
                    fill_percent = Decimal(str(self._config.full_fill_percent))
                    break

                if self._should_mitigate(gap, fill_percent, status):
                    status = FairValueGapStatus.MITIGATED
                    mitigation_bar_index = index
                    break

                if fill_percent > Decimal("0") and fill_percent < Decimal(
                    str(self._config.full_fill_percent),
                ):
                    status = FairValueGapStatus.PARTIAL

        updated_gap = gap.model_copy(
            update={
                "status": status,
                "fill_percent": min(
                    Decimal(str(self._config.full_fill_percent)),
                    max(Decimal("0"), fill_percent),
                ),
                "fill_bar_index": fill_bar_index,
                "mitigation_bar_index": mitigation_bar_index,
                "invalidation_bar_index": invalidation_bar_index,
                "expiration_bar_index": expiration_bar_index,
            },
        )
        return LifecycleUpdate(
            gap=updated_gap,
            ce_encroached=ce_encroached,
            ce_encroachment_bar_index=ce_encroachment_bar_index,
            ce_encroachment_price=ce_encroachment_price,
        )

    def classify_gaps(
        self,
        gaps: list[FairValueGap],
        candles: list[NormalizedCandle],
        *,
        current_bar_count: int,
    ) -> list[LifecycleUpdate]:
        """Update lifecycle for all gaps."""
        return [
            self.update_status(
                gap,
                candles,
                current_bar_count=current_bar_count,
            )
            for gap in gaps
        ]

    def compute_fill_percent(
        self,
        gap: FairValueGap,
        candles: list[NormalizedCandle],
    ) -> Decimal:
        """Compute current fill percentage for a gap."""
        update = self.update_status(
            gap,
            candles,
            current_bar_count=len(candles),
        )
        return update.gap.fill_percent

    def classify_premium_discount(
        self,
        gap: FairValueGap,
        structure: MarketStructure | None,
    ) -> tuple[PremiumDiscountZone, Decimal | None, Decimal | None, list[str]]:
        """Classify gap placement relative to structure dealing range."""
        evidence: list[str] = []
        if structure is None:
            evidence.append("Dealing range unavailable")
            return PremiumDiscountZone.EQUILIBRIUM, None, None, evidence

        range_high, range_low = self._dealing_range(structure)
        if range_high is None or range_low is None:
            evidence.append("Dealing range unavailable")
            return PremiumDiscountZone.EQUILIBRIUM, None, None, evidence

        equilibrium = (range_high + range_low) / Decimal("2")
        tolerance = Decimal(str(self._config.equilibrium_tolerance_price))

        if gap.ce_price > equilibrium + tolerance:
            evidence.append("Gap CE above dealing range equilibrium — premium")
            return PremiumDiscountZone.PREMIUM, range_high, range_low, evidence

        if gap.ce_price < equilibrium - tolerance:
            evidence.append("Gap CE below dealing range equilibrium — discount")
            return PremiumDiscountZone.DISCOUNT, range_high, range_low, evidence

        evidence.append("Gap CE near dealing range equilibrium")
        return PremiumDiscountZone.EQUILIBRIUM, range_high, range_low, evidence

    def resolve_nesting(self, gaps: list[FairValueGap]) -> list[FairValueGap]:
        """Resolve parent-child nesting for contained gaps."""
        if not self._config.nesting_enabled or len(gaps) < 2:
            return gaps

        sorted_gaps = sorted(
            gaps,
            key=lambda gap: (gap.origin_time_utc, gap.gap_size),
            reverse=True,
        )
        parent_map: dict[str, str | None] = {gap.gap_id: None for gap in gaps}
        children_map: dict[str, list[str]] = {gap.gap_id: [] for gap in gaps}

        for parent in sorted_gaps:
            for child in sorted_gaps:
                if parent.gap_id == child.gap_id:
                    continue
                if child.low >= parent.low and child.high <= parent.high:
                    existing_parent = parent_map.get(child.gap_id)
                    if existing_parent is None:
                        parent_map[child.gap_id] = parent.gap_id
                        children_map[parent.gap_id].append(child.gap_id)

        updated: list[FairValueGap] = []
        for gap in gaps:
            updated.append(
                gap.model_copy(
                    update={
                        "nested_parent_gap_id": parent_map.get(gap.gap_id),
                        "nested_child_gap_ids": sorted(
                            children_map.get(gap.gap_id, []),
                        ),
                    },
                ),
            )
        return updated

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

    def _enters_gap(self, gap: FairValueGap, candle: NormalizedCandle) -> bool:
        mode = self._config.entry_touch_mode
        if mode == "wick":
            return candle.low <= gap.high and candle.high >= gap.low
        if mode == "body":
            body_high = max(candle.open, candle.close)
            body_low = min(candle.open, candle.close)
            return body_low <= gap.high and body_high >= gap.low
        return gap.low <= candle.close <= gap.high

    def _touches_ce(self, gap: FairValueGap, candle: NormalizedCandle) -> bool:
        return candle.low <= gap.ce_price <= candle.high

    def _is_invalidated(self, gap: FairValueGap, candle: NormalizedCandle) -> bool:
        mode = self._config.invalidation_mode
        if gap.direction is FairValueGapDirection.BULLISH:
            if mode == "close":
                return candle.close < gap.low
            body_low = min(candle.open, candle.close)
            return body_low < gap.low

        if mode == "close":
            return candle.close > gap.high
        body_high = max(candle.open, candle.close)
        return body_high > gap.high

    def _is_fully_filled(self, gap: FairValueGap, candle: NormalizedCandle) -> bool:
        mode = self._config.fill_mode
        if mode == "ce":
            return gap.low <= candle.close <= gap.high and self._touches_ce(gap, candle)

        if gap.direction is FairValueGapDirection.BULLISH:
            target = gap.low
            if mode == "wick":
                return candle.low <= target
            if mode == "body":
                return min(candle.open, candle.close) <= target
            return candle.close <= target

        target = gap.high
        if mode == "wick":
            return candle.high >= target
        if mode == "body":
            return max(candle.open, candle.close) >= target
        return candle.close >= target

    def _should_mitigate(
        self,
        gap: FairValueGap,
        fill_percent: Decimal,
        status: FairValueGapStatus,
    ) -> bool:
        mode = self._config.mitigation_mode
        if mode == "ce":
            return False
        if mode == "partial":
            return fill_percent >= Decimal(str(self._config.mitigation_fill_percent))
        if mode == "full_fill":
            return status is FairValueGapStatus.FILLED
        return False

    def _compute_fill_percent(
        self,
        gap: FairValueGap,
        candle: NormalizedCandle,
        *,
        deepest_bullish: Decimal,
        highest_bearish: Decimal,
    ) -> Decimal:
        if gap.gap_size <= 0:
            return Decimal("0")

        if gap.direction is FairValueGapDirection.BULLISH:
            if candle.low > gap.high:
                return Decimal("0")
            penetration = gap.high - min(deepest_bullish, candle.low)
        else:
            if candle.high < gap.low:
                return Decimal("0")
            penetration = max(highest_bearish, candle.high) - gap.low

        percent = (penetration / gap.gap_size) * Decimal("100")
        return min(Decimal(str(self._config.full_fill_percent)), max(Decimal("0"), percent))

    @staticmethod
    def premium_discount_alignment_score(
        gap: FairValueGap,
        zone: PremiumDiscountZone,
    ) -> Decimal:
        """Score whether gap sits in the preferred zone for its direction."""
        if zone is PremiumDiscountZone.EQUILIBRIUM:
            return Decimal("0.5")
        if gap.direction is FairValueGapDirection.BULLISH:
            return Decimal("1") if zone is PremiumDiscountZone.DISCOUNT else Decimal("0.2")
        return Decimal("1") if zone is PremiumDiscountZone.PREMIUM else Decimal("0.2")

    @staticmethod
    def structure_trend(structure: MarketStructure | None) -> TrendDirection:
        if structure is None:
            return TrendDirection.UNDETERMINED
        return structure.current_trend
