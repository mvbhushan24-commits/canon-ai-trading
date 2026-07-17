"""Event publisher for the Market Signal Engine."""

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_signal.events import SignalAnalysisEvent
from backend.engines.market_signal.schemas import SignalRejection, SignalState, TradingSignal

EventHandler = Callable[[SignalAnalysisEvent], None]

CONTRACT_EVENT_MAP = {
    "SignalCreated": "signal.created",
    "SignalActivated": "signal.activated",
    "SignalTriggered": "signal.triggered",
    "SignalExpired": "signal.expired",
    "SignalCancelled": "signal.cancelled",
    "SignalClosed": "signal.closed",
    "SignalRejected": "signal.rejected",
}


class SignalEventPublisher:
    """Publish signal lifecycle events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: SignalAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        contract_name = CONTRACT_EVENT_MAP.get(event.event_type)
        if contract_name:
            for handler in self._handlers.get(contract_name, []):
                handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_signal_created(self, signal: TradingSignal) -> None:
        payload = {
            "signal_id": signal.signal_id,
            "decision_id": signal.decision_id,
            "symbol": signal.symbol,
            "timestamp_utc": signal.timestamp_utc.isoformat(),
            "timeframe": signal.timeframe,
            "direction": signal.direction.value,
            "state": signal.state.value,
            "entry_price": str(signal.entry_price),
            "stop_loss": str(signal.stop_loss),
            "take_profit_1": str(signal.take_profit_1),
            "take_profit_2": str(signal.take_profit_2) if signal.take_profit_2 else None,
            "take_profit_3": str(signal.take_profit_3) if signal.take_profit_3 else None,
            "risk_reward": str(signal.risk_reward),
            "confidence": signal.confidence,
            "signal_quality": signal.signal_quality,
            "quality_tier": signal.quality_tier.value,
            "expiry_time": signal.expiry_time.isoformat(),
        }
        self.publish(
            SignalAnalysisEvent(
                "SignalCreated",
                symbol=signal.symbol,
                payload=payload,
                timestamp_utc=signal.timestamp_utc,
            ),
        )

    def publish_signal_activated(self, signal: TradingSignal) -> None:
        payload = signal.model_dump(mode="json")
        self.publish(
            SignalAnalysisEvent(
                "SignalActivated",
                symbol=signal.symbol,
                payload=payload,
                timestamp_utc=signal.timestamp_utc,
            ),
        )

    def publish_signal_triggered(
        self,
        signal: TradingSignal,
        *,
        trigger_price: Decimal,
        timestamp_utc: datetime | None = None,
    ) -> None:
        event_time = timestamp_utc or datetime.now(tz=UTC)
        payload = {
            "signal_id": signal.signal_id,
            "decision_id": signal.decision_id,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "prior_state": SignalState.ACTIVE.value,
            "current_state": SignalState.TRIGGERED.value,
            "entry_price": str(signal.entry_price),
            "trigger_price": str(trigger_price),
            "timestamp_utc": event_time.isoformat(),
        }
        self.publish(
            SignalAnalysisEvent(
                "SignalTriggered",
                symbol=signal.symbol,
                payload=payload,
                timestamp_utc=event_time,
            ),
        )

    def publish_signal_expired(self, signal: TradingSignal, *, expired_at_utc: datetime) -> None:
        payload = {
            "signal_id": signal.signal_id,
            "decision_id": signal.decision_id,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "original_state": SignalState.ACTIVE.value,
            "entry_price": str(signal.entry_price),
            "created_at_utc": signal.timestamp_utc.isoformat(),
            "expired_at_utc": expired_at_utc.isoformat(),
            "expiry_time": signal.expiry_time.isoformat(),
            "was_triggered": False,
        }
        self.publish(
            SignalAnalysisEvent(
                "SignalExpired",
                symbol=signal.symbol,
                payload=payload,
                timestamp_utc=expired_at_utc,
            ),
        )

    def publish_signal_cancelled(
        self,
        signal: TradingSignal,
        *,
        reason: str,
        prior_state: SignalState,
        cancelled_at_utc: datetime,
        cancelled_by: str = "system",
    ) -> None:
        payload = {
            "signal_id": signal.signal_id,
            "decision_id": signal.decision_id,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "prior_state": prior_state.value,
            "reason": reason,
            "cancelled_at_utc": cancelled_at_utc.isoformat(),
            "cancelled_by": cancelled_by,
        }
        self.publish(
            SignalAnalysisEvent(
                "SignalCancelled",
                symbol=signal.symbol,
                payload=payload,
                timestamp_utc=cancelled_at_utc,
            ),
        )

    def publish_signal_closed(
        self,
        signal: TradingSignal,
        *,
        reason: str,
        exit_price: Decimal | None,
        closed_at_utc: datetime,
        prior_state: SignalState | None = None,
    ) -> None:
        duration_minutes = int(
            (closed_at_utc - signal.timestamp_utc).total_seconds() / 60,
        )
        payload = {
            "signal_id": signal.signal_id,
            "decision_id": signal.decision_id,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "final_state": signal.state.value,
            "close_reason": reason,
            "entry_price": str(signal.entry_price),
            "exit_price": str(exit_price) if exit_price is not None else None,
            "closed_at_utc": closed_at_utc.isoformat(),
            "duration_minutes": duration_minutes,
            "was_triggered": signal.state
            not in {SignalState.ACTIVE, SignalState.CREATED, SignalState.EXPIRED},
            "prior_state": prior_state.value if prior_state else None,
        }
        self.publish(
            SignalAnalysisEvent(
                "SignalClosed",
                symbol=signal.symbol,
                payload=payload,
                timestamp_utc=closed_at_utc,
            ),
        )

    def publish_signal_rejected(self, rejection: SignalRejection) -> None:
        payload = {
            "decision_id": rejection.decision_id,
            "symbol": rejection.symbol,
            "timestamp_utc": rejection.timestamp_utc.isoformat(),
            "decision_state": rejection.decision_state,
            "error_codes": rejection.error_codes,
            "blocking_reasons": rejection.blocking_reasons,
            "source": "market_signal",
        }
        self.publish(
            SignalAnalysisEvent(
                "SignalRejected",
                symbol=rejection.symbol,
                payload=payload,
                timestamp_utc=rejection.timestamp_utc,
            ),
        )

    def clear_handlers(self) -> None:
        self._handlers.clear()
