"""Analysis orchestrator for kill zones and trading sessions."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_mitigation.schemas import MitigationBlock
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_premium_discount.schemas import PremiumDiscountAnalysis
from backend.engines.market_sessions.calendar import CalendarResolver
from backend.engines.market_sessions.config import MarketSessionsConfig
from backend.engines.market_sessions.killzones import KillZoneResolver
from backend.engines.market_sessions.lifecycle import LifecycleManager
from backend.engines.market_sessions.quality import QualityScorer
from backend.engines.market_sessions.schemas import (
    KillZoneId,
    MarketAvailability,
    MarketSessionsEvent,
    MarketSessionsEventKind,
    MarketSessionsState,
    SessionAnalysis,
    SessionPhase,
    TradingSessionId,
    VolatilityProfile,
)
from backend.engines.market_sessions.sessions import SessionResolver
from backend.engines.market_sessions.timezone import TimezoneNormalizer
from backend.engines.market_structure import MarketStructure


class MarketSessionsDetector:
    """Detect session context, kill zones, opens, extremes, OR/IB, and quality."""

    def __init__(self, config: MarketSessionsConfig) -> None:
        self._config = config
        self._tz = TimezoneNormalizer()
        self._calendar = CalendarResolver(config, self._tz)
        self._sessions = SessionResolver(config, self._tz)
        self._kill_zones = KillZoneResolver(config, self._tz)
        self._lifecycle = LifecycleManager(config, self._tz)
        self._quality = QualityScorer(config)

    def detect(
        self,
        candles: list[NormalizedCandle],
        timestamp_utc: datetime,
        *,
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
        broker_timezone: str | None = None,
        prior_state: MarketSessionsState | None = None,
    ) -> SessionAnalysis:
        """Run full session and kill zone analysis."""
        broker_tz = broker_timezone or self._config.broker_timezone
        closed = sorted(
            [c for c in candles if c.is_closed][-self._config.lookback :],
            key=lambda c: c.open_time_utc,
        )
        symbol = candles[0].symbol
        timeframe = candles[0].timeframe.upper()

        calendar_context = self._calendar.resolve_calendar_context(
            timestamp_utc,
            broker_tz,
        )
        sessions_allowed = self._calendar.sessions_allowed(calendar_context)
        partial_sessions = self._calendar.partial_holiday_active_sessions()
        market_closed = not sessions_allowed

        # Initial session resolution (pre-quality)
        raw_sessions = self._sessions.resolve_all_sessions(
            timestamp_utc,
            market_closed=market_closed,
            partial_holiday_sessions=partial_sessions if calendar_context.is_holiday else None,
        )
        raw_kill_zones = self._kill_zones.resolve_all_kill_zones(
            timestamp_utc,
            raw_sessions,
            market_closed=market_closed,
        )

        overlaps = self._sessions.detect_overlaps(raw_sessions, timestamp_utc)
        overlap_session_ids = {
            session_id
            for overlap in overlaps
            if overlap.is_active
            for session_id in overlap.sessions
        }

        calendar_clean = (
            not calendar_context.is_weekend
            and not calendar_context.is_holiday
            and not calendar_context.is_dst_transition
        )

        # Volatility and liquidity profiling
        primary_candidate = self._sessions.select_primary_session(raw_sessions)
        primary_session_state = next(
            (s for s in raw_sessions if s.session_id == primary_candidate),
            None,
        )
        volatility_profile, volatility_score = self._quality.profile_volatility(
            closed,
            primary_session_state,
        )
        liquidity_availability, liquidity_score = self._quality.assess_liquidity(
            closed,
            liquidity_state,
        )

        vol_scores: dict[KillZoneId, Decimal] = {}
        vol_profiles: dict[TradingSessionId, VolatilityProfile] = {}
        for session in raw_sessions:
            profile, score = self._quality.profile_volatility(closed, session)
            vol_profiles[session.session_id] = profile
        for kz in raw_kill_zones:
            parent = next(
                (s for s in raw_sessions if s.session_id == kz.parent_session),
                None,
            )
            _, score = self._quality.profile_volatility(closed, parent)
            vol_scores[kz.kill_zone_id] = score

        liquidity_kz_scores = {
            kz.kill_zone_id: liquidity_score for kz in raw_kill_zones
        }
        historical_score = self._quality.historical_performance_score(
            opening_range_complete=False,
            initial_balance_complete=False,
            session_range_pips=None,
        )
        historical_kz_scores = {
            kz.kill_zone_id: historical_score for kz in raw_kill_zones
        }

        sessions = self._quality.enrich_sessions(
            raw_sessions,
            calendar_clean=calendar_clean,
            overlap_session_ids=overlap_session_ids,
        )
        sessions = [
            session.model_copy(
                update={
                    "volatility_profile": vol_profiles.get(
                        session.session_id,
                        session.volatility_profile,
                    ),
                },
            )
            for session in sessions
        ]

        kill_zones = self._quality.enrich_kill_zones(
            raw_kill_zones,
            volatility_scores=vol_scores,
            liquidity_scores=liquidity_kz_scores,
            historical_scores=historical_kz_scores,
        )

        active_sessions = [s for s in sessions if s.is_active]
        active_kill_zones = [kz for kz in kill_zones if kz.is_active]
        primary_session = self._sessions.select_primary_session(sessions)
        primary_state = next(
            (s for s in sessions if s.session_id == primary_session),
            None,
        )
        session_phase = (
            primary_state.phase if primary_state else SessionPhase.INACTIVE
        )

        has_active = bool(active_sessions)
        market_availability = self._calendar.market_availability(
            calendar_context,
            has_active_session=has_active,
        )

        daily_open = self._lifecycle.resolve_daily_open(
            closed,
            timestamp_utc,
            broker_tz,
        )
        weekly_open = self._lifecycle.resolve_weekly_open(
            closed,
            timestamp_utc,
            broker_tz,
        )
        monthly_open = self._lifecycle.resolve_monthly_open(
            closed,
            timestamp_utc,
            broker_tz,
        )

        session_extremes = self._lifecycle.track_session_extremes(
            closed,
            sessions,
            calendar_context.trading_day_id,
            prior_extremes=prior_state.session_extremes_cache if prior_state else None,
            liquidity_state=liquidity_state,
        )

        opening_range = None
        initial_balance = None
        if primary_state is not None:
            opening_range = self._lifecycle.compute_opening_range(
                closed,
                primary_state,
                timestamp_utc,
            )
            initial_balance = self._lifecycle.compute_initial_balance(
                closed,
                primary_state,
                timestamp_utc,
            )

        if opening_range and opening_range.is_complete:
            historical_score = self._quality.historical_performance_score(
                opening_range_complete=True,
                initial_balance_complete=bool(
                    initial_balance and initial_balance.is_complete,
                ),
                session_range_pips=opening_range.range_size_pips,
            )

        time_of_day_filter = self._lifecycle.evaluate_time_filter(
            active_sessions=active_sessions,
            active_kill_zones=active_kill_zones,
            calendar_is_weekend=calendar_context.is_weekend,
            calendar_is_holiday=calendar_context.is_holiday,
            timestamp_utc=timestamp_utc,
            kill_zones_all=kill_zones,
            sessions_all=sessions,
        )

        next_transition, recent_transitions = self._lifecycle.forecast_transitions(
            timestamp_utc,
            sessions,
            kill_zones,
            overlaps,
        )

        upstream_boost = self._quality.upstream_confluence_score(
            order_blocks=order_blocks,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            mitigation_blocks=mitigation_blocks,
        )

        quality_tier, strength, confidence, _ = self._quality.score_analysis(
            sessions=sessions,
            kill_zones=kill_zones,
            overlaps=overlaps,
            volatility_score=volatility_score,
            liquidity_score=liquidity_score,
            historical_score=historical_score,
            structure=structure,
            premium_discount=premium_discount,
        )
        if upstream_boost > Decimal("0"):
            strength = min(Decimal("1"), strength + upstream_boost)
            quality_tier = self._quality._tier_from_score(strength)

        evidence: list[str] = []
        if primary_state:
            evidence.extend(primary_state.evidence)
        for kz in active_kill_zones:
            evidence.extend(kz.evidence[:1])
        for overlap in overlaps:
            if overlap.is_active:
                evidence.extend(overlap.evidence)
        if calendar_context.is_weekend:
            evidence.append("Weekend — temporal context may be reduced")
        if calendar_context.is_holiday:
            evidence.append(
                f"Holiday — {calendar_context.holiday_name or 'market closed'}",
            )
        if calendar_context.is_dst_transition:
            evidence.append("DST transition window — session boundaries recalculated")
        if not structure:
            evidence.append("Market structure unavailable — neutral structure weight")
        if not liquidity_state:
            evidence.append("Liquidity state unavailable — candle proxies used")
        if not premium_discount:
            evidence.append("Premium/discount unavailable — neutral pricing weight")

        bar_count = len(closed)
        state = self._lifecycle.update_state(
            prior_state=prior_state,
            timestamp_utc=timestamp_utc,
            primary_session=primary_session,
            session_phase=session_phase,
            session_extremes=session_extremes,
            opening_range=opening_range,
            initial_balance=initial_balance,
            daily_open=daily_open,
            weekly_open=weekly_open,
            monthly_open=monthly_open,
            active_sessions=active_sessions,
            active_kill_zones=active_kill_zones,
            overlaps=overlaps,
            calendar_is_weekend=calendar_context.is_weekend,
            calendar_is_holiday=calendar_context.is_holiday,
            quality_tier=quality_tier,
            quality_score=strength,
            bar_count=bar_count,
            trading_day_id=calendar_context.trading_day_id,
        )

        events = self._lifecycle.build_timeline_events(
            prior_state=prior_state,
            active_sessions=active_sessions,
            active_kill_zones=active_kill_zones,
            overlaps=overlaps,
            session_extremes=session_extremes,
            opening_range=opening_range,
            initial_balance=initial_balance,
            calendar_is_weekend=calendar_context.is_weekend,
            calendar_is_holiday=calendar_context.is_holiday,
            quality_tier=quality_tier,
            quality_score=strength,
            transitions=recent_transitions,
            timestamp_utc=timestamp_utc,
            trading_day_id=calendar_context.trading_day_id,
            daily_open=daily_open,
            weekly_open=weekly_open,
            monthly_open=monthly_open,
            is_dst_transition=calendar_context.is_dst_transition,
            time_filter=time_of_day_filter,
            prior_daily_open=prior_state.last_daily_open if prior_state else None,
            prior_weekly_open=prior_state.last_weekly_open if prior_state else None,
            prior_monthly_open=prior_state.last_monthly_open if prior_state else None,
        )

        events.append(
            MarketSessionsEvent(
                kind=MarketSessionsEventKind.SESSION_ANALYSIS_UPDATED,
                timestamp_utc=timestamp_utc,
                description="Session analysis cycle complete",
            ),
        )

        return SessionAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_utc=timestamp_utc.astimezone(UTC),
            broker_timezone=broker_tz,
            market_availability=market_availability,
            active_sessions=active_sessions,
            primary_session=primary_session,
            session_phase=session_phase,
            kill_zones=kill_zones,
            active_kill_zones=active_kill_zones,
            overlaps=overlaps,
            next_transition=next_transition,
            recent_transitions=recent_transitions,
            daily_open=daily_open,
            weekly_open=weekly_open,
            monthly_open=monthly_open,
            session_extremes=session_extremes,
            opening_range=opening_range,
            initial_balance=initial_balance,
            time_of_day_filter=time_of_day_filter,
            calendar_context=calendar_context,
            volatility_profile=volatility_profile,
            liquidity_availability=liquidity_availability,
            quality=quality_tier,
            confidence=confidence,
            strength=strength,
            evidence=evidence,
            state=state,
            events=events,
        )
