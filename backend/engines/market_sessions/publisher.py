"""Event publisher for Kill Zones & Trading Sessions Engine."""

from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from backend.engines.market_sessions.events import MarketSessionsAnalysisEvent
from backend.engines.market_sessions.schemas import (
    CalendarContext,
    InitialBalance,
    KillZoneState,
    MarketSessionsEvent,
    MarketSessionsEventKind,
    OpeningRange,
    PeriodOpen,
    SessionAnalysis,
    SessionExtreme,
    SessionOverlap,
    SessionTransition,
    TimeOfDayFilter,
    TradingSessionState,
)

EventHandler = Callable[[MarketSessionsAnalysisEvent], None]

CONTRACT_EVENT_MAP: dict[MarketSessionsEventKind, str] = {
    MarketSessionsEventKind.SESSION_STARTED: "analysis.session.transition",
    MarketSessionsEventKind.SESSION_ENDED: "analysis.session.transition",
    MarketSessionsEventKind.KILL_ZONE_STARTED: "analysis.session.high_impact_start",
    MarketSessionsEventKind.KILL_ZONE_ENDED: "analysis.session.high_impact_end",
    MarketSessionsEventKind.KILL_ZONE_ENTERED: "analysis.session.high_impact_start",
    MarketSessionsEventKind.KILL_ZONE_EXITED: "analysis.session.high_impact_end",
    MarketSessionsEventKind.OVERLAP_STARTED: "analysis.session.overlap_started",
    MarketSessionsEventKind.OVERLAP_ENDED: "analysis.session.overlap_ended",
    MarketSessionsEventKind.DAILY_OPEN_RESOLVED: "analysis.session.daily_open",
    MarketSessionsEventKind.WEEKLY_OPEN_RESOLVED: "analysis.session.weekly_open",
    MarketSessionsEventKind.MONTHLY_OPEN_RESOLVED: "analysis.session.monthly_open",
    MarketSessionsEventKind.SESSION_HIGH_UPDATED: "analysis.session.high_updated",
    MarketSessionsEventKind.SESSION_LOW_UPDATED: "analysis.session.low_updated",
    MarketSessionsEventKind.OPENING_RANGE_COMPLETE: "analysis.session.or_complete",
    MarketSessionsEventKind.OPENING_RANGE_BREAKOUT: "analysis.session.or_breakout",
    MarketSessionsEventKind.INITIAL_BALANCE_COMPLETE: "analysis.session.ib_complete",
    MarketSessionsEventKind.INITIAL_BALANCE_EXTENSION: "analysis.session.ib_extension",
    MarketSessionsEventKind.TIME_FILTER_BLOCKED: "analysis.session.filter_blocked",
    MarketSessionsEventKind.WEEKEND_DETECTED: "analysis.session.weekend",
    MarketSessionsEventKind.HOLIDAY_DETECTED: "analysis.session.holiday",
    MarketSessionsEventKind.DST_TRANSITION: "analysis.session.dst_transition",
    MarketSessionsEventKind.SESSION_QUALITY_UPDATED: "analysis.session.quality_updated",
    MarketSessionsEventKind.SESSION_TRANSITION_DETECTED: "analysis.session.transition",
    MarketSessionsEventKind.SESSION_ANALYSIS_UPDATED: "analysis.session.completed",
}


class MarketSessionsEventPublisher:
    """In-memory pub/sub for session lifecycle and temporal context events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []
        self._published: list[MarketSessionsAnalysisEvent] = []

    def publish(self, event: MarketSessionsAnalysisEvent) -> None:
        """Publish event to subscribed handlers."""
        self._published.append(event)
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)
        for handler in self._global_handlers:
            handler(event)

    def subscribe(
        self,
        handler: EventHandler | str,
        event_handler: EventHandler | None = None,
    ) -> None:
        """Subscribe to all events or a specific event type."""
        if isinstance(handler, str):
            if event_handler is None:
                msg = "event_handler required when subscribing by event type"
                raise TypeError(msg)
            self._handlers[handler].append(event_handler)
            return
        self._global_handlers.append(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        """Remove a global handler."""
        if handler in self._global_handlers:
            self._global_handlers.remove(handler)
        for handlers in self._handlers.values():
            if handler in handlers:
                handlers.remove(handler)

    def clear(self) -> None:
        """Clear handlers and published event history."""
        self._handlers.clear()
        self._global_handlers.clear()
        self._published.clear()

    @property
    def events(self) -> list[MarketSessionsAnalysisEvent]:
        """Return published events in emission order."""
        return list(self._published)

    def publish_error(
        self,
        *,
        symbol: str | None,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        timeframe: str | None = None,
    ) -> None:
        """Publish analysis error event."""
        payload = {
            "error_code": code,
            "message": message,
            "details": details or {},
            "timeframe": timeframe,
        }
        self.publish(
            MarketSessionsAnalysisEvent(
                "analysis.session.error",
                symbol=symbol,
                payload=payload,
            ),
        )

    def publish_from_timeline_event(
        self,
        event: MarketSessionsEvent,
        analysis: SessionAnalysis,
    ) -> None:
        """Publish a timeline event with contract bus alias."""
        payload = self._timeline_payload(event, analysis)
        self._publish_dual(
            event.kind.value,
            CONTRACT_EVENT_MAP.get(event.kind, f"analysis.session.{event.kind.value}"),
            analysis.symbol,
            payload,
            event.timestamp_utc,
        )

    def publish_analysis_completed(self, analysis: SessionAnalysis) -> None:
        """Publish full analysis completion summary."""
        payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "timestamp_utc": analysis.timestamp_utc.isoformat(),
            "primary_session": (
                analysis.primary_session.value if analysis.primary_session else None
            ),
            "session_phase": analysis.session_phase.value,
            "active_sessions": [s.session_id.value for s in analysis.active_sessions],
            "active_kill_zones": [
                kz.kill_zone_id.value for kz in analysis.active_kill_zones
            ],
            "market_availability": analysis.market_availability.value,
            "volatility_profile": analysis.volatility_profile.value,
            "liquidity_availability": analysis.liquidity_availability.value,
            "quality": analysis.quality.value,
            "confidence": str(analysis.confidence),
            "strength": str(analysis.strength),
            "time_of_day_filter_allowed": analysis.time_of_day_filter.is_allowed,
            "daily_open": (
                str(analysis.daily_open.open_price)
                if analysis.daily_open and analysis.daily_open.is_confirmed
                else None
            ),
            "evidence_summary": analysis.evidence[:5],
        }
        self._publish_dual(
            MarketSessionsEventKind.SESSION_ANALYSIS_UPDATED.value,
            "analysis.session.completed",
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
        kwargs: dict[str, Any] = {"symbol": symbol, "payload": payload}
        if timestamp is not None:
            kwargs["timestamp_utc"] = timestamp
        self.publish(MarketSessionsAnalysisEvent(event_type, **kwargs))
        if contract_name != event_type:
            self.publish(MarketSessionsAnalysisEvent(contract_name, **kwargs))

    def _timeline_payload(
        self,
        event: MarketSessionsEvent,
        analysis: SessionAnalysis,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "description": event.description,
            "broker_timezone": analysis.broker_timezone,
            "trading_day_id": analysis.calendar_context.trading_day_id,
        }
        if event.session_id:
            payload["session_id"] = event.session_id.value
        if event.kill_zone_id:
            payload["kill_zone_id"] = event.kill_zone_id.value
        if event.overlap_id:
            payload["overlap_id"] = event.overlap_id
        return payload
