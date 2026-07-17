"""Kill zone window resolution and activation."""

from datetime import datetime
from decimal import Decimal

from backend.engines.market_sessions.config import MarketSessionsConfig
from backend.engines.market_sessions.schemas import (
    KILL_ZONE_DISPLAY_NAMES,
    KillZoneId,
    KillZoneState,
    SessionQualityTier,
    TradingSessionId,
    TradingSessionState,
    VolatilityProfile,
)
from backend.engines.market_sessions.timezone import TimezoneNormalizer


class KillZoneResolver:
    """Resolve ICT-style kill zone windows and quality."""

    def __init__(
        self,
        config: MarketSessionsConfig,
        normalizer: TimezoneNormalizer | None = None,
    ) -> None:
        self._config = config
        self._tz = normalizer or TimezoneNormalizer()

    def resolve_kill_zone_window(
        self,
        kill_zone_id: KillZoneId,
        timestamp_utc: datetime,
    ) -> tuple[datetime, datetime]:
        """Compute UTC window for kill zone at reference time."""
        kz_cfg = self._config.kill_zones[kill_zone_id.value]
        if kz_cfg.use_dst_adjustment:
            session_cfg = self._config.sessions[kz_cfg.parent_session]
            return self._tz.resolve_local_window_utc(
                timestamp_utc,
                session_cfg.timezone,
                kz_cfg.utc_start,
                kz_cfg.utc_end,
            )
        return self._tz.resolve_utc_window(
            timestamp_utc,
            kz_cfg.utc_start,
            kz_cfg.utc_end,
        )

    def resolve_kill_zone(
        self,
        kill_zone_id: KillZoneId,
        timestamp_utc: datetime,
        sessions: list[TradingSessionState],
        *,
        market_closed: bool = False,
        quality_score: Decimal | None = None,
        liquidity_score: Decimal | None = None,
        historical_score: Decimal | None = None,
        volatility: VolatilityProfile = VolatilityProfile.UNDETERMINED,
    ) -> KillZoneState:
        """Build kill zone state for reference time."""
        kz_cfg = self._config.kill_zones.get(kill_zone_id.value)
        evidence: list[str] = []
        if kz_cfg is None or not kz_cfg.enabled:
            now = timestamp_utc
            return KillZoneState(
                kill_zone_id=kill_zone_id,
                display_name=KILL_ZONE_DISPLAY_NAMES[kill_zone_id],
                parent_session=TradingSessionId.LONDON,
                is_active=False,
                window_start_utc=now,
                window_end_utc=now,
                elapsed_minutes=0,
                remaining_minutes=0,
                quality=SessionQualityTier.LOW,
                quality_score=Decimal("0"),
                volatility_profile=VolatilityProfile.UNDETERMINED,
                liquidity_score=Decimal("0"),
                historical_score=Decimal("0"),
                evidence=["Kill zone disabled in configuration"],
            )

        try:
            parent_session = TradingSessionId(kz_cfg.parent_session)
        except ValueError:
            parent_session = TradingSessionId.LONDON

        window_start, window_end = self.resolve_kill_zone_window(
            kill_zone_id,
            timestamp_utc,
        )
        in_window = self._tz.is_time_in_window(timestamp_utc, window_start, window_end)

        parent_active = any(
            session.session_id == parent_session and session.is_active
            for session in sessions
        )
        require_parent = self._config.kill_zones_require_active_session
        is_active = (
            not market_closed
            and in_window
            and (parent_active or not require_parent)
        )

        elapsed = self._tz.minutes_between(window_start, timestamp_utc) if is_active else 0
        remaining = self._tz.minutes_between(timestamp_utc, window_end) if is_active else 0

        if is_active:
            evidence.append(
                f"{KILL_ZONE_DISPLAY_NAMES[kill_zone_id]} active",
            )
            evidence.append(
                f"Window {window_start.isoformat()} – {window_end.isoformat()} UTC",
            )
        elif in_window and require_parent and not parent_active:
            evidence.append(
                f"{KILL_ZONE_DISPLAY_NAMES[kill_zone_id]} window open but parent session inactive",
            )
        else:
            evidence.append(f"{KILL_ZONE_DISPLAY_NAMES[kill_zone_id]} inactive")

        score = quality_score if quality_score is not None else (
            Decimal("0.65") if is_active else Decimal("0.15")
        )
        liq = liquidity_score if liquidity_score is not None else Decimal("0.5")
        hist = historical_score if historical_score is not None else Decimal("0.5")

        return KillZoneState(
            kill_zone_id=kill_zone_id,
            display_name=KILL_ZONE_DISPLAY_NAMES[kill_zone_id],
            parent_session=parent_session,
            is_active=is_active,
            window_start_utc=window_start,
            window_end_utc=window_end,
            elapsed_minutes=elapsed,
            remaining_minutes=remaining,
            quality=self._tier_from_score(score),
            quality_score=score,
            volatility_profile=volatility,
            liquidity_score=liq,
            historical_score=hist,
            evidence=evidence,
        )

    def resolve_all_kill_zones(
        self,
        timestamp_utc: datetime,
        sessions: list[TradingSessionState],
        *,
        market_closed: bool = False,
        kill_zone_scores: dict[KillZoneId, Decimal] | None = None,
        liquidity_scores: dict[KillZoneId, Decimal] | None = None,
        historical_scores: dict[KillZoneId, Decimal] | None = None,
        volatility_profiles: dict[KillZoneId, VolatilityProfile] | None = None,
    ) -> list[KillZoneState]:
        """Resolve all configured kill zones."""
        scores = kill_zone_scores or {}
        liquidity = liquidity_scores or {}
        historical = historical_scores or {}
        volatilities = volatility_profiles or {}
        return [
            self.resolve_kill_zone(
                kill_zone_id,
                timestamp_utc,
                sessions,
                market_closed=market_closed,
                quality_score=scores.get(kill_zone_id),
                liquidity_score=liquidity.get(kill_zone_id),
                historical_score=historical.get(kill_zone_id),
                volatility=volatilities.get(kill_zone_id, VolatilityProfile.UNDETERMINED),
            )
            for kill_zone_id in KillZoneId
        ]

    @staticmethod
    def _tier_from_score(score: Decimal) -> SessionQualityTier:
        if score >= Decimal("0.7"):
            return SessionQualityTier.HIGH
        if score >= Decimal("0.4"):
            return SessionQualityTier.MEDIUM
        return SessionQualityTier.LOW
