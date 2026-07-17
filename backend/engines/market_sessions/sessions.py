"""Trading session window resolution and phase classification."""

from datetime import datetime, timedelta
from decimal import Decimal

from backend.engines.market_sessions.config import MarketSessionsConfig
from backend.engines.market_sessions.schemas import (
    SESSION_DISPLAY_NAMES,
    SessionOverlap,
    SessionPhase,
    SessionQualityTier,
    TradingSessionId,
    TradingSessionState,
    VolatilityProfile,
)
from backend.engines.market_sessions.timezone import TimezoneNormalizer


class SessionResolver:
    """Resolve institutional trading session windows and phases."""

    def __init__(
        self,
        config: MarketSessionsConfig,
        normalizer: TimezoneNormalizer | None = None,
    ) -> None:
        self._config = config
        self._tz = normalizer or TimezoneNormalizer()

    def resolve_session_window(
        self,
        session_id: TradingSessionId,
        timestamp_utc: datetime,
    ) -> tuple[datetime, datetime]:
        """Compute UTC window bounds for a session at reference time."""
        session_cfg = self._config.sessions[session_id.value]
        return self._tz.resolve_local_window_utc(
            timestamp_utc,
            session_cfg.timezone,
            session_cfg.local_start,
            session_cfg.local_end,
        )

    def classify_phase(
        self,
        session_id: TradingSessionId,
        timestamp_utc: datetime,
        window_start_utc: datetime,
        window_end_utc: datetime,
        *,
        in_kill_zone: bool = False,
    ) -> SessionPhase:
        """Classify session phase at reference time."""
        if not self._tz.is_time_in_window(timestamp_utc, window_start_utc, window_end_utc):
            pre_open_start = window_start_utc - timedelta(
                minutes=self._config.session_phases.pre_open_minutes,
            )
            if pre_open_start <= timestamp_utc < window_start_utc:
                return SessionPhase.PRE_OPEN
            return SessionPhase.INACTIVE

        elapsed = self._tz.minutes_between(window_start_utc, timestamp_utc)
        remaining = self._tz.minutes_between(timestamp_utc, window_end_utc)

        if in_kill_zone or elapsed < self._config.session_phases.opening_phase_minutes:
            return SessionPhase.OPENING
        if remaining <= self._config.session_phases.closing_phase_minutes:
            return SessionPhase.CLOSING
        return SessionPhase.MID

    def resolve_session(
        self,
        session_id: TradingSessionId,
        timestamp_utc: datetime,
        *,
        market_closed: bool = False,
        partial_holiday_allowed: bool = True,
        in_kill_zone: bool = False,
        quality_score: Decimal | None = None,
        volatility: VolatilityProfile = VolatilityProfile.UNDETERMINED,
    ) -> TradingSessionState:
        """Build trading session state for reference time."""
        session_cfg = self._config.sessions.get(session_id.value)
        evidence: list[str] = []
        if session_cfg is None or not session_cfg.enabled:
            now = timestamp_utc
            return TradingSessionState(
                session_id=session_id,
                display_name=SESSION_DISPLAY_NAMES[session_id],
                is_active=False,
                phase=SessionPhase.INACTIVE,
                window_start_utc=now,
                window_end_utc=now,
                elapsed_minutes=0,
                remaining_minutes=0,
                quality=SessionQualityTier.LOW,
                quality_score=Decimal("0"),
                volatility_profile=VolatilityProfile.UNDETERMINED,
                evidence=["Session disabled in configuration"],
            )

        window_start, window_end = self.resolve_session_window(session_id, timestamp_utc)
        is_active = (
            not market_closed
            and partial_holiday_allowed
            and self._tz.is_time_in_window(timestamp_utc, window_start, window_end)
        )
        phase = self.classify_phase(
            session_id,
            timestamp_utc,
            window_start,
            window_end,
            in_kill_zone=in_kill_zone and is_active,
        )
        if not is_active and phase != SessionPhase.PRE_OPEN:
            phase = SessionPhase.INACTIVE

        elapsed = (
            self._tz.minutes_between(window_start, timestamp_utc) if is_active else 0
        )
        remaining = (
            self._tz.minutes_between(timestamp_utc, window_end) if is_active else 0
        )

        if is_active:
            evidence.append(
                f"{SESSION_DISPLAY_NAMES[session_id]} active — {phase.value} phase",
            )
            evidence.append(
                f"Window {window_start.isoformat()} – {window_end.isoformat()} UTC",
            )
        else:
            evidence.append(f"{SESSION_DISPLAY_NAMES[session_id]} inactive")

        score = quality_score if quality_score is not None else Decimal("0.3")
        tier = self._tier_from_score(score)

        return TradingSessionState(
            session_id=session_id,
            display_name=SESSION_DISPLAY_NAMES[session_id],
            is_active=is_active,
            phase=phase,
            window_start_utc=window_start,
            window_end_utc=window_end,
            elapsed_minutes=elapsed,
            remaining_minutes=remaining,
            quality=tier,
            quality_score=score,
            volatility_profile=volatility,
            evidence=evidence,
        )

    def resolve_all_sessions(
        self,
        timestamp_utc: datetime,
        *,
        market_closed: bool = False,
        partial_holiday_sessions: set[str] | None = None,
        active_kill_zone_sessions: set[TradingSessionId] | None = None,
        session_scores: dict[TradingSessionId, Decimal] | None = None,
        volatility_profiles: dict[TradingSessionId, VolatilityProfile] | None = None,
    ) -> list[TradingSessionState]:
        """Resolve all configured trading sessions."""
        partial = partial_holiday_sessions or set()
        kill_parents = active_kill_zone_sessions or set()
        scores = session_scores or {}
        volatilities = volatility_profiles or {}
        results: list[TradingSessionState] = []

        for session_id in TradingSessionId:
            allowed = True
            if partial_holiday_sessions is not None and partial:
                allowed = session_id.value in partial
            state = self.resolve_session(
                session_id,
                timestamp_utc,
                market_closed=market_closed,
                partial_holiday_allowed=allowed,
                in_kill_zone=session_id in kill_parents,
                quality_score=scores.get(session_id),
                volatility=volatilities.get(
                    session_id,
                    VolatilityProfile.UNDETERMINED,
                ),
            )
            results.append(state)
        return results

    def select_primary_session(
        self,
        sessions: list[TradingSessionState],
    ) -> TradingSessionId | None:
        """Select dominant session by configured priority among active sessions."""
        active = {session.session_id for session in sessions if session.is_active}
        if not active:
            pre_open = [
                session.session_id
                for session in sessions
                if session.phase == SessionPhase.PRE_OPEN
            ]
            for session_name in self._config.session_priority:
                try:
                    session_id = TradingSessionId(session_name)
                except ValueError:
                    continue
                if session_id in pre_open:
                    return session_id
            return None

        for session_name in self._config.session_priority:
            try:
                session_id = TradingSessionId(session_name)
            except ValueError:
                continue
            if session_id in active:
                return session_id
        return next(iter(active))

    def detect_overlaps(
        self,
        sessions: list[TradingSessionState],
        timestamp_utc: datetime,
    ) -> list[SessionOverlap]:
        """Detect configured session overlaps at reference time."""
        session_map = {session.session_id.value: session for session in sessions}
        overlaps: list[SessionOverlap] = []

        for overlap_id, overlap_cfg in self._config.overlaps.items():
            if not overlap_cfg.enabled or len(overlap_cfg.sessions) < 2:
                continue
            try:
                participants = [TradingSessionId(name) for name in overlap_cfg.sessions]
            except ValueError:
                continue

            participant_states = [session_map.get(name.value) for name in participants]
            if any(state is None for state in participant_states):
                continue
            assert all(state is not None for state in participant_states)
            typed_states: list[TradingSessionState] = participant_states  # type: ignore[assignment]

            if not all(state.is_active for state in typed_states):
                window_start = max(state.window_start_utc for state in typed_states)
                window_end = min(state.window_end_utc for state in typed_states)
                is_active = False
                quality_score = Decimal("0.2")
            else:
                window_start = max(state.window_start_utc for state in typed_states)
                window_end = min(state.window_end_utc for state in typed_states)
                is_active = (
                    window_start < window_end
                    and self._tz.is_time_in_window(
                        timestamp_utc,
                        window_start,
                        window_end,
                    )
                )
                quality_score = Decimal("0.75") if is_active else Decimal("0.2")

            evidence = [
                f"Overlap {overlap_id}: "
                + ", ".join(name.value for name in participants)
                + (" active" if is_active else " inactive"),
            ]
            overlaps.append(
                SessionOverlap(
                    overlap_id=overlap_id,
                    sessions=participants,
                    window_start_utc=window_start,
                    window_end_utc=window_end,
                    is_active=is_active,
                    quality=self._tier_from_score(quality_score),
                    quality_score=quality_score,
                    volatility_profile=VolatilityProfile.MODERATE
                    if is_active
                    else VolatilityProfile.UNDETERMINED,
                    evidence=evidence,
                ),
            )
        return overlaps

    @staticmethod
    def _tier_from_score(score: Decimal) -> SessionQualityTier:
        if score >= Decimal("0.7"):
            return SessionQualityTier.HIGH
        if score >= Decimal("0.4"):
            return SessionQualityTier.MEDIUM
        return SessionQualityTier.LOW
