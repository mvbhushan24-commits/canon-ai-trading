"""Unit tests for market sessions lifecycle manager."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_sessions.lifecycle import LifecycleManager
from backend.engines.market_sessions.schemas import (
    FilterMode,
    SessionPhase,
    TradingSessionId,
    SessionQualityTier,
)
from backend.engines.market_sessions.sessions import SessionResolver
from backend.engines.market_sessions.timezone import TimezoneNormalizer
from tests.unit.engines.market_sessions_conftest import (
    build_london_or_ib_candles,
    build_market_sessions_candles,
    kill_zone_only_config,
    london_open_timestamp,
    market_sessions_config,
    sample_liquidity_state,
)


def _lifecycle() -> LifecycleManager:
    return LifecycleManager(market_sessions_config(), TimezoneNormalizer())


def _resolve_london_session(timestamp: datetime):
    resolver = SessionResolver(market_sessions_config(), TimezoneNormalizer())
    sessions = resolver.resolve_all_sessions(timestamp)
    return next(session for session in sessions if session.session_id is TradingSessionId.LONDON)


def test_resolve_daily_open() -> None:
    lifecycle = _lifecycle()
    candles = build_market_sessions_candles(30)
    daily = lifecycle.resolve_daily_open(
        candles,
        london_open_timestamp(),
        "Europe/Nicosia",
    )

    assert daily is not None
    assert daily.open_price > Decimal("0")
    assert daily.is_confirmed


def test_resolve_weekly_open() -> None:
    lifecycle = _lifecycle()
    candles = build_market_sessions_candles(30)
    weekly = lifecycle.resolve_weekly_open(
        candles,
        london_open_timestamp(),
        "Europe/Nicosia",
    )

    assert weekly is not None
    assert weekly.is_confirmed


def test_resolve_monthly_open() -> None:
    lifecycle = _lifecycle()
    candles = build_market_sessions_candles(30)
    monthly = lifecycle.resolve_monthly_open(
        candles,
        london_open_timestamp(),
        "Europe/Nicosia",
    )

    assert monthly is not None
    assert monthly.is_confirmed


def test_track_session_extremes() -> None:
    lifecycle = _lifecycle()
    candles = build_london_or_ib_candles(count=12)
    ts = london_open_timestamp()
    sessions = SessionResolver(market_sessions_config(), TimezoneNormalizer()).resolve_all_sessions(ts)
    extremes = lifecycle.track_session_extremes(
        candles,
        sessions,
        "2026-01-14",
        liquidity_state=sample_liquidity_state(),
    )

    assert extremes
    london_extreme = next(
        item for item in extremes if item.session_id is TradingSessionId.LONDON
    )
    assert london_extreme.session_high >= london_extreme.session_low
    assert london_extreme.range_size_pips >= Decimal("0")


def test_compute_opening_range() -> None:
    lifecycle = _lifecycle()
    candles = build_london_or_ib_candles(count=8)
    session = _resolve_london_session(candles[-1].open_time_utc + timedelta(minutes=45))
    opening_range = lifecycle.compute_opening_range(
        candles,
        session,
        candles[-1].open_time_utc + timedelta(minutes=45),
    )

    assert opening_range is not None
    assert opening_range.high >= opening_range.low
    assert opening_range.range_size_pips >= Decimal("0")
    assert opening_range.quality in SessionQualityTier


def test_compute_initial_balance() -> None:
    lifecycle = _lifecycle()
    candles = build_london_or_ib_candles(count=12)
    ts = candles[0].open_time_utc + timedelta(hours=2)
    session = _resolve_london_session(ts)
    initial_balance = lifecycle.compute_initial_balance(candles, session, ts)

    assert initial_balance is not None
    assert initial_balance.high >= initial_balance.low
    assert initial_balance.duration_minutes == market_sessions_config().initial_balance.duration_minutes


def test_evaluate_time_filter_kill_zone_only() -> None:
    lifecycle = LifecycleManager(kill_zone_only_config(), TimezoneNormalizer())
    resolver = SessionResolver(kill_zone_only_config(), TimezoneNormalizer())
    ts = london_open_timestamp()
    sessions = resolver.resolve_all_sessions(ts)
    from backend.engines.market_sessions.killzones import KillZoneResolver

    kill_zones = KillZoneResolver(kill_zone_only_config(), TimezoneNormalizer()).resolve_all_kill_zones(
        ts,
        sessions,
    )
    active_sessions = [session for session in sessions if session.is_active]
    active_kill_zones = [kz for kz in kill_zones if kz.is_active]
    time_filter = lifecycle.evaluate_time_filter(
        active_sessions=active_sessions,
        active_kill_zones=active_kill_zones,
        calendar_is_weekend=False,
        calendar_is_holiday=False,
        timestamp_utc=ts,
        kill_zones_all=kill_zones,
        sessions_all=sessions,
    )

    assert time_filter.filter_mode is FilterMode.KILL_ZONE_ONLY
    assert isinstance(time_filter.is_allowed, bool)


def test_forecast_transitions() -> None:
    lifecycle = _lifecycle()
    resolver = SessionResolver(market_sessions_config(), TimezoneNormalizer())
    from backend.engines.market_sessions.killzones import KillZoneResolver

    ts = london_open_timestamp()
    sessions = resolver.resolve_all_sessions(ts)
    kill_zones = KillZoneResolver(market_sessions_config(), TimezoneNormalizer()).resolve_all_kill_zones(
        ts,
        sessions,
    )
    overlaps = resolver.detect_overlaps(sessions, ts)
    next_transition, recent = lifecycle.forecast_transitions(ts, sessions, kill_zones, overlaps)

    assert next_transition is None or next_transition.transition_time_utc >= ts
    assert isinstance(recent, list)


def test_build_timeline_events_session_started() -> None:
    lifecycle = _lifecycle()
    resolver = SessionResolver(market_sessions_config(), TimezoneNormalizer())
    ts = london_open_timestamp()
    sessions = resolver.resolve_all_sessions(ts)
    active_sessions = [session for session in sessions if session.is_active]
    events = lifecycle.build_timeline_events(
        prior_state=None,
        active_sessions=active_sessions,
        active_kill_zones=[],
        overlaps=[],
        session_extremes=[],
        opening_range=None,
        initial_balance=None,
        calendar_is_weekend=False,
        calendar_is_holiday=False,
        quality_tier=SessionQualityTier.MEDIUM,
        quality_score=Decimal("0.5"),
        transitions=[],
        timestamp_utc=ts,
    )

    assert any(event.kind.value == "SessionStarted" for event in events)


def test_update_state_persists_extremes_cache() -> None:
    lifecycle = _lifecycle()
    candles = build_london_or_ib_candles(count=12)
    ts = london_open_timestamp()
    sessions = SessionResolver(market_sessions_config(), TimezoneNormalizer()).resolve_all_sessions(ts)
    extremes = lifecycle.track_session_extremes(candles, sessions, "2026-01-14")
    state = lifecycle.update_state(
        prior_state=None,
        timestamp_utc=ts,
        primary_session=TradingSessionId.LONDON,
        session_phase=SessionPhase.OPENING,
        session_extremes=extremes,
        opening_range=None,
        initial_balance=None,
        daily_open=None,
        weekly_open=None,
        monthly_open=None,
        active_sessions=[session for session in sessions if session.is_active],
        active_kill_zones=[],
        overlaps=[],
        calendar_is_weekend=False,
        calendar_is_holiday=False,
        quality_tier=SessionQualityTier.MEDIUM,
        quality_score=Decimal("0.5"),
        bar_count=len(candles),
        trading_day_id="2026-01-14",
    )

    assert state.bar_count == len(candles)
    assert state.last_primary_session is TradingSessionId.LONDON
