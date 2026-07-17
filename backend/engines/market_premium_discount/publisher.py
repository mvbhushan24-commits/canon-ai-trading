"""Event publisher for the Premium / Discount Engine."""

from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from backend.engines.market_premium_discount.events import PremiumDiscountAnalysisEvent
from backend.engines.market_premium_discount.schemas import (
    DealingRange,
    FibonacciDealingRange,
    HTFPricingContext,
    InstitutionalArray,
    InstitutionalPricingContext,
    MTFPremiumDiscountAlignment,
    NestedZoneContext,
    OptimalTradeEntryZone,
    PremiumDiscountAnalysis,
    PriceZoneBand,
    SwingAnchor,
)

EventHandler = Callable[[PremiumDiscountAnalysisEvent], None]


class PremiumDiscountEventPublisher:
    """Publish premium / discount contract events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: PremiumDiscountAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_error(
        self,
        *,
        symbol: str | None,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        timeframe: str | None = None,
    ) -> None:
        payload = {
            "code": code,
            "message": message,
            "details": details or {},
            "timeframe": timeframe,
        }
        self.publish(
            PremiumDiscountAnalysisEvent(
                "analysis.premium_discount.error",
                symbol=symbol,
                payload=payload,
            ),
        )

    def publish_dealing_range_established(
        self,
        dealing_range: DealingRange,
        symbol: str,
    ) -> None:
        self._publish_dual(
            "DealingRangeEstablished",
            "analysis.premium_discount.dealing_range_established",
            symbol,
            self._range_payload(dealing_range),
            dealing_range.formation_time_utc,
        )

    def publish_dealing_range_updated(
        self,
        dealing_range: DealingRange,
        symbol: str,
        *,
        previous_high: Decimal | None = None,
        update_reason: str | None = None,
    ) -> None:
        payload = self._range_payload(dealing_range)
        if previous_high is not None:
            payload["previous_high"] = str(previous_high)
        if update_reason:
            payload["update_reason"] = update_reason
        self._publish_dual(
            "DealingRangeUpdated",
            "analysis.premium_discount.dealing_range_updated",
            symbol,
            payload,
            dealing_range.formation_time_utc,
        )

    def publish_dealing_range_invalidated(
        self,
        dealing_range: DealingRange,
        symbol: str,
    ) -> None:
        payload = self._range_payload(dealing_range)
        payload["invalidation_reason"] = dealing_range.invalidation_reason
        self._publish_dual(
            "DealingRangeInvalidated",
            "analysis.premium_discount.dealing_range_invalidated",
            symbol,
            payload,
            dealing_range.formation_time_utc,
        )

    def publish_swing_high_anchored(self, anchor: SwingAnchor, symbol: str) -> None:
        self._publish_dual(
            "SwingHighAnchored",
            "analysis.premium_discount.swing_high_anchored",
            symbol,
            self._swing_payload(anchor),
            anchor.timestamp_utc,
        )

    def publish_swing_low_anchored(self, anchor: SwingAnchor, symbol: str) -> None:
        self._publish_dual(
            "SwingLowAnchored",
            "analysis.premium_discount.swing_low_anchored",
            symbol,
            self._swing_payload(anchor),
            anchor.timestamp_utc,
        )

    def publish_premium_entered(self, price: Decimal, symbol: str, *, range_id: str | None = None) -> None:
        payload = {"price": str(price), "range_id": range_id}
        self._publish_dual(
            "PremiumZoneEntered",
            "analysis.premium_discount.premium_entered",
            symbol,
            payload,
        )
        self._publish_dual(
            "PremiumDetected",
            "analysis.premium_discount.premium_detected",
            symbol,
            payload,
        )

    def publish_discount_entered(self, price: Decimal, symbol: str, *, range_id: str | None = None) -> None:
        payload = {"price": str(price), "range_id": range_id}
        self._publish_dual(
            "DiscountZoneEntered",
            "analysis.premium_discount.discount_entered",
            symbol,
            payload,
        )
        self._publish_dual(
            "DiscountDetected",
            "analysis.premium_discount.discount_detected",
            symbol,
            payload,
        )

    def publish_equilibrium_reached(
        self,
        price: Decimal,
        symbol: str,
        *,
        range_id: str | None = None,
    ) -> None:
        payload = {"price": str(price), "range_id": range_id}
        self._publish_dual(
            "EquilibriumReached",
            "analysis.premium_discount.equilibrium_reached",
            symbol,
            payload,
        )
        self._publish_dual(
            "EquilibriumCalculated",
            "analysis.premium_discount.equilibrium_calculated",
            symbol,
            payload,
        )

    def publish_premium_array(self, array: InstitutionalArray, symbol: str) -> None:
        self._publish_dual(
            "PremiumArrayFormed",
            "analysis.premium_discount.premium_array",
            symbol,
            self._array_payload(array),
        )

    def publish_discount_array(self, array: InstitutionalArray, symbol: str) -> None:
        self._publish_dual(
            "DiscountArrayFormed",
            "analysis.premium_discount.discount_array",
            symbol,
            self._array_payload(array),
        )

    def publish_internal_premium(self, band: PriceZoneBand, symbol: str) -> None:
        self._publish_dual(
            "InternalPremiumClassified",
            "analysis.premium_discount.internal_premium",
            symbol,
            self._band_payload(band),
        )

    def publish_internal_discount(self, band: PriceZoneBand, symbol: str) -> None:
        self._publish_dual(
            "InternalDiscountClassified",
            "analysis.premium_discount.internal_discount",
            symbol,
            self._band_payload(band),
        )

    def publish_htf_premium(self, context: HTFPricingContext, symbol: str) -> None:
        self._publish_dual(
            "HTFPremiumContext",
            "analysis.premium_discount.htf_premium",
            symbol,
            self._htf_payload(context),
        )

    def publish_htf_discount(self, context: HTFPricingContext, symbol: str) -> None:
        self._publish_dual(
            "HTFDiscountContext",
            "analysis.premium_discount.htf_discount",
            symbol,
            self._htf_payload(context),
        )

    def publish_mtf_premium_aligned(
        self,
        alignment: MTFPremiumDiscountAlignment,
        symbol: str,
    ) -> None:
        self._publish_dual(
            "MTFPremiumAligned",
            "analysis.premium_discount.mtf_premium_aligned",
            symbol,
            self._mtf_payload(alignment),
        )

    def publish_mtf_discount_aligned(
        self,
        alignment: MTFPremiumDiscountAlignment,
        symbol: str,
    ) -> None:
        self._publish_dual(
            "MTFDiscountAligned",
            "analysis.premium_discount.mtf_discount_aligned",
            symbol,
            self._mtf_payload(alignment),
        )

    def publish_nested_premium(self, context: NestedZoneContext, symbol: str) -> None:
        self._publish_dual(
            "NestedPremiumZone",
            "analysis.premium_discount.nested_premium",
            symbol,
            self._nested_payload(context),
        )

    def publish_nested_discount(self, context: NestedZoneContext, symbol: str) -> None:
        self._publish_dual(
            "NestedDiscountZone",
            "analysis.premium_discount.nested_discount",
            symbol,
            self._nested_payload(context),
        )

    def publish_fibonacci_computed(
        self,
        fibonacci: FibonacciDealingRange,
        symbol: str,
    ) -> None:
        payload = {
            "range_id": fibonacci.range_id,
            "direction": fibonacci.direction.value,
            "level_count": len(fibonacci.levels),
        }
        self._publish_dual(
            "FibonacciRangeComputed",
            "analysis.premium_discount.fibonacci_computed",
            symbol,
            payload,
        )

    def publish_ote_derived(self, ote: OptimalTradeEntryZone, symbol: str) -> None:
        payload = {
            "ote_id": ote.ote_id,
            "territory": ote.territory.value,
            "high": str(ote.high),
            "low": str(ote.low),
            "overlapping_zone_ids": ote.overlapping_zone_ids,
        }
        self._publish_dual(
            "OTEZoneDerived",
            "analysis.premium_discount.ote_derived",
            symbol,
            payload,
        )

    def publish_institutional_context(
        self,
        context: InstitutionalPricingContext,
        symbol: str,
    ) -> None:
        payload = {
            "narrative": context.narrative,
            "current_price_location": context.current_price_location.value,
            "confidence": str(context.confidence),
            "mtf_aligned": context.mtf_aligned,
            "ote_available": context.ote_available,
        }
        self._publish_dual(
            "InstitutionalContextUpdated",
            "analysis.premium_discount.context_updated",
            symbol,
            payload,
        )

    def publish_premium_expired(self, price: Decimal, symbol: str) -> None:
        self._publish_dual(
            "PremiumExpired",
            "analysis.premium_discount.premium_expired",
            symbol,
            {"price": str(price)},
        )

    def publish_discount_expired(self, price: Decimal, symbol: str) -> None:
        self._publish_dual(
            "DiscountExpired",
            "analysis.premium_discount.discount_expired",
            symbol,
            {"price": str(price)},
        )

    def publish_quality_updated(
        self,
        *,
        symbol: str,
        quality: str,
        strength: str,
        timestamp,
    ) -> None:
        payload = {"quality": quality, "strength": strength}
        self._publish_dual(
            "PremiumQualityUpdated",
            "analysis.premium_discount.quality_updated",
            symbol,
            payload,
            timestamp,
        )

    def publish_analysis_completed(self, analysis: PremiumDiscountAnalysis) -> None:
        payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "bias": analysis.bias.value,
            "quality": analysis.quality.value,
            "strength": str(analysis.strength),
            "confidence": str(analysis.confidence),
            "price_location": analysis.price_location.value,
            "dealing_range_id": analysis.dealing_range.range_id,
            "premium_array_count": len(analysis.premium_arrays),
            "discount_array_count": len(analysis.discount_arrays),
            "ote_available": analysis.ote_zone is not None,
        }
        self._publish_dual(
            "PremiumDiscountUpdated",
            "analysis.premium_discount.completed",
            analysis.symbol,
            payload,
            analysis.timestamp_utc,
        )

    def _publish_dual(
        self,
        event_type: str,
        contract_name: str,
        symbol: str,
        payload: dict[str, Any],
        timestamp=None,
    ) -> None:
        kwargs = {"symbol": symbol, "payload": payload}
        if timestamp is not None:
            kwargs["timestamp_utc"] = timestamp
        self.publish(PremiumDiscountAnalysisEvent(event_type, **kwargs))
        self.publish(PremiumDiscountAnalysisEvent(contract_name, **kwargs))

    @staticmethod
    def _range_payload(dealing_range: DealingRange) -> dict[str, Any]:
        return {
            "range_id": dealing_range.range_id,
            "scope": dealing_range.scope.value,
            "high": str(dealing_range.high),
            "low": str(dealing_range.low),
            "equilibrium": str(dealing_range.equilibrium),
            "range_size": str(dealing_range.range_size),
            "is_valid": dealing_range.is_valid,
            "quality": dealing_range.quality.value,
            "strength": str(dealing_range.strength),
        }

    @staticmethod
    def _swing_payload(anchor: SwingAnchor) -> dict[str, Any]:
        return {
            "price": str(anchor.price),
            "bar_index": anchor.bar_index,
            "kind": anchor.kind.value,
            "label": anchor.label.value,
            "quality_score": str(anchor.quality_score),
        }

    @staticmethod
    def _array_payload(array: InstitutionalArray) -> dict[str, Any]:
        return {
            "array_id": array.array_id,
            "territory": array.territory.value,
            "entry_count": array.entry_count,
            "cluster_high": str(array.cluster_high),
            "cluster_low": str(array.cluster_low),
            "confluence_score": str(array.confluence_score),
        }

    @staticmethod
    def _band_payload(band: PriceZoneBand) -> dict[str, Any]:
        return {
            "territory": band.territory.value,
            "high": str(band.high),
            "low": str(band.low),
            "scope": band.scope.value,
        }

    @staticmethod
    def _htf_payload(context: HTFPricingContext) -> dict[str, Any]:
        return {
            "timeframe": context.timeframe,
            "territory": context.territory.value,
            "array_count": context.array_count,
            "equilibrium": str(context.equilibrium),
        }

    @staticmethod
    def _mtf_payload(alignment: MTFPremiumDiscountAlignment) -> dict[str, Any]:
        return {
            "territory": alignment.territory.value,
            "alignment_score": str(alignment.alignment_score),
            "ltf_timeframe": alignment.ltf_timeframe,
            "htf_timeframe": alignment.htf_timeframe,
            "range_overlap_percent": str(alignment.range_overlap_percent),
            "array_overlap_count": alignment.array_overlap_count,
        }

    @staticmethod
    def _nested_payload(context: NestedZoneContext) -> dict[str, Any]:
        return {
            "child_zone_id": context.child_zone_id,
            "parent_zone_id": context.parent_zone_id,
            "territory": context.territory.value,
            "containment_percent": str(context.containment_percent),
        }
