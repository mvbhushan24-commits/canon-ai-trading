"""Event publisher for Order Block Engine."""

from collections import defaultdict
from collections.abc import Callable

from backend.engines.market_order_block.events import OrderBlockAnalysisEvent
from backend.engines.market_order_block.schemas import OrderBlock, OrderBlockAnalysis

EventHandler = Callable[[OrderBlockAnalysisEvent], None]


class OrderBlockEventPublisher:
    """Publish order block contract events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: OrderBlockAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_block_detected(self, block: OrderBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            OrderBlockAnalysisEvent(
                "OrderBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )
        self.publish(
            OrderBlockAnalysisEvent(
                "analysis.order_block.detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )

    def publish_bullish_block(self, block: OrderBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            OrderBlockAnalysisEvent(
                "BullishOrderBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )
        self.publish(
            OrderBlockAnalysisEvent(
                "analysis.order_block.bullish_detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )

    def publish_bearish_block(self, block: OrderBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            OrderBlockAnalysisEvent(
                "BearishOrderBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )
        self.publish(
            OrderBlockAnalysisEvent(
                "analysis.order_block.bearish_detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )

    def publish_fresh_block(self, block: OrderBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            OrderBlockAnalysisEvent(
                "FreshOrderBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )
        self.publish(
            OrderBlockAnalysisEvent(
                "analysis.order_block.fresh",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )

    def publish_mitigated_block(self, block: OrderBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        if block.mitigation_bar_index is not None:
            payload["mitigation_bar_index"] = block.mitigation_bar_index
        self.publish(
            OrderBlockAnalysisEvent(
                "MitigatedOrderBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )
        self.publish(
            OrderBlockAnalysisEvent(
                "analysis.order_block.mitigated",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )

    def publish_invalidated_block(self, block: OrderBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        if block.invalidation_bar_index is not None:
            payload["invalidation_bar_index"] = block.invalidation_bar_index
        self.publish(
            OrderBlockAnalysisEvent(
                "InvalidatedOrderBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )
        self.publish(
            OrderBlockAnalysisEvent(
                "analysis.order_block.invalidated",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.origin_time_utc,
            ),
        )

    def publish_analysis_completed(self, analysis: OrderBlockAnalysis) -> None:
        self.publish(
            OrderBlockAnalysisEvent(
                "OrderBlockUpdated",
                symbol=analysis.symbol,
                payload=analysis.model_dump(mode="json"),
                timestamp_utc=analysis.timestamp_utc,
            ),
        )
        self.publish(
            OrderBlockAnalysisEvent(
                "analysis.order_block.completed",
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
    ) -> None:
        self.publish(
            OrderBlockAnalysisEvent(
                "analysis.order_block.error",
                symbol=symbol,
                payload={
                    "code": code,
                    "message": message,
                    "details": details or {},
                },
            ),
        )

    def clear_handlers(self) -> None:
        self._handlers.clear()

    @staticmethod
    def _block_payload(block: OrderBlock) -> dict[str, str | int | None]:
        return {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "status": block.status.value,
            "high": str(block.high),
            "low": str(block.low),
            "origin_time_utc": block.origin_time_utc.isoformat(),
            "origin_bar_index": block.origin_bar_index,
            "quality": block.quality.value,
            "strength": str(block.strength),
        }
