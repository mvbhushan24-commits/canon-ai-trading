"""Unit tests for market sessions event publisher."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_sessions.publisher import (
    CONTRACT_EVENT_MAP,
    MarketSessionsEventPublisher,
)
from backend.engines.market_sessions.schemas import (
    CalendarContext,
    MarketAvailability,
    MarketSessionsEvent,
    MarketSessionsEventKind,
    SessionAnalysis,
    SessionPhase,
    SessionQualityTier,
    TimeOfDayFilter,
    FilterMode,
    TradingSessionId,
    VolatilityProfile,
    LiquidityAvailability,
    MarketSessionsState,
)


def _sample_analysis() -> SessionAnalysis:
    return SessionAnalysis(
        symbol="XAUUSD",
        timeframe="M15",
        timestamp_utc=datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        broker_timezone="Europe/Nicosia",
        market_availability=MarketAvailability.OPEN,
        active_sessions=[],
        primary_session=TradingSessionId.LONDON,
        session_phase=SessionPhase.OPENING,
        kill_zones=[],
        active_kill_zones=[],
        overlaps=[],
        next_transition=None,
        recent_transitions=[],
        daily_open=None,
        weekly_open=None,
        monthly_open=None,
        session_extremes=[],
        opening_range=None,
        initial_balance=None,
        time_of_day_filter=TimeOfDayFilter(
            filter_mode=FilterMode.KILL_ZONE_ONLY,
            is_allowed=True,
        ),
        calendar_context=CalendarContext(
            is_weekend=False,
            is_holiday=False,
            is_dst_transition=False,
            dst_offset_minutes=120,
            trading_day_id="2026-01-14",
            week_id="2026-W03",
            month_id="2026-01",
        ),
        volatility_profile=VolatilityProfile.MODERATE,
        liquidity_availability=LiquidityAvailability.MODERATE,
        quality=SessionQualityTier.MEDIUM,
        confidence=Decimal("0.6"),
        strength=Decimal("0.55"),
        state=MarketSessionsState(bar_count=20),
        events=[],
    )


def test_subscribe_and_publish_error() -> None:
    publisher = MarketSessionsEventPublisher()
    received: list[str] = []
    publisher.subscribe("analysis.session.error", lambda event: received.append(event.event_type))

    publisher.publish_error(
        symbol="XAUUSD",
        code="MS_VALIDATION_FAILED",
        message="Validation failed",
        timeframe="M15",
    )

    assert "analysis.session.error" in received


def test_wildcard_subscribe() -> None:
    publisher = MarketSessionsEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_analysis_completed(_sample_analysis())

    assert "analysis.session.completed" in received
    assert "SessionAnalysisUpdated" in received


def test_publish_from_timeline_event_dual_naming() -> None:
    publisher = MarketSessionsEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    analysis = _sample_analysis()
    event = MarketSessionsEvent(
        kind=MarketSessionsEventKind.SESSION_STARTED,
        timestamp_utc=analysis.timestamp_utc,
        description="Session london started",
        session_id=TradingSessionId.LONDON,
    )
    publisher.publish_from_timeline_event(event, analysis)

    assert "SessionStarted" in received
    assert CONTRACT_EVENT_MAP[MarketSessionsEventKind.SESSION_STARTED] in received


def test_publish_analysis_completed_payload() -> None:
    publisher = MarketSessionsEventPublisher()
    publisher.publish_analysis_completed(_sample_analysis())

    completed = [event for event in publisher.events if event.event_type == "analysis.session.completed"]
    assert completed
    payload = completed[0].payload
    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "M15"
    assert payload["primary_session"] == "london"


def test_unsubscribe_global_handler() -> None:
    publisher = MarketSessionsEventPublisher()
    received: list[str] = []

    def handler(event) -> None:
        received.append(event.event_type)

    publisher.subscribe(handler)
    publisher.unsubscribe(handler)
    publisher.publish_analysis_completed(_sample_analysis())

    assert not received


def test_clear_resets_history() -> None:
    publisher = MarketSessionsEventPublisher()
    publisher.publish_analysis_completed(_sample_analysis())
    assert publisher.events

    publisher.clear()
    assert not publisher.events


def test_subscribe_by_event_type_requires_handler() -> None:
    publisher = MarketSessionsEventPublisher()
    with __import__("pytest").raises(TypeError):
        publisher.subscribe("analysis.session.completed")
