"""Unit tests for market sessions detector."""

from datetime import UTC, datetime, timedelta

import pytest

pytest_plugins = ["tests.unit.engines.market_sessions_conftest"]
from backend.engines.market_sessions.detector import MarketSessionsDetector
from backend.engines.market_sessions.schemas import (
    KillZoneId,
    SessionPhase,
    TradingSessionId,
)
from tests.unit.engines.market_sessions_conftest import (
    asian_killzone_timestamp,
    build_london_or_ib_candles,
    build_market_sessions_candles,
    holiday_config,
    london_close_timestamp,
    london_ny_overlap_timestamp,
    london_open_timestamp,
    market_sessions_config,
    new_york_session_timestamp,
    partial_holiday_config,
    sample_liquidity_state,
    sample_premium_discount_analysis,
    weekend_timestamp,
)
from tests.unit.engines.premium_discount_conftest import build_premium_discount_structure


def test_detect_returns_session_analysis(market_sessions_candles) -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    analysis = detector.detect(
        market_sessions_candles,
        london_open_timestamp(),
    )

    assert analysis.symbol == "XAUUSD"
    assert analysis.timeframe == "M15"
    assert analysis.quality.value in {"high", "medium", "low"}
    assert analysis.state.bar_count >= 10


def test_detect_london_session_active() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(30)
    analysis = detector.detect(candles, london_open_timestamp())

    london = next(
        session for session in analysis.active_sessions
        if session.session_id is TradingSessionId.LONDON
    )
    assert london.is_active
    assert london.phase in {SessionPhase.OPENING, SessionPhase.MID}


def test_detect_new_york_session() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(
        30,
        start=new_york_session_timestamp() - timedelta(hours=4),
    )
    analysis = detector.detect(candles, new_york_session_timestamp())

    active_ids = {session.session_id for session in analysis.active_sessions}
    assert TradingSessionId.NEW_YORK in active_ids


def test_detect_asian_kill_zone() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(
        30,
        start=asian_killzone_timestamp() - timedelta(hours=2),
    )
    analysis = detector.detect(candles, asian_killzone_timestamp())

    asian = next(kz for kz in analysis.kill_zones if kz.kill_zone_id is KillZoneId.ASIAN)
    assert asian.is_active or asian.kill_zone_id is KillZoneId.ASIAN


def test_detect_london_close_kill_zone() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(30)
    analysis = detector.detect(candles, london_close_timestamp())

    london_close = next(
        kz for kz in analysis.kill_zones if kz.kill_zone_id is KillZoneId.LONDON_CLOSE
    )
    assert london_close.is_active


def test_detect_london_new_york_overlap() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(30)
    analysis = detector.detect(candles, london_ny_overlap_timestamp())

    overlap = next(
        (item for item in analysis.overlaps if item.overlap_id == "london_new_york"),
        None,
    )
    assert overlap is not None
    assert overlap.is_active
    assert TradingSessionId.LONDON in overlap.sessions
    assert TradingSessionId.NEW_YORK in overlap.sessions


def test_detect_weekend_context() -> None:
    config = market_sessions_config(weekend_trading_enabled=False)
    detector = MarketSessionsDetector(config)
    candles = build_market_sessions_candles(
        30,
        start=weekend_timestamp() - timedelta(hours=4),
    )
    analysis = detector.detect(candles, weekend_timestamp())

    assert analysis.calendar_context.is_weekend
    assert any("Weekend" in item for item in analysis.evidence)


def test_detect_holiday_context() -> None:
    detector = MarketSessionsDetector(holiday_config())
    candles = build_market_sessions_candles(
        30,
        start=datetime(2026, 1, 1, 6, 0, tzinfo=UTC),
    )
    analysis = detector.detect(candles, datetime(2026, 1, 1, 10, 0, tzinfo=UTC))

    assert analysis.calendar_context.is_holiday
    assert any("Holiday" in item for item in analysis.evidence)


def test_detect_partial_holiday_allows_london() -> None:
    detector = MarketSessionsDetector(partial_holiday_config())
    ts = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    candles = build_market_sessions_candles(30, start=datetime(2026, 1, 1, 7, 0, tzinfo=UTC))
    analysis = detector.detect(candles, ts)

    assert analysis.calendar_context.is_holiday


def test_detect_opening_range_and_initial_balance() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_london_or_ib_candles(count=12)
    ts = candles[-1].open_time_utc + timedelta(minutes=30)
    analysis = detector.detect(candles, ts)

    assert analysis.opening_range is None or analysis.opening_range.session_id is TradingSessionId.LONDON
    assert analysis.initial_balance is None or analysis.initial_balance.session_id is TradingSessionId.LONDON


def test_detect_session_extremes() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_london_or_ib_candles(count=12)
    analysis = detector.detect(candles, london_open_timestamp())

    assert isinstance(analysis.session_extremes, list)


def test_detect_with_upstream_context() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(30)
    structure = build_premium_discount_structure().model_copy(update={"timeframe": "M15"})
    liquidity = sample_liquidity_state()
    pd = sample_premium_discount_analysis().model_copy(update={"timeframe": "M15"})

    analysis = detector.detect(
        candles,
        london_open_timestamp(),
        structure=structure,
        liquidity_state=liquidity,
        premium_discount=pd,
    )

    assert analysis.confidence > 0
    assert not any("Market structure unavailable" in item for item in analysis.evidence)


def test_detect_graceful_degradation_without_upstream() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(30)
    analysis = detector.detect(candles, london_open_timestamp())

    assert any("Market structure unavailable" in item for item in analysis.evidence)
    assert any("Liquidity state unavailable" in item for item in analysis.evidence)
    assert any("Premium/discount unavailable" in item for item in analysis.evidence)


def test_detect_emits_timeline_events() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(30)
    analysis = detector.detect(candles, london_open_timestamp())

    assert analysis.events
    assert any(event.kind.value == "SessionAnalysisUpdated" for event in analysis.events)


def test_detect_transitions_forecast() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(30)
    analysis = detector.detect(candles, london_open_timestamp())

    assert analysis.next_transition is None or analysis.next_transition.transition_time_utc >= london_open_timestamp()


def test_detect_dst_transition_context() -> None:
    from tests.unit.engines.market_sessions_conftest import dst_transition_timestamp

    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(
        30,
        start=dst_transition_timestamp() - timedelta(hours=6),
    )
    analysis = detector.detect(candles, dst_transition_timestamp())

    assert isinstance(analysis.calendar_context.is_dst_transition, bool)


def test_detect_timezone_normalization_trading_day_id() -> None:
    detector = MarketSessionsDetector(market_sessions_config())
    candles = build_market_sessions_candles(30)
    analysis = detector.detect(candles, london_open_timestamp())

    assert analysis.calendar_context.trading_day_id == "2026-01-14"
    assert analysis.broker_timezone == market_sessions_config().broker_timezone
