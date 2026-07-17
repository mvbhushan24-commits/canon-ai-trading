"""Unit tests for market sessions quality scoring."""

from decimal import Decimal

from backend.engines.market_sessions.quality import QualityScorer
from backend.engines.market_sessions.schemas import (
    KillZoneId,
    SessionPhase,
    SessionQualityTier,
    TradingSessionId,
    VolatilityProfile,
)
from backend.engines.market_sessions.sessions import SessionResolver
from backend.engines.market_sessions.timezone import TimezoneNormalizer
from tests.unit.engines.market_sessions_conftest import (
    build_market_sessions_candles,
    london_open_timestamp,
    market_sessions_config,
    sample_liquidity_state,
)
from tests.unit.engines.premium_discount_conftest import build_premium_discount_structure


def _scorer() -> QualityScorer:
    return QualityScorer(market_sessions_config())


def _active_london_session():
    resolver = SessionResolver(market_sessions_config(), TimezoneNormalizer())
    sessions = resolver.resolve_all_sessions(london_open_timestamp())
    return next(session for session in sessions if session.session_id is TradingSessionId.LONDON)


def test_score_session_active_opening_phase() -> None:
    scorer = _scorer()
    session = _active_london_session().model_copy(update={"is_active": True, "phase": SessionPhase.OPENING})
    score = scorer.score_session(session, calendar_clean=True, has_overlap=False)

    assert score > Decimal("0.5")


def test_score_session_inactive() -> None:
    scorer = _scorer()
    session = _active_london_session().model_copy(update={"is_active": False, "phase": SessionPhase.INACTIVE})
    score = scorer.score_session(session, calendar_clean=True, has_overlap=False)

    assert score == Decimal("0.15")


def test_score_kill_zone_active() -> None:
    scorer = _scorer()
    from backend.engines.market_sessions.killzones import KillZoneResolver

    resolver = KillZoneResolver(market_sessions_config(), TimezoneNormalizer())
    sessions = SessionResolver(market_sessions_config(), TimezoneNormalizer()).resolve_all_sessions(
        london_open_timestamp(),
    )
    kill_zone = next(
        kz for kz in resolver.resolve_all_kill_zones(london_open_timestamp(), sessions)
        if kz.kill_zone_id is KillZoneId.LONDON_OPEN
    )
    score = scorer.score_kill_zone(
        kill_zone,
        volatility_score=Decimal("0.6"),
        liquidity_score=Decimal("0.6"),
        historical_score=Decimal("0.5"),
    )

    assert score > Decimal("0.4")


def test_profile_volatility() -> None:
    scorer = _scorer()
    candles = build_market_sessions_candles(30)
    session = _active_london_session()
    profile, score = scorer.profile_volatility(candles, session)

    assert profile in VolatilityProfile
    assert Decimal("0") < score <= Decimal("1")


def test_assess_liquidity_with_engine_state() -> None:
    scorer = _scorer()
    candles = build_market_sessions_candles(30)
    availability, score = scorer.assess_liquidity(candles, sample_liquidity_state())

    assert availability.value in {"high", "moderate", "low", "undetermined"}
    assert Decimal("0") < score <= Decimal("1")


def test_assess_liquidity_without_engine_state() -> None:
    scorer = _scorer()
    candles = build_market_sessions_candles(30)
    availability, score = scorer.assess_liquidity(candles, None)

    assert availability.value in {"high", "moderate", "low", "undetermined"}
    assert score >= Decimal("0")


def test_historical_performance_disabled_by_default() -> None:
    scorer = _scorer()
    score = scorer.historical_performance_score(
        opening_range_complete=True,
        initial_balance_complete=True,
        session_range_pips=Decimal("40"),
    )
    assert score == Decimal("0.5")


def test_historical_performance_when_enabled() -> None:
    config = market_sessions_config()
    config = config.model_copy(
        update={
            "historical_performance": config.historical_performance.model_copy(
                update={"enabled": True},
            ),
        },
    )
    scorer = QualityScorer(config)
    score = scorer.historical_performance_score(
        opening_range_complete=True,
        initial_balance_complete=True,
        session_range_pips=Decimal("40"),
    )
    assert score > Decimal("0.5")


def test_score_analysis_composite() -> None:
    scorer = _scorer()
    resolver = SessionResolver(market_sessions_config(), TimezoneNormalizer())
    from backend.engines.market_sessions.killzones import KillZoneResolver

    ts = london_open_timestamp()
    sessions = resolver.resolve_all_sessions(ts)
    kill_zones = KillZoneResolver(market_sessions_config(), TimezoneNormalizer()).resolve_all_kill_zones(
        ts,
        sessions,
    )
    overlaps = resolver.detect_overlaps(sessions, ts)
    sessions = scorer.enrich_sessions(
        sessions,
        calendar_clean=True,
        overlap_session_ids=set(),
    )
    kill_zones = scorer.enrich_kill_zones(
        kill_zones,
        volatility_scores={KillZoneId.LONDON_OPEN: Decimal("0.6")},
        liquidity_scores={KillZoneId.LONDON_OPEN: Decimal("0.6")},
        historical_scores={KillZoneId.LONDON_OPEN: Decimal("0.5")},
    )

    tier, strength, confidence, _ = scorer.score_analysis(
        sessions=sessions,
        kill_zones=kill_zones,
        overlaps=overlaps,
        volatility_score=Decimal("0.6"),
        liquidity_score=Decimal("0.6"),
        historical_score=Decimal("0.5"),
        structure=build_premium_discount_structure().model_copy(update={"timeframe": "M15"}),
    )

    assert tier in SessionQualityTier
    assert strength > Decimal("0")
    assert confidence > Decimal("0")


def test_upstream_confluence_score() -> None:
    scorer = _scorer()
    boost = scorer.upstream_confluence_score(
        order_blocks=[],
        fair_value_gap_state=None,
        breaker_blocks=[],
        mitigation_blocks=[],
    )
    assert boost == Decimal("0")
