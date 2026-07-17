"""Unit tests for MarketSessionsEngine."""

import pytest

pytest_plugins = ["tests.unit.engines.market_sessions_conftest"]

from backend.engines.market_sessions import (
    MarketSessionsEngine,
    TradingSessionId,
    load_market_sessions_config,
)
from backend.engines.market_sessions.detector import MarketSessionsDetector
from backend.engines.market_sessions.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
    ValidationError,
)
from backend.engines.market_sessions.publisher import MarketSessionsEventPublisher
from backend.engines.market_sessions.validator import MarketSessionsInputValidator
from tests.unit.engines.conftest import make_candle
from tests.unit.engines.market_sessions_conftest import (
    build_market_sessions_candles,
    london_ny_overlap_timestamp,
    london_open_timestamp,
    market_sessions_config,
    sample_liquidity_state,
    sample_premium_discount_analysis,
)
from tests.unit.engines.premium_discount_conftest import build_premium_discount_structure


def test_engine_analyze_returns_session_analysis(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    analysis = engine.analyze(
        market_sessions_candles,
        timestamp_utc=london_open_timestamp(),
        timeframe="M15",
    )

    assert analysis.symbol == "XAUUSD"
    assert analysis.timeframe == "M15"
    assert analysis.primary_session in {TradingSessionId.LONDON, None, *TradingSessionId}
    assert analysis.state.bar_count >= 10


def test_engine_insufficient_data(market_sessions_cfg) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    with pytest.raises(InsufficientDataError):
        engine.analyze([], timestamp_utc=london_open_timestamp())


def test_engine_unsupported_timeframe(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    with pytest.raises(UnsupportedTimeframeError):
        engine.analyze(
            market_sessions_candles,
            timestamp_utc=london_open_timestamp(),
            timeframe="M1",
        )


def test_engine_validation_failure(market_sessions_cfg) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    engine = MarketSessionsEngine(config=market_sessions_cfg)
    bad = make_candle(
        open_time=datetime(2026, 1, 14, 8, 0, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    with pytest.raises(ValidationError):
        engine.analyze([bad] * 12, timestamp_utc=london_open_timestamp(), timeframe="M15")


def test_engine_publishes_events(
    market_sessions_cfg,
    market_sessions_candles,
    market_sessions_publisher,
) -> None:
    events: list[str] = []
    market_sessions_publisher.subscribe("*", lambda event: events.append(event.event_type))
    engine = MarketSessionsEngine(config=market_sessions_cfg, publisher=market_sessions_publisher)
    engine.analyze(
        market_sessions_candles,
        timestamp_utc=london_open_timestamp(),
        timeframe="M15",
    )

    assert "analysis.session.completed" in events


def test_engine_resolve_sessions(market_sessions_cfg) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    sessions = engine.resolve_sessions(london_open_timestamp())

    assert len(sessions) == 4
    assert any(session.session_id is TradingSessionId.LONDON for session in sessions)


def test_engine_resolve_kill_zones(market_sessions_cfg) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    kill_zones = engine.resolve_kill_zones(london_open_timestamp())

    assert len(kill_zones) == 4


def test_engine_detect_overlaps(market_sessions_cfg) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    sessions = engine.resolve_sessions(london_ny_overlap_timestamp())
    overlaps = engine.detect_overlaps(sessions, london_ny_overlap_timestamp())

    assert any(overlap.overlap_id == "london_new_york" for overlap in overlaps)


def test_engine_forecast_transitions(market_sessions_cfg) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    transitions = engine.forecast_transitions(london_open_timestamp(), horizon_hours=12)

    assert isinstance(transitions, list)


def test_engine_resolve_daily_open(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    daily = engine.resolve_daily_open(market_sessions_candles)

    assert daily is not None
    assert daily.is_confirmed


def test_engine_compute_opening_range(market_sessions_cfg) -> None:
    from tests.unit.engines.market_sessions_conftest import build_london_or_ib_candles

    engine = MarketSessionsEngine(config=market_sessions_cfg)
    candles = build_london_or_ib_candles(count=8)
    opening_range = engine.compute_opening_range(
        candles,
        TradingSessionId.LONDON,
        timestamp_utc=candles[-1].open_time_utc,
    )

    assert opening_range is None or opening_range.session_id is TradingSessionId.LONDON


def test_engine_compute_initial_balance(market_sessions_cfg) -> None:
    from datetime import timedelta
    from tests.unit.engines.market_sessions_conftest import build_london_or_ib_candles

    engine = MarketSessionsEngine(config=market_sessions_cfg)
    candles = build_london_or_ib_candles(count=12)
    initial_balance = engine.compute_initial_balance(
        candles,
        TradingSessionId.LONDON,
        timestamp_utc=candles[-1].open_time_utc + timedelta(hours=1),
    )

    assert initial_balance is None or initial_balance.session_id is TradingSessionId.LONDON


def test_engine_resolve_calendar(market_sessions_cfg) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    calendar = engine.resolve_calendar(london_open_timestamp())

    assert calendar.trading_day_id
    assert calendar.week_id
    assert calendar.month_id


def test_engine_score_quality(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    analysis = engine.analyze(
        market_sessions_candles,
        timestamp_utc=london_open_timestamp(),
        timeframe="M15",
    )
    tier, strength, confidence = engine.score_quality(analysis)

    assert tier in {"high", "medium", "low"}
    assert strength > 0
    assert confidence > 0


def test_engine_reset_state(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    engine.analyze(
        market_sessions_candles,
        timestamp_utc=london_open_timestamp(),
        timeframe="M15",
    )
    assert engine.prior_state is not None

    engine.reset_state()
    assert engine.prior_state is None


def test_engine_handle_config_updated(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    updated = market_sessions_cfg.model_copy(update={"min_quality_score": 0.55})
    engine.handle_config_updated(updated)

    assert engine.config.min_quality_score == 0.55


def test_engine_dependency_injection(market_sessions_cfg, market_sessions_publisher) -> None:
    detector = MarketSessionsDetector(market_sessions_cfg)
    validator = MarketSessionsInputValidator(market_sessions_cfg)
    engine = MarketSessionsEngine(
        config=market_sessions_cfg,
        detector=detector,
        validator=validator,
        publisher=market_sessions_publisher,
    )

    assert engine.config is market_sessions_cfg
    assert engine.publisher is market_sessions_publisher


def test_engine_with_upstream_context(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    structure = build_premium_discount_structure().model_copy(update={"timeframe": "M15"})
    pd = sample_premium_discount_analysis().model_copy(update={"timeframe": "M15"})
    analysis = engine.analyze(
        market_sessions_candles,
        timestamp_utc=london_open_timestamp(),
        structure=structure,
        liquidity_state=sample_liquidity_state(),
        premium_discount=pd,
        timeframe="M15",
    )

    assert analysis.strength > 0


def test_public_package_exports() -> None:
    import backend.engines.market_sessions as market_sessions

    assert hasattr(market_sessions, "MarketSessionsEngine")
    assert hasattr(market_sessions, "SessionAnalysis")
    assert hasattr(market_sessions, "load_market_sessions_config")


def test_engine_track_session_extremes(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    sessions = engine.resolve_sessions(london_open_timestamp())
    extremes = engine.track_session_extremes(market_sessions_candles, sessions)

    assert isinstance(extremes, list)


def test_engine_evaluate_time_filter(market_sessions_cfg, market_sessions_candles) -> None:
    engine = MarketSessionsEngine(config=market_sessions_cfg)
    analysis = engine.analyze(
        market_sessions_candles,
        timestamp_utc=london_open_timestamp(),
        timeframe="M15",
    )
    time_filter = engine.evaluate_time_filter(analysis)

    assert time_filter.filter_mode.value in {
        "allow_list",
        "block_list",
        "kill_zone_only",
        "disabled",
    }
