"""Event publisher for the Breaker Block Engine."""

from collections import defaultdict
from collections.abc import Callable

from backend.engines.market_breaker.events import BreakerBlockAnalysisEvent
from backend.engines.market_breaker.schemas import BreakerBlock, BreakerBlockAnalysis

EventHandler = Callable[[BreakerBlockAnalysisEvent], None]


class BreakerBlockEventPublisher:
    """Publish breaker block contract events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: BreakerBlockAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_breaker_detected(self, breaker: BreakerBlock, symbol: str) -> None:
        payload = self._breaker_payload(breaker)
        self.publish(
            BreakerBlockAnalysisEvent(
                "BreakerBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_bullish_breaker(self, breaker: BreakerBlock, symbol: str) -> None:
        payload = self._breaker_payload(breaker)
        self.publish(
            BreakerBlockAnalysisEvent(
                "BullishBreakerBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.bullish_detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_bearish_breaker(self, breaker: BreakerBlock, symbol: str) -> None:
        payload = self._breaker_payload(breaker)
        self.publish(
            BreakerBlockAnalysisEvent(
                "BearishBreakerBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.bearish_detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_candidate_breaker(self, breaker: BreakerBlock, symbol: str) -> None:
        payload = self._breaker_payload(breaker)
        self.publish(
            BreakerBlockAnalysisEvent(
                "CandidateBreakerBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.candidate",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_confirmed_breaker(self, breaker: BreakerBlock, symbol: str) -> None:
        payload = self._breaker_payload(breaker)
        if breaker.confirmation_bar_index is not None:
            payload["confirmation_bar_index"] = breaker.confirmation_bar_index
        if breaker.confirmation_time_utc is not None:
            payload["confirmation_time_utc"] = breaker.confirmation_time_utc.isoformat()
        payload["confirmation_reason"] = breaker.confirmation_reason
        payload["confirmation_mode"] = "configured"
        timestamp = breaker.confirmation_time_utc or breaker.formation_time_utc
        self.publish(
            BreakerBlockAnalysisEvent(
                "ConfirmedBreakerBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=timestamp,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.confirmed",
                symbol=symbol,
                payload=payload,
                timestamp_utc=timestamp,
            ),
        )

    def publish_mitigated_breaker(self, breaker: BreakerBlock, symbol: str) -> None:
        payload = self._breaker_payload(breaker)
        if breaker.mitigation_bar_index is not None:
            payload["mitigation_bar_index"] = breaker.mitigation_bar_index
        self.publish(
            BreakerBlockAnalysisEvent(
                "MitigatedBreakerBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.mitigated",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_invalidated_breaker(self, breaker: BreakerBlock, symbol: str) -> None:
        payload = self._breaker_payload(breaker)
        if breaker.invalidation_breaker_bar_index is not None:
            payload["invalidation_breaker_bar_index"] = breaker.invalidation_breaker_bar_index
        self.publish(
            BreakerBlockAnalysisEvent(
                "InvalidatedBreakerBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.invalidated",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_expired_breaker(self, breaker: BreakerBlock, symbol: str) -> None:
        payload = self._breaker_payload(breaker)
        if breaker.expiration_bar_index is not None:
            payload["expiration_bar_index"] = breaker.expiration_bar_index
            payload["age_bars"] = breaker.expiration_bar_index - breaker.formation_bar_index
        self.publish(
            BreakerBlockAnalysisEvent(
                "ExpiredBreakerBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.expired",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_liquidity_confluence(
        self,
        breaker: BreakerBlock,
        symbol: str,
        *,
        timeframe: str | None = None,
    ) -> None:
        payload = {
            "breaker_id": breaker.breaker_id,
            "direction": breaker.direction.value,
            "liquidity_confluence": True,
            "liquidity_confluence_ids": breaker.liquidity_confluence_ids,
            "timeframe": timeframe,
        }
        self.publish(
            BreakerBlockAnalysisEvent(
                "LiquidityConfluenceBreaker",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.liquidity_confluence",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_fvg_confluence(
        self,
        breaker: BreakerBlock,
        symbol: str,
        *,
        timeframe: str | None = None,
    ) -> None:
        payload = {
            "breaker_id": breaker.breaker_id,
            "direction": breaker.direction.value,
            "fvg_confluence": True,
            "fvg_confluence_ids": breaker.fvg_confluence_ids,
            "timeframe": timeframe,
        }
        self.publish(
            BreakerBlockAnalysisEvent(
                "FVGConfluenceBreaker",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.fvg_confluence",
                symbol=symbol,
                payload=payload,
                timestamp_utc=breaker.formation_time_utc,
            ),
        )

    def publish_analysis_completed(self, analysis: BreakerBlockAnalysis) -> None:
        summary_payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "timestamp_utc": analysis.timestamp_utc.isoformat(),
            "breaker_count": len(analysis.breaker_blocks),
            "candidate_count": len(analysis.candidate_breakers),
            "confirmed_count": len(analysis.confirmed_breakers),
            "mitigated_count": len(analysis.mitigated_breakers),
            "invalidated_count": len(analysis.invalidated_breakers),
            "expired_count": len(analysis.expired_breakers),
            "bias": analysis.bias.value,
            "confidence": str(analysis.confidence),
            "evidence": analysis.evidence,
        }
        self.publish(
            BreakerBlockAnalysisEvent(
                "BreakerBlockUpdated",
                symbol=analysis.symbol,
                payload=summary_payload,
                timestamp_utc=analysis.timestamp_utc,
            ),
        )
        self.publish(
            BreakerBlockAnalysisEvent(
                "analysis.breaker.completed",
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
            BreakerBlockAnalysisEvent(
                "analysis.breaker.error",
                symbol=symbol,
                payload={
                    "error_code": code,
                    "message": message,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "details": details or {},
                },
            ),
        )

    def clear_handlers(self) -> None:
        self._handlers.clear()

    @staticmethod
    def _breaker_payload(breaker: BreakerBlock) -> dict[str, str | int | bool | None]:
        return {
            "breaker_id": breaker.breaker_id,
            "direction": breaker.direction.value,
            "status": breaker.status.value,
            "high": str(breaker.high),
            "low": str(breaker.low),
            "source_type": breaker.source_type.value,
            "source_id": breaker.source_id,
            "source_direction": breaker.source_direction,
            "invalidation_bar_index": breaker.invalidation_bar_index,
            "invalidation_time_utc": breaker.invalidation_time_utc.isoformat(),
            "formation_bar_index": breaker.formation_bar_index,
            "formation_time_utc": breaker.formation_time_utc.isoformat(),
            "is_confirmed": breaker.is_confirmed,
            "confirmation_reason": breaker.confirmation_reason,
            "quality": breaker.quality.value,
            "strength": str(breaker.strength),
            "structure_alignment": breaker.structure_alignment,
            "liquidity_confluence": breaker.liquidity_confluence,
            "fvg_confluence": breaker.fvg_confluence,
            "premium_discount": breaker.premium_discount.value,
        }
