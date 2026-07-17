"""Event publisher for the Mitigation Block Engine."""

from collections import defaultdict
from collections.abc import Callable

from backend.engines.market_mitigation.events import MitigationBlockAnalysisEvent
from backend.engines.market_mitigation.schemas import MitigationBlock, MitigationBlockAnalysis

EventHandler = Callable[[MitigationBlockAnalysisEvent], None]


class MitigationBlockEventPublisher:
    """Publish mitigation block contract events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: MitigationBlockAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_block_detected(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            MitigationBlockAnalysisEvent(
                "MitigationBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_bullish_block(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            MitigationBlockAnalysisEvent(
                "BullishMitigationBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.bullish_detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_bearish_block(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            MitigationBlockAnalysisEvent(
                "BearishMitigationBlockDetected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.bearish_detected",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_fresh_block(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            MitigationBlockAnalysisEvent(
                "FreshMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.fresh",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_partial_mitigation(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            MitigationBlockAnalysisEvent(
                "PartialMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.partial",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_full_mitigation(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            MitigationBlockAnalysisEvent(
                "FullMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.full",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_multi_touch(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        self.publish(
            MitigationBlockAnalysisEvent(
                "MultiTouchMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.multi_touch",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_confirmed(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        if block.confirmation_bar_index is not None:
            payload["confirmation_bar_index"] = block.confirmation_bar_index
        if block.confirmation_time_utc is not None:
            payload["confirmation_time_utc"] = block.confirmation_time_utc.isoformat()
        payload["confirmation_reason"] = block.confirmation_reason
        timestamp = block.confirmation_time_utc or block.formation_time_utc
        self.publish(
            MitigationBlockAnalysisEvent(
                "ConfirmedMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=timestamp,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.confirmed",
                symbol=symbol,
                payload=payload,
                timestamp_utc=timestamp,
            ),
        )

    def publish_used(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        if block.used_bar_index is not None:
            payload["used_bar_index"] = block.used_bar_index
        self.publish(
            MitigationBlockAnalysisEvent(
                "UsedMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.used",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_invalidated(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        if block.invalidation_bar_index is not None:
            payload["invalidation_bar_index"] = block.invalidation_bar_index
        self.publish(
            MitigationBlockAnalysisEvent(
                "InvalidatedMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.invalidated",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_expired(self, block: MitigationBlock, symbol: str) -> None:
        payload = self._block_payload(block)
        if block.expiration_bar_index is not None:
            payload["expiration_bar_index"] = block.expiration_bar_index
            payload["age_bars"] = block.expiration_bar_index - block.formation_bar_index
        self.publish(
            MitigationBlockAnalysisEvent(
                "ExpiredMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.expired",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_nested(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "is_nested": True,
            "parent_zone_id": block.parent_zone_id,
            "parent_zone_type": (
                block.parent_zone_type.value if block.parent_zone_type else None
            ),
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "NestedMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.nested",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_internal_scope(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "structure_scope": block.structure_scope.value,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "InternalMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.internal",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_external_scope(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "structure_scope": block.structure_scope.value,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "ExternalMitigationBlock",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.external",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_htf_aligned(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "htf_aligned": True,
            "htf_block_ids": block.htf_block_ids,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "HTFMitigationAligned",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.htf_aligned",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_ltf_nested(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "ltf_nested": True,
            "ltf_block_ids": block.ltf_block_ids,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "LTFMitigationNested",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.ltf_nested",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_liquidity_confluence(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "liquidity_confluence": True,
            "confluence_ids": block.confluence_ids,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "LiquidityConfluenceMitigation",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.liquidity_confluence",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_ob_confluence(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "order_block_confluence": True,
            "confluence_ids": block.confluence_ids,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "OrderBlockConfluenceMitigation",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.ob_confluence",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_fvg_confluence(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "fvg_confluence": True,
            "confluence_ids": block.confluence_ids,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "FVGConfluenceMitigation",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.fvg_confluence",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_breaker_confluence(self, block: MitigationBlock, symbol: str) -> None:
        payload = {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "breaker_confluence": True,
            "confluence_ids": block.confluence_ids,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "BreakerConfluenceMitigation",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.breaker_confluence",
                symbol=symbol,
                payload=payload,
                timestamp_utc=block.formation_time_utc,
            ),
        )

    def publish_analysis_completed(self, analysis: MitigationBlockAnalysis) -> None:
        summary_payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "timestamp_utc": analysis.timestamp_utc.isoformat(),
            "block_count": len(analysis.mitigation_blocks),
            "fresh_count": len(analysis.fresh_blocks),
            "partial_count": len(analysis.partial_blocks),
            "confirmed_count": len(analysis.confirmed_blocks),
            "used_count": len(analysis.used_blocks),
            "invalidated_count": len(analysis.invalidated_blocks),
            "expired_count": len(analysis.expired_blocks),
            "nested_count": len(analysis.nested_blocks),
            "htf_aligned_count": len(analysis.htf_aligned_blocks),
            "bias": analysis.bias.value,
            "confidence": str(analysis.confidence),
            "evidence": analysis.evidence,
        }
        self.publish(
            MitigationBlockAnalysisEvent(
                "MitigationBlockUpdated",
                symbol=analysis.symbol,
                payload=summary_payload,
                timestamp_utc=analysis.timestamp_utc,
            ),
        )
        self.publish(
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.completed",
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
            MitigationBlockAnalysisEvent(
                "analysis.mitigation.error",
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
    def _block_payload(block: MitigationBlock) -> dict[str, str | int | bool | None]:
        return {
            "block_id": block.block_id,
            "direction": block.direction.value,
            "status": block.status.value,
            "high": str(block.high),
            "low": str(block.low),
            "origin_bar_index": block.origin_bar_index,
            "origin_time_utc": block.origin_time_utc.isoformat(),
            "displacement_bar_index": block.displacement_bar_index,
            "displacement_time_utc": block.displacement_time_utc.isoformat(),
            "formation_bar_index": block.formation_bar_index,
            "formation_time_utc": block.formation_time_utc.isoformat(),
            "mitigation_percent": str(block.mitigation_percent),
            "touch_count": block.touch_count,
            "is_confirmed": block.is_confirmed,
            "confirmation_reason": block.confirmation_reason,
            "structure_scope": block.structure_scope.value,
            "structure_alignment": block.structure_alignment,
            "liquidity_confluence": block.liquidity_confluence,
            "order_block_confluence": block.order_block_confluence,
            "fvg_confluence": block.fvg_confluence,
            "breaker_confluence": block.breaker_confluence,
            "is_nested": block.is_nested,
            "parent_zone_id": block.parent_zone_id,
            "parent_zone_type": (
                block.parent_zone_type.value if block.parent_zone_type else None
            ),
            "htf_aligned": block.htf_aligned,
            "quality": block.quality.value,
            "strength": str(block.strength),
            "premium_discount": block.premium_discount.value,
        }
