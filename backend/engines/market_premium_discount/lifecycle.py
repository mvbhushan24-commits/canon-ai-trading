"""Dealing range lifecycle, invalidation, and territory transitions."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_premium_discount.config import PremiumDiscountConfig
from backend.engines.market_premium_discount.schemas import (
    DealingRange,
    DealingRangeScope,
    EquilibriumLevel,
    PremiumDiscountEvent,
    PremiumDiscountEventKind,
    PremiumDiscountZone,
    PriceZoneBand,
)
from backend.engines.market_structure import BOSDirection, CHoCHDirection, MarketStructure


class LifecycleManager:
    """Manage dealing range invalidation and price territory transitions."""

    def __init__(self, config: PremiumDiscountConfig) -> None:
        self._config = config

    def apply_invalidation(
        self,
        dealing_range: DealingRange,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
    ) -> DealingRange:
        """Invalidate dealing range on structure break, staleness, or age."""
        if not dealing_range.is_valid:
            return dealing_range

        current_bar = len(candles) - 1
        age_bars = current_bar - dealing_range.formation_bar_index
        if age_bars > self._config.max_range_age_bars:
            return dealing_range.model_copy(
                update={
                    "is_valid": False,
                    "invalidation_reason": "Range exceeded max age",
                    "evidence": dealing_range.evidence + ["Range stale — exceeded max age"],
                },
            )

        if structure is None or not candles:
            return dealing_range

        latest = candles[-1]
        if self._config.invalidate_on_bos:
            for event in structure.bos_events:
                if event.bar_index < dealing_range.formation_bar_index:
                    continue
                if (
                    event.direction is BOSDirection.BEARISH
                    and event.break_price < dealing_range.low
                ):
                    return self._invalidate(
                        dealing_range,
                        "Opposing BOS close below range low",
                        event.break_price,
                    )
                if (
                    event.direction is BOSDirection.BULLISH
                    and event.break_price > dealing_range.high
                ):
                    return self._invalidate(
                        dealing_range,
                        "Opposing BOS close above range high",
                        event.break_price,
                    )

        if self._config.invalidate_on_choch:
            for event in structure.choch_events:
                if event.bar_index < dealing_range.formation_bar_index:
                    continue
                if (
                    event.direction is CHoCHDirection.BEARISH
                    and latest.close < dealing_range.low
                ):
                    return self._invalidate(
                        dealing_range,
                        "Counter-trend CHoCH below range low",
                        latest.close,
                    )
                if (
                    event.direction is CHoCHDirection.BULLISH
                    and latest.close > dealing_range.high
                ):
                    return self._invalidate(
                        dealing_range,
                        "Counter-trend CHoCH above range high",
                        latest.close,
                    )

        return dealing_range

    def classify_price(
        self,
        price: Decimal,
        dealing_range: DealingRange,
    ) -> PremiumDiscountZone:
        """Classify price location relative to dealing range equilibrium."""
        if not dealing_range.is_valid:
            return PremiumDiscountZone.EQUILIBRIUM

        tolerance = self._config.equilibrium_tolerance_price
        if price > dealing_range.equilibrium + tolerance:
            return PremiumDiscountZone.PREMIUM
        if price < dealing_range.equilibrium - tolerance:
            return PremiumDiscountZone.DISCOUNT
        return PremiumDiscountZone.EQUILIBRIUM

    def build_zones(
        self,
        dealing_range: DealingRange,
    ) -> tuple[PriceZoneBand, PriceZoneBand, EquilibriumLevel]:
        """Build premium, discount, and equilibrium bands from dealing range."""
        tolerance = self._config.equilibrium_tolerance_price
        equilibrium = EquilibriumLevel(
            price=dealing_range.equilibrium,
            tolerance_high=dealing_range.equilibrium + tolerance,
            tolerance_low=dealing_range.equilibrium - tolerance,
            scope=dealing_range.scope,
        )
        premium = PriceZoneBand(
            territory=PremiumDiscountZone.PREMIUM,
            high=dealing_range.high,
            low=dealing_range.equilibrium + tolerance,
            scope=dealing_range.scope,
        )
        discount = PriceZoneBand(
            territory=PremiumDiscountZone.DISCOUNT,
            high=dealing_range.equilibrium - tolerance,
            low=dealing_range.low,
            scope=dealing_range.scope,
        )
        return premium, discount, equilibrium

    def detect_territory_events(
        self,
        *,
        current_price: Decimal,
        current_location: PremiumDiscountZone,
        prior_location: PremiumDiscountZone,
        dealing_range: DealingRange,
        timeframe: str,
        timestamp,
    ) -> list[PremiumDiscountEvent]:
        """Detect territory transition events vs prior state."""
        if current_location == prior_location:
            return []

        events: list[PremiumDiscountEvent] = []
        if current_location is PremiumDiscountZone.PREMIUM:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.PREMIUM_ZONE_ENTERED,
                    timestamp_utc=timestamp,
                    timeframe=timeframe,
                    description="Price entered premium territory",
                    range_id=dealing_range.range_id,
                    price=current_price,
                    territory=PremiumDiscountZone.PREMIUM,
                ),
            )
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.PREMIUM_DETECTED,
                    timestamp_utc=timestamp,
                    timeframe=timeframe,
                    description="Premium territory detected",
                    range_id=dealing_range.range_id,
                    price=current_price,
                    territory=PremiumDiscountZone.PREMIUM,
                ),
            )
        elif current_location is PremiumDiscountZone.DISCOUNT:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.DISCOUNT_ZONE_ENTERED,
                    timestamp_utc=timestamp,
                    timeframe=timeframe,
                    description="Price entered discount territory",
                    range_id=dealing_range.range_id,
                    price=current_price,
                    territory=PremiumDiscountZone.DISCOUNT,
                ),
            )
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.DISCOUNT_DETECTED,
                    timestamp_utc=timestamp,
                    timeframe=timeframe,
                    description="Discount territory detected",
                    range_id=dealing_range.range_id,
                    price=current_price,
                    territory=PremiumDiscountZone.DISCOUNT,
                ),
            )
        else:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.EQUILIBRIUM_REACHED,
                    timestamp_utc=timestamp,
                    timeframe=timeframe,
                    description="Price reached equilibrium band",
                    range_id=dealing_range.range_id,
                    price=current_price,
                    territory=PremiumDiscountZone.EQUILIBRIUM,
                ),
            )
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.EQUILIBRIUM_CALCULATED,
                    timestamp_utc=timestamp,
                    timeframe=timeframe,
                    description="Equilibrium band calculated",
                    range_id=dealing_range.range_id,
                    price=current_price,
                    territory=PremiumDiscountZone.EQUILIBRIUM,
                ),
            )

        if prior_location is PremiumDiscountZone.PREMIUM and current_location is not PremiumDiscountZone.PREMIUM:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.PREMIUM_EXPIRED,
                    timestamp_utc=timestamp,
                    timeframe=timeframe,
                    description="Price exited premium territory",
                    range_id=dealing_range.range_id,
                    price=current_price,
                ),
            )
        if prior_location is PremiumDiscountZone.DISCOUNT and current_location is not PremiumDiscountZone.DISCOUNT:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.DISCOUNT_EXPIRED,
                    timestamp_utc=timestamp,
                    timeframe=timeframe,
                    description="Price exited discount territory",
                    range_id=dealing_range.range_id,
                    price=current_price,
                ),
            )

        return events

    def merge_primary_range(
        self,
        external_range: DealingRange,
        internal_range: DealingRange,
    ) -> DealingRange:
        """Select primary dealing range per configuration."""
        mode = self._config.primary_range_mode
        if mode == "internal":
            return internal_range.model_copy(update={"scope": DealingRangeScope.PRIMARY})
        if mode == "external":
            return external_range.model_copy(update={"scope": DealingRangeScope.PRIMARY})

        external_score = external_range.strength if external_range.is_valid else Decimal("-1")
        internal_score = internal_range.strength if internal_range.is_valid else Decimal("-1")
        if internal_score > external_score:
            return internal_range.model_copy(update={"scope": DealingRangeScope.PRIMARY})
        return external_range.model_copy(update={"scope": DealingRangeScope.PRIMARY})

    @staticmethod
    def _invalidate(
        dealing_range: DealingRange,
        reason: str,
        price: Decimal,
    ) -> DealingRange:
        return dealing_range.model_copy(
            update={
                "is_valid": False,
                "invalidation_reason": reason,
                "evidence": dealing_range.evidence + [f"{reason} at {price}"],
            },
        )
