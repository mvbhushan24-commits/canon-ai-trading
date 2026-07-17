"""Session lifecycle: opens, extremes, OR/IB, filters, and transitions."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_sessions.config import MarketSessionsConfig
from backend.engines.market_sessions.schemas import (
    BreakoutDirection,
    FilterMode,
    InitialBalance,
    KillZoneId,
    MarketSessionsEvent,
    MarketSessionsEventKind,
    MarketSessionsState,
    OpeningRange,
    PeriodOpen,
    PeriodType,
    SessionExtreme,
    SessionPhase,
    SessionQualityTier,
    SessionTransition,
    TimeOfDayFilter,
    TradingSessionId,
    TradingSessionState,
    TransitionType,
)
from backend.engines.market_sessions.timezone import TimezoneNormalizer


class LifecycleManager:
    """Manage period opens, extremes, OR/IB, filters, and state continuity."""

    def __init__(
        self,
        config: MarketSessionsConfig,
        normalizer: TimezoneNormalizer | None = None,
    ) -> None:
        self._config = config
        self._tz = normalizer or TimezoneNormalizer()

    def resolve_daily_open(
        self,
        candles: list[NormalizedCandle],
        timestamp_utc: datetime,
        broker_timezone: str,
    ) -> PeriodOpen | None:
        """Resolve daily open from broker day boundary."""
        if not self._config.opens.daily_enabled:
            return None
        boundary = self._tz.broker_day_boundary_utc(
            timestamp_utc,
            broker_timezone,
            self._config.broker_day_start_hour,
        )
        return self._resolve_period_open(
            candles,
            boundary,
            PeriodType.DAILY,
            require_closed=self._config.opens.daily_require_closed_candle,
            broker_midnight=boundary,
        )

    def resolve_weekly_open(
        self,
        candles: list[NormalizedCandle],
        timestamp_utc: datetime,
        broker_timezone: str,
    ) -> PeriodOpen | None:
        """Resolve weekly open from configured week start."""
        if not self._config.opens.weekly_enabled:
            return None
        from backend.engines.market_sessions.calendar import CalendarResolver

        calendar = CalendarResolver(self._config, self._tz)
        broker_local = self._tz.to_broker_local(timestamp_utc, broker_timezone)
        week_start = calendar.week_start_date(broker_local)
        tz = self._tz
        boundary = tz.combine_local(
            week_start,
            tz.parse_hhmm(f"{self._config.broker_day_start_hour:02d}:00"),
            broker_timezone,
        )
        return self._resolve_period_open(
            candles,
            boundary,
            PeriodType.WEEKLY,
            require_closed=self._config.opens.weekly_require_closed_candle,
        )

    def resolve_monthly_open(
        self,
        candles: list[NormalizedCandle],
        timestamp_utc: datetime,
        broker_timezone: str,
    ) -> PeriodOpen | None:
        """Resolve monthly open from broker-local month start."""
        if not self._config.opens.monthly_enabled:
            return None
        from backend.engines.market_sessions.calendar import CalendarResolver

        calendar = CalendarResolver(self._config, self._tz)
        broker_local = self._tz.to_broker_local(timestamp_utc, broker_timezone)
        month_start = calendar.month_start_date(broker_local)
        boundary = self._tz.combine_local(
            month_start,
            self._tz.parse_hhmm(f"{self._config.broker_day_start_hour:02d}:00"),
            broker_timezone,
        )
        return self._resolve_period_open(
            candles,
            boundary,
            PeriodType.MONTHLY,
            require_closed=self._config.opens.monthly_require_closed_candle,
        )

    def _resolve_period_open(
        self,
        candles: list[NormalizedCandle],
        boundary_utc: datetime,
        period_type: PeriodType,
        *,
        require_closed: bool,
        broker_midnight: datetime | None = None,
    ) -> PeriodOpen | None:
        closed = sorted(
            [c for c in candles if c.is_closed or not require_closed],
            key=lambda c: c.open_time_utc,
        )
        candidates = [
            (index, candle)
            for index, candle in enumerate(closed)
            if candle.open_time_utc >= boundary_utc
        ]
        if not candidates:
            return PeriodOpen(
                period_type=period_type,
                open_price=Decimal("0"),
                open_time_utc=boundary_utc,
                is_confirmed=False,
                broker_midnight_utc=broker_midnight,
                evidence=[f"{period_type.value} open undetermined — no candle at boundary"],
            )

        index, candle = candidates[0]
        confirmed = candle.is_closed if require_closed else True
        evidence = [
            f"{period_type.value.title()} open at {candle.open} "
            f"({candle.open_time_utc.isoformat()})",
        ]
        if not confirmed:
            evidence.append("Open candle not yet closed")

        return PeriodOpen(
            period_type=period_type,
            open_price=candle.open,
            open_time_utc=candle.open_time_utc,
            bar_index=index,
            broker_midnight_utc=broker_midnight,
            is_confirmed=confirmed,
            evidence=evidence,
        )

    def track_session_extremes(
        self,
        candles: list[NormalizedCandle],
        sessions: list[TradingSessionState],
        trading_day_id: str,
        *,
        prior_extremes: dict[str, SessionExtreme] | None = None,
        liquidity_state: LiquidityState | None = None,
    ) -> list[SessionExtreme]:
        """Track per-session high/low for current trading day."""
        if not self._config.session_extremes.enabled:
            return []

        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda c: c.open_time_utc,
        )
        prior = prior_extremes or {}
        results: list[SessionExtreme] = []

        for session in sessions:
            session_candles = [
                candle
                for candle in closed
                if self._tz.is_time_in_window(
                    candle.open_time_utc,
                    session.window_start_utc,
                    session.window_end_utc,
                )
            ]
            cache_key = f"{trading_day_id}:{session.session_id.value}"
            prior_extreme = prior.get(cache_key)

            if not session_candles and prior_extreme is not None:
                results.append(prior_extreme)
                continue
            if not session_candles:
                continue

            high_candle = max(session_candles, key=lambda c: c.high)
            low_candle = min(session_candles, key=lambda c: c.low)
            range_pips = (high_candle.high - low_candle.low) / Decimal(
                str(self._config.pip_size),
            )

            evidence: list[str] = []
            if (
                self._config.session_extremes.cross_validate_liquidity
                and liquidity_state is not None
            ):
                evidence.append("Liquidity cross-validation applied")

            extreme = SessionExtreme(
                session_id=session.session_id,
                session_high=high_candle.high,
                session_low=low_candle.low,
                high_time_utc=high_candle.open_time_utc,
                low_time_utc=low_candle.open_time_utc,
                range_size_pips=range_pips,
                is_complete=not session.is_active,
            )
            results.append(extreme)

        return results

    def compute_opening_range(
        self,
        candles: list[NormalizedCandle],
        session: TradingSessionState,
        timestamp_utc: datetime,
    ) -> OpeningRange | None:
        """Compute opening range for session when configured."""
        if not self._config.opening_range.enabled:
            return None
        if session.session_id.value not in self._config.opening_range.sessions:
            return None

        formation_end = session.window_start_utc + timedelta(
            minutes=self._config.opening_range.duration_minutes,
        )
        window_candles = [
            c
            for c in candles
            if c.is_closed
            and session.window_start_utc <= c.open_time_utc < formation_end
        ]
        range_id = f"or-{session.session_id.value}-{session.window_start_utc.date().isoformat()}"

        if len(window_candles) < self._config.opening_range.min_candles:
            return None

        high = max(c.high for c in window_candles)
        low = min(c.low for c in window_candles)
        midpoint = (high + low) / 2
        range_pips = (high - low) / Decimal(str(self._config.pip_size))
        is_complete = timestamp_utc >= formation_end

        breakout = BreakoutDirection.NONE
        if is_complete and candles:
            last_close = window_candles[-1].close if window_candles else candles[-1].close
            buffer = Decimal(str(self._config.opening_range.breakout_buffer_pips)) * Decimal(
                str(self._config.pip_size),
            )
            recent = [c for c in candles if c.is_closed][-1]
            price = recent.close
            if price > high + buffer:
                breakout = BreakoutDirection.BULLISH
            elif price < low - buffer:
                breakout = BreakoutDirection.BEARISH

        strength = min(Decimal("1"), range_pips / Decimal("50"))
        tier = (
            SessionQualityTier.HIGH
            if strength >= Decimal("0.7")
            else SessionQualityTier.MEDIUM
            if strength >= Decimal("0.4")
            else SessionQualityTier.LOW
        )

        return OpeningRange(
            range_id=range_id,
            session_id=session.session_id,
            high=high,
            low=low,
            midpoint=midpoint,
            range_size_pips=range_pips,
            formation_start_utc=session.window_start_utc,
            formation_end_utc=formation_end,
            duration_minutes=self._config.opening_range.duration_minutes,
            is_complete=is_complete,
            breakout_direction=breakout if is_complete else BreakoutDirection.UNDETERMINED,
            quality=tier,
            strength=strength,
            evidence=[
                f"Opening range for {session.session_id.value}: "
                f"{low} – {high} ({range_pips} pips)",
            ],
        )

    def compute_initial_balance(
        self,
        candles: list[NormalizedCandle],
        session: TradingSessionState,
        timestamp_utc: datetime,
    ) -> InitialBalance | None:
        """Compute initial balance for session when configured."""
        if not self._config.initial_balance.enabled:
            return None
        if session.session_id.value not in self._config.initial_balance.sessions:
            return None

        formation_end = session.window_start_utc + timedelta(
            minutes=self._config.initial_balance.duration_minutes,
        )
        window_candles = [
            c
            for c in candles
            if c.is_closed
            and session.window_start_utc <= c.open_time_utc < formation_end
        ]
        balance_id = f"ib-{session.session_id.value}-{session.window_start_utc.date().isoformat()}"

        if len(window_candles) < self._config.initial_balance.min_candles:
            return None

        high = max(c.high for c in window_candles)
        low = min(c.low for c in window_candles)
        midpoint = (high + low) / 2
        range_pips = (high - low) / Decimal(str(self._config.pip_size))
        is_complete = timestamp_utc >= formation_end

        extension_high: Decimal | None = None
        extension_low: Decimal | None = None
        threshold = Decimal(str(self._config.initial_balance.extension_threshold_pips)) * Decimal(
            str(self._config.pip_size),
        )
        if is_complete:
            post_candles = [
                c
                for c in candles
                if c.is_closed and c.open_time_utc >= formation_end
            ]
            if post_candles:
                max_high = max(c.high for c in post_candles)
                min_low = min(c.low for c in post_candles)
                if max_high > high + threshold:
                    extension_high = max_high
                if min_low < low - threshold:
                    extension_low = min_low

        strength = min(Decimal("1"), range_pips / Decimal("80"))
        tier = (
            SessionQualityTier.HIGH
            if strength >= Decimal("0.7")
            else SessionQualityTier.MEDIUM
            if strength >= Decimal("0.4")
            else SessionQualityTier.LOW
        )

        return InitialBalance(
            balance_id=balance_id,
            session_id=session.session_id,
            high=high,
            low=low,
            midpoint=midpoint,
            range_size_pips=range_pips,
            formation_start_utc=session.window_start_utc,
            formation_end_utc=formation_end,
            duration_minutes=self._config.initial_balance.duration_minutes,
            is_complete=is_complete,
            extension_high=extension_high,
            extension_low=extension_low,
            quality=tier,
            strength=strength,
            evidence=[
                f"Initial balance for {session.session_id.value}: "
                f"{low} – {high} ({range_pips} pips)",
            ],
        )

    def evaluate_time_filter(
        self,
        *,
        active_sessions: list[TradingSessionState],
        active_kill_zones: list,
        calendar_is_weekend: bool,
        calendar_is_holiday: bool,
        timestamp_utc: datetime,
        kill_zones_all: list,
        sessions_all: list[TradingSessionState],
    ) -> TimeOfDayFilter:
        """Evaluate time-of-day filter for current context."""
        cfg = self._config.time_of_day_filter
        mode = FilterMode(cfg.mode)
        active_window_ids: list[str] = []
        blocked_reasons: list[str] = []

        for session in active_sessions:
            if session.is_active:
                active_window_ids.append(session.session_id.value)
        for kz in active_kill_zones:
            if kz.is_active:
                active_window_ids.append(kz.kill_zone_id.value)

        if mode is FilterMode.DISABLED:
            return TimeOfDayFilter(
                filter_mode=mode,
                is_allowed=True,
                active_windows=active_window_ids,
            )

        if cfg.block_weekends and calendar_is_weekend:
            blocked_reasons.append("Weekend blocked by filter")
        if cfg.block_holidays and calendar_is_holiday:
            blocked_reasons.append("Holiday blocked by filter")
        if cfg.block_outside_sessions and not any(s.is_active for s in active_sessions):
            blocked_reasons.append("No active session")

        if mode is FilterMode.KILL_ZONE_ONLY and not any(kz.is_active for kz in active_kill_zones):
            blocked_reasons.append("No active kill zone at reference time")

        if mode is FilterMode.ALLOW_LIST:
            allowed = set(cfg.allow_list)
            if not any(window_id in allowed for window_id in active_window_ids):
                blocked_reasons.append("Current window not in allow_list")

        if mode is FilterMode.BLOCK_LIST:
            blocked = set(cfg.block_list)
            if any(window_id in blocked for window_id in active_window_ids):
                blocked_reasons.append("Active window in block_list")

        is_allowed = not blocked_reasons
        next_allowed = None
        if not is_allowed:
            next_allowed = self._estimate_next_allowed(
                timestamp_utc,
                kill_zones_all,
                sessions_all,
                mode,
                cfg,
            )

        return TimeOfDayFilter(
            filter_mode=mode,
            is_allowed=is_allowed,
            active_windows=active_window_ids,
            blocked_reasons=blocked_reasons,
            next_allowed_utc=next_allowed,
        )

    def _estimate_next_allowed(
        self,
        timestamp_utc: datetime,
        kill_zones: list,
        sessions: list[TradingSessionState],
        mode: FilterMode,
        cfg,
    ) -> datetime | None:
        """Estimate next time filter permits analysis."""
        probe = timestamp_utc
        for _ in range(48):
            probe += timedelta(hours=1)
            active_sessions = [
                s
                for s in sessions
                if self._tz.is_time_in_window(probe, s.window_start_utc, s.window_end_utc)
            ]
            active_kz = [
                kz
                for kz in kill_zones
                if self._tz.is_time_in_window(probe, kz.window_start_utc, kz.window_end_utc)
            ]
            window_ids = [s.session_id.value for s in active_sessions] + [
                kz.kill_zone_id.value for kz in active_kz
            ]
            if mode is FilterMode.KILL_ZONE_ONLY and active_kz:
                return probe
            if mode is FilterMode.ALLOW_LIST and any(
                w in cfg.allow_list for w in window_ids
            ):
                return probe
            if mode is FilterMode.BLOCK_LIST and window_ids and not any(
                w in cfg.block_list for w in window_ids
            ):
                return probe
            if mode is FilterMode.DISABLED:
                return probe
        return None

    def forecast_transitions(
        self,
        timestamp_utc: datetime,
        sessions: list[TradingSessionState],
        kill_zones: list,
        overlaps: list,
    ) -> tuple[SessionTransition | None, list[SessionTransition]]:
        """Forecast next transition and collect recent transitions."""
        horizon = timedelta(hours=self._config.transitions.forecast_hours)
        lookback = timedelta(hours=self._config.transitions.recent_lookback_hours)
        imminent = timedelta(minutes=self._config.transitions.imminent_minutes)
        candidates: list[SessionTransition] = []

        for session in sessions:
            for boundary, t_type, to_phase in (
                (session.window_start_utc, TransitionType.SESSION_START, SessionPhase.OPENING),
                (session.window_end_utc, TransitionType.SESSION_END, SessionPhase.INACTIVE),
            ):
                if timestamp_utc <= boundary <= timestamp_utc + horizon:
                    candidates.append(
                        SessionTransition(
                            transition_id=f"{session.session_id.value}-{t_type.value}",
                            session_id=session.session_id,
                            transition_type=t_type,
                            transition_time_utc=boundary,
                            from_phase=session.phase,
                            to_phase=to_phase,
                            is_imminent=boundary - timestamp_utc <= imminent,
                        ),
                    )

        for kz in kill_zones:
            for boundary, t_type in (
                (kz.window_start_utc, TransitionType.KILL_ZONE_START),
                (kz.window_end_utc, TransitionType.KILL_ZONE_END),
            ):
                if timestamp_utc <= boundary <= timestamp_utc + horizon:
                    candidates.append(
                        SessionTransition(
                            transition_id=f"{kz.kill_zone_id.value}-{t_type.value}",
                            kill_zone_id=kz.kill_zone_id,
                            transition_type=t_type,
                            transition_time_utc=boundary,
                            from_phase=SessionPhase.INACTIVE,
                            to_phase=SessionPhase.OPENING,
                            is_imminent=boundary - timestamp_utc <= imminent,
                        ),
                    )

        recent = [
            transition
            for transition in candidates
            if transition.transition_time_utc >= timestamp_utc - lookback
            and transition.transition_time_utc <= timestamp_utc
        ]
        future = [
            transition
            for transition in candidates
            if transition.transition_time_utc > timestamp_utc
        ]
        next_transition = min(future, key=lambda t: t.transition_time_utc) if future else None
        return next_transition, sorted(recent, key=lambda t: t.transition_time_utc)

    def build_timeline_events(
        self,
        *,
        prior_state: MarketSessionsState | None,
        active_sessions: list[TradingSessionState],
        active_kill_zones: list,
        overlaps: list,
        session_extremes: list[SessionExtreme],
        opening_range: OpeningRange | None,
        initial_balance: InitialBalance | None,
        calendar_is_weekend: bool,
        calendar_is_holiday: bool,
        quality_tier: SessionQualityTier,
        quality_score: Decimal,
        transitions: list[SessionTransition],
        timestamp_utc: datetime,
        trading_day_id: str = "",
        daily_open: PeriodOpen | None = None,
        weekly_open: PeriodOpen | None = None,
        monthly_open: PeriodOpen | None = None,
        prior_daily_open: PeriodOpen | None = None,
        prior_weekly_open: PeriodOpen | None = None,
        prior_monthly_open: PeriodOpen | None = None,
        is_dst_transition: bool = False,
        time_filter: TimeOfDayFilter | None = None,
    ) -> list[MarketSessionsEvent]:
        """Build timeline events by comparing prior and current state."""
        events: list[MarketSessionsEvent] = []
        prior = prior_state or MarketSessionsState()

        if calendar_is_weekend and not prior.was_weekend:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.WEEKEND_DETECTED,
                    timestamp_utc=timestamp_utc,
                    description="Weekend state entered",
                ),
            )
        if calendar_is_holiday and not prior.was_holiday:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.HOLIDAY_DETECTED,
                    timestamp_utc=timestamp_utc,
                    description="Holiday state entered",
                ),
            )
        if is_dst_transition:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.DST_TRANSITION,
                    timestamp_utc=timestamp_utc,
                    description="DST transition detected within configured window",
                ),
            )

        if daily_open and daily_open.is_confirmed:
            if prior_daily_open is None or prior_daily_open.open_time_utc != daily_open.open_time_utc:
                events.append(
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.DAILY_OPEN_RESOLVED,
                        timestamp_utc=daily_open.open_time_utc,
                        description=f"Daily open resolved at {daily_open.open_price}",
                    ),
                )
        if weekly_open and weekly_open.is_confirmed:
            if prior_weekly_open is None or prior_weekly_open.open_time_utc != weekly_open.open_time_utc:
                events.append(
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.WEEKLY_OPEN_RESOLVED,
                        timestamp_utc=weekly_open.open_time_utc,
                        description=f"Weekly open resolved at {weekly_open.open_price}",
                    ),
                )
        if monthly_open and monthly_open.is_confirmed:
            if prior_monthly_open is None or prior_monthly_open.open_time_utc != monthly_open.open_time_utc:
                events.append(
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.MONTHLY_OPEN_RESOLVED,
                        timestamp_utc=monthly_open.open_time_utc,
                        description=f"Monthly open resolved at {monthly_open.open_price}",
                    ),
                )

        if time_filter is not None and not time_filter.is_allowed:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.TIME_FILTER_BLOCKED,
                    timestamp_utc=timestamp_utc,
                    description="; ".join(time_filter.blocked_reasons)
                    or "Time-of-day filter blocked",
                ),
            )

        prior_sessions = set(prior.active_session_ids)
        current_sessions = {s.session_id for s in active_sessions if s.is_active}
        for session_id in current_sessions - prior_sessions:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.SESSION_STARTED,
                    timestamp_utc=timestamp_utc,
                    description=f"Session {session_id.value} started",
                    session_id=session_id,
                ),
            )
        for session_id in prior_sessions - current_sessions:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.SESSION_ENDED,
                    timestamp_utc=timestamp_utc,
                    description=f"Session {session_id.value} ended",
                    session_id=session_id,
                ),
            )

        prior_kz = set(prior.active_kill_zone_ids)
        current_kz = {kz.kill_zone_id for kz in active_kill_zones if kz.is_active}
        for kz_id in current_kz - prior_kz:
            events.extend(
                [
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.KILL_ZONE_STARTED,
                        timestamp_utc=timestamp_utc,
                        description=f"Kill zone {kz_id.value} started",
                        kill_zone_id=kz_id,
                    ),
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.KILL_ZONE_ENTERED,
                        timestamp_utc=timestamp_utc,
                        description=f"Kill zone {kz_id.value} entered",
                        kill_zone_id=kz_id,
                    ),
                ],
            )
        for kz_id in prior_kz - current_kz:
            events.extend(
                [
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.KILL_ZONE_ENDED,
                        timestamp_utc=timestamp_utc,
                        description=f"Kill zone {kz_id.value} ended",
                        kill_zone_id=kz_id,
                    ),
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.KILL_ZONE_EXITED,
                        timestamp_utc=timestamp_utc,
                        description=f"Kill zone {kz_id.value} exited",
                        kill_zone_id=kz_id,
                    ),
                ],
            )

        prior_overlaps = set(prior.active_overlap_ids)
        current_overlaps = {o.overlap_id for o in overlaps if o.is_active}
        for overlap_id in current_overlaps - prior_overlaps:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.OVERLAP_STARTED,
                    timestamp_utc=timestamp_utc,
                    description=f"Overlap {overlap_id} started",
                    overlap_id=overlap_id,
                ),
            )
        for overlap_id in prior_overlaps - current_overlaps:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.OVERLAP_ENDED,
                    timestamp_utc=timestamp_utc,
                    description=f"Overlap {overlap_id} ended",
                    overlap_id=overlap_id,
                ),
            )

        for transition in transitions:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.SESSION_TRANSITION_DETECTED,
                    timestamp_utc=transition.transition_time_utc,
                    description=f"Transition {transition.transition_type.value}",
                    session_id=transition.session_id,
                    kill_zone_id=transition.kill_zone_id,
                    overlap_id=transition.overlap_id,
                ),
            )

        if (
            prior.last_quality_tier != quality_tier
            or prior.last_quality_score != quality_score
        ):
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.SESSION_QUALITY_UPDATED,
                    timestamp_utc=timestamp_utc,
                    description=f"Quality updated to {quality_tier.value} ({quality_score})",
                ),
            )

        if opening_range and opening_range.is_complete:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.OPENING_RANGE_COMPLETE,
                    timestamp_utc=opening_range.formation_end_utc,
                    description=f"Opening range complete for {opening_range.session_id.value}",
                    session_id=opening_range.session_id,
                ),
            )
            if opening_range.breakout_direction in (
                BreakoutDirection.BULLISH,
                BreakoutDirection.BEARISH,
            ):
                events.append(
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.OPENING_RANGE_BREAKOUT,
                        timestamp_utc=timestamp_utc,
                        description=f"OR breakout {opening_range.breakout_direction.value}",
                        session_id=opening_range.session_id,
                    ),
                )

        if initial_balance and initial_balance.is_complete:
            events.append(
                MarketSessionsEvent(
                    kind=MarketSessionsEventKind.INITIAL_BALANCE_COMPLETE,
                    timestamp_utc=initial_balance.formation_end_utc,
                    description=f"Initial balance complete for {initial_balance.session_id.value}",
                    session_id=initial_balance.session_id,
                ),
            )
            if initial_balance.extension_high or initial_balance.extension_low:
                events.append(
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.INITIAL_BALANCE_EXTENSION,
                        timestamp_utc=timestamp_utc,
                        description="Initial balance extension detected",
                        session_id=initial_balance.session_id,
                    ),
                )

        for extreme in session_extremes:
            cache_key = f"{trading_day_id}:{extreme.session_id.value}"
            prior_extreme = prior.session_extremes_cache.get(cache_key)
            if prior_extreme and extreme.session_high > prior_extreme.session_high:
                events.append(
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.SESSION_HIGH_UPDATED,
                        timestamp_utc=extreme.high_time_utc,
                        description=f"Session high updated for {extreme.session_id.value}",
                        session_id=extreme.session_id,
                    ),
                )
            if prior_extreme and extreme.session_low < prior_extreme.session_low:
                events.append(
                    MarketSessionsEvent(
                        kind=MarketSessionsEventKind.SESSION_LOW_UPDATED,
                        timestamp_utc=extreme.low_time_utc,
                        description=f"Session low updated for {extreme.session_id.value}",
                        session_id=extreme.session_id,
                    ),
                )

        return events

    def update_state(
        self,
        *,
        prior_state: MarketSessionsState | None,
        timestamp_utc: datetime,
        primary_session: TradingSessionId | None,
        session_phase: SessionPhase,
        session_extremes: list[SessionExtreme],
        opening_range: OpeningRange | None,
        initial_balance: InitialBalance | None,
        daily_open: PeriodOpen | None,
        weekly_open: PeriodOpen | None,
        monthly_open: PeriodOpen | None,
        active_sessions: list[TradingSessionState],
        active_kill_zones: list,
        overlaps: list,
        calendar_is_weekend: bool,
        calendar_is_holiday: bool,
        quality_tier: SessionQualityTier,
        quality_score: Decimal,
        bar_count: int,
        trading_day_id: str,
    ) -> MarketSessionsState:
        """Build updated continuity state."""
        extremes_cache: dict[str, SessionExtreme] = {}
        if prior_state and not self._config.session_extremes.reset_at_daily_open:
            extremes_cache.update(prior_state.session_extremes_cache)
        for extreme in session_extremes:
            key = f"{trading_day_id}:{extreme.session_id.value}"
            extremes_cache[key] = extreme

        or_cache: dict[str, OpeningRange] = {}
        ib_cache: dict[str, InitialBalance] = {}
        if prior_state:
            or_cache.update(prior_state.active_opening_ranges)
            ib_cache.update(prior_state.active_initial_balances)
        if opening_range:
            or_cache[opening_range.session_id.value] = opening_range
        if initial_balance:
            ib_cache[initial_balance.session_id.value] = initial_balance

        return MarketSessionsState(
            last_primary_session=primary_session,
            last_session_phase=session_phase,
            session_extremes_cache=extremes_cache,
            active_opening_ranges=or_cache,
            active_initial_balances=ib_cache,
            last_daily_open=daily_open or (prior_state.last_daily_open if prior_state else None),
            last_weekly_open=weekly_open or (prior_state.last_weekly_open if prior_state else None),
            last_monthly_open=monthly_open or (prior_state.last_monthly_open if prior_state else None),
            last_analysis_utc=timestamp_utc,
            bar_count=bar_count,
            active_session_ids=[s.session_id for s in active_sessions if s.is_active],
            active_kill_zone_ids=[kz.kill_zone_id for kz in active_kill_zones if kz.is_active],
            active_overlap_ids=[o.overlap_id for o in overlaps if o.is_active],
            was_weekend=calendar_is_weekend,
            was_holiday=calendar_is_holiday,
            last_quality_tier=quality_tier,
            last_quality_score=quality_score,
        )
