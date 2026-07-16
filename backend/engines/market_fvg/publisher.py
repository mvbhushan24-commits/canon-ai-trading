"""Event publisher for Fair Value Gap Engine."""

from collections import defaultdict
from collections.abc import Callable

from backend.engines.market_fvg.events import FairValueGapAnalysisEvent
from backend.engines.market_fvg.schemas import FairValueGap, FairValueGapAnalysis, MTFGapAlignment

EventHandler = Callable[[FairValueGapAnalysisEvent], None]


class FairValueGapEventPublisher:
    """Publish fair value gap contract events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: FairValueGapAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_gap_detected(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        self.publish(
            FairValueGapAnalysisEvent(
                "FairValueGapDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_bullish_gap(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        self.publish(
            FairValueGapAnalysisEvent(
                "BullishFairValueGapDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.bullish_detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_bearish_gap(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        self.publish(
            FairValueGapAnalysisEvent(
                "BearishFairValueGapDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.bearish_detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_open_gap(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        self.publish(
            FairValueGapAnalysisEvent(
                "OpenFairValueGap",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.open",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_partial_fill(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        payload["fill_percent"] = str(gap.fill_percent)
        self.publish(
            FairValueGapAnalysisEvent(
                "PartialFillFairValueGap",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.partial_fill",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_filled(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        payload["fill_percent"] = str(gap.fill_percent)
        if gap.fill_bar_index is not None:
            payload["fill_bar_index"] = gap.fill_bar_index
        self.publish(
            FairValueGapAnalysisEvent(
                "FilledFairValueGap",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.filled",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_mitigated(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        payload["mitigation_mode"] = "configured"
        if gap.mitigation_bar_index is not None:
            payload["mitigation_bar_index"] = gap.mitigation_bar_index
        payload["mitigation_price"] = str(gap.ce_price)
        self.publish(
            FairValueGapAnalysisEvent(
                "MitigatedFairValueGap",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.mitigated",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_invalidated(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        if gap.invalidation_bar_index is not None:
            payload["invalidation_bar_index"] = gap.invalidation_bar_index
        self.publish(
            FairValueGapAnalysisEvent(
                "InvalidatedFairValueGap",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.invalidated",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_expired(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        if gap.expiration_bar_index is not None:
            payload["expiration_bar_index"] = gap.expiration_bar_index
        self.publish(
            FairValueGapAnalysisEvent(
                "ExpiredFairValueGap",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.expired",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_ce_encroached(self, gap: FairValueGap, symbol: str) -> None:
        payload = self._gap_payload(gap)
        payload["ce_price"] = str(gap.ce_price)
        payload["fill_percent"] = str(gap.fill_percent)
        payload["gap_status"] = gap.status.value
        self.publish(
            FairValueGapAnalysisEvent(
                "CEEncroached",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.ce_encroached",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_nested(
        self,
        *,
        child: FairValueGap,
        parent: FairValueGap,
        symbol: str,
        timeframe: str,
    ) -> None:
        payload = {
            "child_gap_id": child.gap_id,
            "parent_gap_id": parent.gap_id,
            "child_high": str(child.high),
            "child_low": str(child.low),
            "parent_high": str(parent.high),
            "parent_low": str(parent.low),
            "timeframe": timeframe,
        }
        self.publish(
            FairValueGapAnalysisEvent(
                "NestedFairValueGap",
                symbol=symbol,
                payload=payload,
                timestamp_utc=child.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.nested",
                symbol=symbol,
                payload=payload,
                timestamp_utc=child.origin_time_utc,
            ),
        )

    def publish_mtf_aligned(
        self,
        gap: FairValueGap,
        alignment: MTFGapAlignment,
        symbol: str,
    ) -> None:
        payload = {
            "gap_id": gap.gap_id,
            "direction": gap.direction.value,
            "aligned_timeframes": alignment.aligned_timeframes,
            "alignment_direction": alignment.alignment_direction.value,
            "alignment_score": str(alignment.alignment_score),
            "parent_timeframe": alignment.parent_timeframe,
            "parent_gap_id": alignment.parent_gap_id,
        }
        self.publish(
            FairValueGapAnalysisEvent(
                "MTFAlignedFairValueGap",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.mtf_aligned",
                symbol=symbol,
                payload=payload,
                timestamp_utc=gap.origin_time_utc,
            ),
        )

    def publish_analysis_completed(self, analysis: FairValueGapAnalysis) -> None:
        self.publish(
            FairValueGapAnalysisEvent(
                "FairValueGapUpdated",
                symbol=analysis.symbol,
                payload=analysis.model_dump(mode="json"),
                timestamp_utc=analysis.timestamp_utc,
            ),
        )
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.completed",
                symbol=analysis.symbol,
                payload=analysis.model_dump(mode="json"),
                timestamp_utc=analysis.timestamp_utc,
            ),
        )

    def publish_error(
        self,
        *,
        symbol: str | None,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
        timeframe: str | None = None,
    ) -> None:
        self.publish(
            FairValueGapAnalysisEvent(
                "analysis.fvg.error",
                symbol=symbol,
                payload={
                    "error_code": code,
                    "message": message,
                    "details": details or {},
                    "timeframe": timeframe,
                },
            ),
        )

    def clear_handlers(self) -> None:
        self._handlers.clear()

    @staticmethod
    def _gap_payload(gap: FairValueGap) -> dict[str, str | int | bool | None]:
        return {
            "gap_id": gap.gap_id,
            "direction": gap.direction.value,
            "status": gap.status.value,
            "high": str(gap.high),
            "low": str(gap.low),
            "ce_price": str(gap.ce_price),
            "gap_size": str(gap.gap_size),
            "gap_size_pips": str(gap.gap_size_pips),
            "fill_percent": str(gap.fill_percent),
            "origin_time_utc": gap.origin_time_utc.isoformat(),
            "origin_bar_index": gap.origin_bar_index,
            "candle_a_index": gap.candle_a_index,
            "candle_b_index": gap.candle_b_index,
            "candle_c_index": gap.candle_c_index,
            "quality": gap.quality.value,
            "strength": str(gap.strength),
            "premium_discount": gap.premium_discount.value,
            "structure_alignment": gap.structure_alignment,
            "liquidity_confluence": gap.liquidity_confluence,
            "order_block_confluence": gap.order_block_confluence,
        }
