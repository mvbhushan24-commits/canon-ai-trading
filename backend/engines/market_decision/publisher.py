"""Event publisher for the Market Decision Engine."""

from collections import defaultdict
from collections.abc import Callable

from backend.engines.market_decision.events import DecisionAnalysisEvent
from backend.engines.market_decision.schemas import DecisionState, TradeDecision

EventHandler = Callable[[DecisionAnalysisEvent], None]


class DecisionEventPublisher:
    """Publish decision lifecycle events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DecisionAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_decision_created(self, decision: TradeDecision) -> None:
        payload = {
            "decision_id": decision.decision_id,
            "symbol": decision.symbol,
            "timestamp_utc": decision.timestamp_utc.isoformat(),
            "state": decision.state.value,
            "direction": decision.direction.value,
            "confidence": decision.confidence,
            "quality_score": decision.quality_score,
            "quality_tier": decision.quality_tier.value,
            "engines_available": decision.metadata.engines_available,
            "engines_stale": decision.metadata.engines_stale,
        }
        self.publish(
            DecisionAnalysisEvent(
                "DecisionCreated",
                symbol=decision.symbol,
                payload=payload,
                timestamp_utc=decision.timestamp_utc,
            ),
        )
        self.publish(
            DecisionAnalysisEvent(
                "decision.completed",
                symbol=decision.symbol,
                payload=payload,
                timestamp_utc=decision.timestamp_utc,
            ),
        )

    def publish_decision_published(self, decision: TradeDecision) -> None:
        payload = decision.model_dump(mode="json")
        self.publish(
            DecisionAnalysisEvent(
                "DecisionPublished",
                symbol=decision.symbol,
                payload=payload,
                timestamp_utc=decision.timestamp_utc,
            ),
        )
        self.publish(
            DecisionAnalysisEvent(
                "decision.signal.published",
                symbol=decision.symbol,
                payload=payload,
                timestamp_utc=decision.timestamp_utc,
            ),
        )

    def publish_decision_rejected(self, decision: TradeDecision) -> None:
        payload = {
            "decision_id": decision.decision_id,
            "symbol": decision.symbol,
            "timestamp_utc": decision.timestamp_utc.isoformat(),
            "state": decision.state.value,
            "direction": decision.direction.value,
            "confidence": decision.confidence,
            "blocking_reasons": decision.blocking_reasons,
            "error_codes": decision.error_codes,
            "evidence_summary": [
                item.model_dump(mode="json") for item in decision.evidence_summary
            ],
            "warnings": decision.warnings,
        }
        self.publish(
            DecisionAnalysisEvent(
                "DecisionRejected",
                symbol=decision.symbol,
                payload=payload,
                timestamp_utc=decision.timestamp_utc,
            ),
        )
        if decision.state is DecisionState.NO_TRADE:
            self.publish(
                DecisionAnalysisEvent(
                    "decision.no_trade.published",
                    symbol=decision.symbol,
                    payload=payload,
                    timestamp_utc=decision.timestamp_utc,
                ),
            )
        elif decision.state is DecisionState.INVALID:
            self.publish(
                DecisionAnalysisEvent(
                    "decision.error",
                    symbol=decision.symbol,
                    payload={**payload, "source": "market_decision"},
                    timestamp_utc=decision.timestamp_utc,
                ),
            )

    def publish_decision_updated(
        self,
        prior: TradeDecision,
        current: TradeDecision,
        reason: str,
    ) -> None:
        payload = {
            "prior_decision_id": prior.decision_id,
            "decision_id": current.decision_id,
            "symbol": current.symbol,
            "timestamp_utc": current.timestamp_utc.isoformat(),
            "prior_state": prior.state.value,
            "current_state": current.state.value,
            "update_reason": reason,
            "confidence_delta": current.confidence - prior.confidence,
        }
        self.publish(
            DecisionAnalysisEvent(
                "DecisionUpdated",
                symbol=current.symbol,
                payload=payload,
                timestamp_utc=current.timestamp_utc,
            ),
        )
        self.publish(
            DecisionAnalysisEvent(
                "decision.updated",
                symbol=current.symbol,
                payload=payload,
                timestamp_utc=current.timestamp_utc,
            ),
        )

    def publish_decision_expired(self, decision: TradeDecision) -> None:
        payload = {
            "decision_id": decision.decision_id,
            "symbol": decision.symbol,
            "original_state": decision.state.value,
            "direction": decision.direction.value,
            "created_at_utc": decision.timestamp_utc.isoformat(),
            "expired_at_utc": decision.valid_until_utc.isoformat()
            if decision.valid_until_utc
            else None,
            "validity_minutes": None,
        }
        self.publish(
            DecisionAnalysisEvent(
                "DecisionExpired",
                symbol=decision.symbol,
                payload=payload,
                timestamp_utc=decision.valid_until_utc,
            ),
        )
        self.publish(
            DecisionAnalysisEvent(
                "decision.expired",
                symbol=decision.symbol,
                payload=payload,
                timestamp_utc=decision.valid_until_utc,
            ),
        )

    def clear_handlers(self) -> None:
        self._handlers.clear()
