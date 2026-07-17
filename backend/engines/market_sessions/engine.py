"""Kill Zones & Trading Sessions Engine orchestrator."""

import logging
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
from backend.engines.market_sessions.config import (
    MarketSessionsConfig,
    load_market_sessions_config,
    validate_config_timezones,
)
from backend.engines.market_sessions.detector import MarketSessionsDetector
from backend.engines.market_sessions.exceptions import (
    InsufficientDataError,
    MarketSessionsError,
    UnsupportedTimeframeError,
)
from backend.engines.market_sessions.killzones import KillZoneResolver
from backend.engines.market_sessions.lifecycle import LifecycleManager
from backend.engines.market_sessions.publisher import MarketSessionsEventPublisher
from backend.engines.market_sessions.quality import QualityScorer
from backend.engines.market_sessions.schemas import (
    CalendarContext,
    InitialBalance,
    KillZoneState,
    MarketSessionsEventKind,
    MarketSessionsState,
    OpeningRange,
    PeriodOpen,
    SessionAnalysis,
    SessionOverlap,
    SessionTransition,
    TimeOfDayFilter,
    TradingSessionId,
    TradingSessionState,
)
from backend.engines.market_sessions.sessions import SessionResolver
from backend.engines.market_sessions.timezone import TimezoneNormalizer
from backend.engines.market_sessions.validator import MarketSessionsInputValidator
from backend.engines.market_structure import MarketStructure

logger = logging.getLogger(__name__)


class MarketSessionsEngine:
    """Institutional session and kill zone temporal context engine."""

    def __init__(
        self,
        config: MarketSessionsConfig | None = None,
        detector: MarketSessionsDetector | None = None,
        validator: MarketSessionsInputValidator | None = None,
        publisher: MarketSessionsEventPublisher | None = None,
    ) -> None:
        self._config = config or load_market_sessions_config()
        validate_config_timezones(self._config)
        self._detector = detector or MarketSessionsDetector(self._config)
        self._validator = validator or MarketSessionsInputValidator(self._config)
        self._publisher = publisher or MarketSessionsEventPublisher()
        self._tz = TimezoneNormalizer()
        self._calendar = CalendarResolver(self._config, self._tz)
        self._sessions = SessionResolver(self._config, self._tz)
        self._kill_zones = KillZoneResolver(self._config, self._tz)
        self._lifecycle = LifecycleManager(self._config, self._tz)
        self._quality = QualityScorer(self._config)
        self._prior_state: MarketSessionsState | None = None

    @property
    def config(self) -> MarketSessionsConfig:
        return self._config

    @property
    def publisher(self) -> MarketSessionsEventPublisher:
        return self._publisher

    @property
    def prior_state(self) -> MarketSessionsState | None:
        return self._prior_state

    def analyze(
        self,
        candles: list[NormalizedCandle],
        *,
        timestamp_utc: datetime,
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
        broker_timezone: str | None = None,
        timeframe: str | None = None,
        prior_state: MarketSessionsState | None = None,
    ) -> SessionAnalysis:
        """Analyze session and kill zone context from candles and upstream engines."""
        if not candles:
            raise InsufficientDataError(
                "No candles provided",
                details={"min_candles": self._config.min_candles},
            )

        state = prior_state or self._prior_state
        broker_tz = broker_timezone or self._config.broker_timezone
        target_timeframe = (timeframe or candles[0].timeframe).upper()

        try:
            self._validator.validate_or_raise(
                candles,
                timestamp_utc,
                broker_tz,
                structure=structure,
                liquidity_state=liquidity_state,
                premium_discount=premium_discount,
                order_blocks=order_blocks,
                fair_value_gap_state=fair_value_gap_state,
                breaker_blocks=breaker_blocks,
                mitigation_blocks=mitigation_blocks,
                prior_state=state,
                timeframe=target_timeframe,
            )
        except MarketSessionsError as exc:
            self._publisher.publish_error(
                symbol=candles[0].symbol if candles else None,
                code=exc.code,
                message=str(exc),
                details=exc.details,
                timeframe=target_timeframe,
            )
            raise

        if target_timeframe not in self._config.timeframes:
            raise UnsupportedTimeframeError(
                f"Timeframe '{target_timeframe}' is not configured",
                details={"configured": self._config.timeframes},
            )

        logger.info(
            "Analyzing session context",
            extra={
                "symbol": candles[0].symbol,
                "timeframe": target_timeframe,
                "candles": len(candles),
                "structure": structure is not None,
                "liquidity_state": liquidity_state is not None,
                "premium_discount": premium_discount is not None,
            },
        )

        analysis = self._detector.detect(
            candles,
            timestamp_utc,
            structure=structure,
            liquidity_state=liquidity_state,
            premium_discount=premium_discount,
            order_blocks=order_blocks,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            mitigation_blocks=mitigation_blocks,
            broker_timezone=broker_tz,
            prior_state=state,
        )
        self.publish_events(analysis)
        self._prior_state = analysis.state

        logger.info(
            "Session analysis complete",
            extra={
                "symbol": analysis.symbol,
                "timeframe": analysis.timeframe,
                "primary_session": (
                    analysis.primary_session.value if analysis.primary_session else None
                ),
                "quality": analysis.quality.value,
            },
        )
        return analysis

    def resolve_sessions(
        self,
        timestamp_utc: datetime,
        broker_timezone: str | None = None,
    ) -> list[TradingSessionState]:
        """Resolve all session windows at reference time."""
        broker_tz = broker_timezone or self._config.broker_timezone
        calendar = self._calendar.resolve_calendar_context(timestamp_utc, broker_tz)
        market_closed = not self._calendar.sessions_allowed(calendar)
        partial = self._calendar.partial_holiday_active_sessions()
        return self._sessions.resolve_all_sessions(
            timestamp_utc,
            market_closed=market_closed,
            partial_holiday_sessions=partial if calendar.is_holiday else None,
        )

    def resolve_kill_zones(
        self,
        timestamp_utc: datetime,
        sessions: list[TradingSessionState] | None = None,
        broker_timezone: str | None = None,
    ) -> list[KillZoneState]:
        """Resolve all kill zones at reference time."""
        broker_tz = broker_timezone or self._config.broker_timezone
        calendar = self._calendar.resolve_calendar_context(timestamp_utc, broker_tz)
        market_closed = not self._calendar.sessions_allowed(calendar)
        session_list = sessions or self.resolve_sessions(timestamp_utc, broker_tz)
        return self._kill_zones.resolve_all_kill_zones(
            timestamp_utc,
            session_list,
            market_closed=market_closed,
        )

    def detect_overlaps(
        self,
        sessions: list[TradingSessionState],
        timestamp_utc: datetime,
    ) -> list[SessionOverlap]:
        """Detect configured session overlaps."""
        return self._sessions.detect_overlaps(sessions, timestamp_utc)

    def forecast_transitions(
        self,
        timestamp_utc: datetime,
        *,
        horizon_hours: int | None = None,
    ) -> list[SessionTransition]:
        """Forecast upcoming session and kill zone boundaries."""
        sessions = self.resolve_sessions(timestamp_utc)
        kill_zones = self.resolve_kill_zones(timestamp_utc, sessions)
        overlaps = self.detect_overlaps(sessions, timestamp_utc)
        if horizon_hours is not None:
            config = self._config.model_copy(
                update={
                    "transitions": self._config.transitions.model_copy(
                        update={"forecast_hours": horizon_hours},
                    ),
                },
            )
            lifecycle = LifecycleManager(config, self._tz)
            _next, transitions = lifecycle.forecast_transitions(
                timestamp_utc,
                sessions,
                kill_zones,
                overlaps,
            )
            return transitions
        _next, transitions = self._lifecycle.forecast_transitions(
            timestamp_utc,
            sessions,
            kill_zones,
            overlaps,
        )
        return transitions

    def resolve_daily_open(
        self,
        candles: list[NormalizedCandle],
        broker_timezone: str | None = None,
    ) -> PeriodOpen | None:
        """Resolve daily open from candles."""
        if not candles:
            return None
        ts = candles[-1].close_time_utc or candles[-1].open_time_utc
        return self._lifecycle.resolve_daily_open(
            candles,
            ts,
            broker_timezone or self._config.broker_timezone,
        )

    def resolve_weekly_open(
        self,
        candles: list[NormalizedCandle],
        broker_timezone: str | None = None,
    ) -> PeriodOpen | None:
        """Resolve weekly open from candles."""
        if not candles:
            return None
        ts = candles[-1].close_time_utc or candles[-1].open_time_utc
        return self._lifecycle.resolve_weekly_open(
            candles,
            ts,
            broker_timezone or self._config.broker_timezone,
        )

    def resolve_monthly_open(
        self,
        candles: list[NormalizedCandle],
        broker_timezone: str | None = None,
    ) -> PeriodOpen | None:
        """Resolve monthly open from candles."""
        if not candles:
            return None
        ts = candles[-1].close_time_utc or candles[-1].open_time_utc
        return self._lifecycle.resolve_monthly_open(
            candles,
            ts,
            broker_timezone or self._config.broker_timezone,
        )

    def track_session_extremes(
        self,
        candles: list[NormalizedCandle],
        sessions: list[TradingSessionState],
        prior_extremes: dict[str, object] | None = None,
        *,
        trading_day_id: str | None = None,
    ) -> list:
        """Track session highs and lows from candles."""
        if not candles:
            return []
        ts = candles[-1].close_time_utc or candles[-1].open_time_utc
        day_id = trading_day_id or self._tz.trading_day_id(
            ts,
            self._config.broker_timezone,
            self._config.broker_day_start_hour,
        )
        return self._lifecycle.track_session_extremes(
            candles,
            sessions,
            day_id,
            prior_extremes=prior_extremes,
        )

    def compute_opening_range(
        self,
        candles: list[NormalizedCandle],
        session_id: TradingSessionId,
        timestamp_utc: datetime | None = None,
    ) -> OpeningRange | None:
        """Compute opening range for a session."""
        ts = timestamp_utc or (
            candles[-1].close_time_utc if candles else datetime.now(tz=UTC)
        )
        sessions = self.resolve_sessions(ts)
        session = next((s for s in sessions if s.session_id == session_id), None)
        if session is None:
            return None
        return self._lifecycle.compute_opening_range(candles, session, ts)

    def compute_initial_balance(
        self,
        candles: list[NormalizedCandle],
        session_id: TradingSessionId,
        timestamp_utc: datetime | None = None,
    ) -> InitialBalance | None:
        """Compute initial balance for a session."""
        ts = timestamp_utc or (
            candles[-1].close_time_utc if candles else datetime.now(tz=UTC)
        )
        sessions = self.resolve_sessions(ts)
        session = next((s for s in sessions if s.session_id == session_id), None)
        if session is None:
            return None
        return self._lifecycle.compute_initial_balance(candles, session, ts)

    def evaluate_time_filter(
        self,
        analysis_context: SessionAnalysis,
    ) -> TimeOfDayFilter:
        """Evaluate time-of-day filter from partial or full analysis context."""
        return self._lifecycle.evaluate_time_filter(
            active_sessions=analysis_context.active_sessions,
            active_kill_zones=analysis_context.active_kill_zones,
            calendar_is_weekend=analysis_context.calendar_context.is_weekend,
            calendar_is_holiday=analysis_context.calendar_context.is_holiday,
            timestamp_utc=analysis_context.timestamp_utc,
            kill_zones_all=analysis_context.kill_zones,
            sessions_all=analysis_context.active_sessions,
        )

    def resolve_calendar(
        self,
        timestamp_utc: datetime,
        broker_timezone: str | None = None,
    ) -> CalendarContext:
        """Resolve weekend, holiday, and DST calendar context."""
        return self._calendar.resolve_calendar_context(
            timestamp_utc,
            broker_timezone or self._config.broker_timezone,
        )

    def score_quality(
        self,
        analysis_parts: SessionAnalysis,
    ) -> tuple[str, Decimal, Decimal]:
        """Score quality tier, strength, and confidence from analysis."""
        tier, strength, confidence, _ = self._quality.score_analysis(
            sessions=analysis_parts.active_sessions,
            kill_zones=analysis_parts.kill_zones,
            overlaps=analysis_parts.overlaps,
            volatility_score=Decimal("0.5"),
            liquidity_score=Decimal("0.5"),
            historical_score=Decimal("0.5"),
        )
        return tier.value, strength, confidence

    def publish_events(
        self,
        analysis: SessionAnalysis,
        *,
        prior_state: MarketSessionsState | None = None,
    ) -> None:
        """Emit all session lifecycle events."""
        published_kinds: set[MarketSessionsEventKind] = set()
        for event in analysis.events:
            if event.kind is MarketSessionsEventKind.SESSION_ANALYSIS_UPDATED:
                continue
            if event.kind in published_kinds and event.kind in (
                MarketSessionsEventKind.KILL_ZONE_ENTERED,
                MarketSessionsEventKind.KILL_ZONE_EXITED,
            ):
                continue
            published_kinds.add(event.kind)
            self._publisher.publish_from_timeline_event(event, analysis)
        self._publisher.publish_analysis_completed(analysis)

    def reset_state(self) -> None:
        """Clear persisted continuity state."""
        self._prior_state = None
        logger.info("Market sessions engine state reset")

    def handle_config_updated(self, config: MarketSessionsConfig) -> None:
        """Hot reload configuration and rebuild detector."""
        validate_config_timezones(config)
        self._config = config
        self._detector = MarketSessionsDetector(config)
        self._validator = MarketSessionsInputValidator(config)
        self._calendar = CalendarResolver(config, self._tz)
        self._sessions = SessionResolver(config, self._tz)
        self._kill_zones = KillZoneResolver(config, self._tz)
        self._lifecycle = LifecycleManager(config, self._tz)
        self._quality = QualityScorer(config)
        logger.info("Market sessions configuration updated")
