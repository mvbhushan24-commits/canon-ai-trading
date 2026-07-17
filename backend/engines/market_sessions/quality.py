"""Quality scoring for sessions, kill zones, and composite analysis."""

from decimal import Decimal
from statistics import median

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_mitigation.schemas import MitigationBlock
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_order_block.schemas import OrderBlockStatus
from backend.engines.market_premium_discount.schemas import PremiumDiscountAnalysis
from backend.engines.market_sessions.config import MarketSessionsConfig
from backend.engines.market_sessions.schemas import (
    KillZoneId,
    KillZoneState,
    LiquidityAvailability,
    SessionOverlap,
    SessionPhase,
    SessionQualityTier,
    TradingSessionId,
    TradingSessionState,
    VolatilityProfile,
)
from backend.engines.market_structure import MarketStructure


class QualityScorer:
    """Evidence-weighted session and kill zone quality scoring."""

    def __init__(self, config: MarketSessionsConfig) -> None:
        self._config = config

    def score_session(
        self,
        session: TradingSessionState,
        *,
        calendar_clean: bool,
        has_overlap: bool,
    ) -> Decimal:
        """Score individual session quality."""
        if not session.is_active:
            return Decimal("0.15")

        phase_weights = {
            SessionPhase.OPENING: Decimal("0.85"),
            SessionPhase.MID: Decimal("0.65"),
            SessionPhase.CLOSING: Decimal("0.55"),
            SessionPhase.PRE_OPEN: Decimal("0.35"),
            SessionPhase.INACTIVE: Decimal("0.1"),
        }
        score = phase_weights.get(session.phase, Decimal("0.3"))
        if calendar_clean:
            score += Decimal("0.05")
        if has_overlap:
            score += Decimal("0.08")
        return min(Decimal("1"), score)

    def score_kill_zone(
        self,
        kill_zone: KillZoneState,
        *,
        volatility_score: Decimal,
        liquidity_score: Decimal,
        historical_score: Decimal,
    ) -> Decimal:
        """Score kill zone quality from timing and evidence factors."""
        if not kill_zone.is_active:
            return Decimal("0.15")

        timing = Decimal("0.6")
        if kill_zone.elapsed_minutes <= 30:
            timing = Decimal("0.85")
        elif kill_zone.elapsed_minutes <= 90:
            timing = Decimal("0.75")

        composite = (
            timing * Decimal("0.4")
            + volatility_score * Decimal("0.2")
            + liquidity_score * Decimal("0.25")
            + historical_score * Decimal("0.15")
        )
        return min(Decimal("1"), composite)

    def score_overlap(self, overlap: SessionOverlap) -> Decimal:
        """Score session overlap quality."""
        if not overlap.is_active:
            return Decimal("0.2")
        return Decimal("0.85")

    def profile_volatility(
        self,
        candles: list[NormalizedCandle],
        session: TradingSessionState | None = None,
    ) -> tuple[VolatilityProfile, Decimal]:
        """Derive volatility profile and score from candle ranges."""
        if not self._config.volatility.enabled:
            return VolatilityProfile.UNDETERMINED, Decimal("0.5")

        closed = [c for c in candles if c.is_closed]
        if len(closed) < self._config.volatility.min_candles_for_profile:
            return VolatilityProfile.UNDETERMINED, Decimal("0.5")

        if session is not None:
            session_candles = [
                c
                for c in closed
                if session.window_start_utc <= c.open_time_utc < session.window_end_utc
            ]
            target = session_candles or closed[-10:]
        else:
            target = closed[-20:]

        ranges = [float(c.high - c.low) for c in target]
        if not ranges:
            return VolatilityProfile.UNDETERMINED, Decimal("0.5")

        current = ranges[-1]
        baseline = median(ranges)
        if baseline <= 0:
            return VolatilityProfile.MODERATE, Decimal("0.5")

        ratio = current / baseline
        low_cut = self._config.volatility.low_percentile / 100
        high_cut = self._config.volatility.high_percentile / 100

        if ratio < low_cut + 0.5:
            return VolatilityProfile.LOW, Decimal("0.35")
        if ratio > high_cut / 100 + 0.8:
            return VolatilityProfile.HIGH, Decimal("0.8")
        return VolatilityProfile.MODERATE, Decimal("0.6")

    def assess_liquidity(
        self,
        candles: list[NormalizedCandle],
        liquidity_state: LiquidityState | None,
    ) -> tuple[LiquidityAvailability, Decimal]:
        """Assess liquidity availability from candles and optional LiquidityState."""
        closed = [c for c in candles if c.is_closed]
        volume_score = Decimal("0.5")
        if self._config.liquidity.use_volume and closed:
            volumes = [c.volume for c in closed[-20:]]
            if volumes:
                avg = sum(volumes) / len(volumes)
                current = volumes[-1]
                if avg > 0:
                    ratio = current / avg
                    if ratio < self._config.liquidity.low_volume_percentile / 100:
                        volume_score = Decimal("0.3")
                    elif ratio > self._config.liquidity.high_volume_percentile / 100:
                        volume_score = Decimal("0.85")
                    else:
                        volume_score = Decimal("0.6")

        engine_score = Decimal("0.5")
        if (
            self._config.liquidity.use_liquidity_engine
            and liquidity_state is not None
        ):
            sweep_factor = min(len(liquidity_state.recent_sweeps), 5) / 5
            zone_factor = min(len(liquidity_state.active_zones), 5) / 5
            engine_score = Decimal(str(0.4 + 0.3 * sweep_factor + 0.3 * zone_factor))

        score = (volume_score + engine_score) / 2
        if score >= Decimal("0.7"):
            return LiquidityAvailability.HIGH, score
        if score >= Decimal("0.45"):
            return LiquidityAvailability.MODERATE, score
        if score >= Decimal("0.25"):
            return LiquidityAvailability.LOW, score
        return LiquidityAvailability.UNDETERMINED, score

    def historical_performance_score(
        self,
        *,
        opening_range_complete: bool,
        initial_balance_complete: bool,
        session_range_pips: Decimal | None,
    ) -> Decimal:
        """Optional historical performance factor (in-memory proxy when DB unavailable)."""
        if not self._config.historical_performance.enabled:
            return Decimal("0.5")

        score = Decimal("0.4")
        if opening_range_complete:
            score += Decimal("0.15")
        if initial_balance_complete:
            score += Decimal("0.15")
        if session_range_pips and session_range_pips > Decimal("30"):
            score += Decimal("0.1")
        return min(Decimal("1"), score)

    def score_analysis(
        self,
        *,
        sessions: list[TradingSessionState],
        kill_zones: list[KillZoneState],
        overlaps: list[SessionOverlap],
        volatility_score: Decimal,
        liquidity_score: Decimal,
        historical_score: Decimal,
        structure: MarketStructure | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
    ) -> tuple[SessionQualityTier, Decimal, Decimal, Decimal]:
        """Compute composite quality tier, strength, and confidence."""
        active_sessions = [s for s in sessions if s.is_active]
        active_kill_zones = [kz for kz in kill_zones if kz.is_active]
        active_overlaps = [o for o in overlaps if o.is_active]

        session_score = (
            max((s.quality_score for s in active_sessions), default=Decimal("0.2"))
        )
        kill_zone_score = (
            max((kz.quality_score for kz in active_kill_zones), default=Decimal("0.2"))
        )
        overlap_score = (
            max((o.quality_score for o in active_overlaps), default=Decimal("0.2"))
        )

        weights = self._config.quality_weights
        strength = (
            session_score * Decimal(str(weights.session_quality))
            + kill_zone_score * Decimal(str(weights.kill_zone_quality))
            + overlap_score * Decimal(str(weights.overlap_quality))
            + volatility_score * Decimal(str(weights.volatility))
            + liquidity_score * Decimal(str(weights.liquidity_availability))
            + historical_score * Decimal(str(weights.historical_performance))
        )

        if structure is not None:
            strength = min(
                Decimal("1"),
                strength + structure.confidence * Decimal("0.05"),
            )
        if premium_discount is not None:
            pd_boost = {
                "high": Decimal("0.08"),
                "medium": Decimal("0.04"),
                "low": Decimal("0"),
            }.get(premium_discount.quality.value, Decimal("0"))
            strength = min(Decimal("1"), strength + pd_boost)

        tier = self._tier_from_score(strength)
        evidence_count = len(active_sessions) + len(active_kill_zones)
        confidence = min(
            Decimal("1"),
            Decimal("0.4")
            + strength * Decimal("0.4")
            + Decimal(str(min(evidence_count, 4))) * Decimal("0.05"),
        )
        return tier, strength, confidence, strength

    def enrich_sessions(
        self,
        sessions: list[TradingSessionState],
        *,
        calendar_clean: bool,
        overlap_session_ids: set[TradingSessionId],
    ) -> list[TradingSessionState]:
        """Re-score sessions with calendar and overlap context."""
        enriched: list[TradingSessionState] = []
        for session in sessions:
            score = self.score_session(
                session,
                calendar_clean=calendar_clean,
                has_overlap=session.session_id in overlap_session_ids,
            )
            enriched.append(
                session.model_copy(
                    update={
                        "quality_score": score,
                        "quality": self._tier_from_score(score),
                    },
                ),
            )
        return enriched

    def enrich_kill_zones(
        self,
        kill_zones: list[KillZoneState],
        *,
        volatility_scores: dict[KillZoneId, Decimal],
        liquidity_scores: dict[KillZoneId, Decimal],
        historical_scores: dict[KillZoneId, Decimal],
    ) -> list[KillZoneState]:
        """Re-score kill zones with factor inputs."""
        enriched: list[KillZoneState] = []
        for kz in kill_zones:
            vol = volatility_scores.get(kz.kill_zone_id, Decimal("0.5"))
            liq = liquidity_scores.get(kz.kill_zone_id, Decimal("0.5"))
            hist = historical_scores.get(kz.kill_zone_id, Decimal("0.5"))
            score = self.score_kill_zone(
                kz,
                volatility_score=vol,
                liquidity_score=liq,
                historical_score=hist,
            )
            enriched.append(
                kz.model_copy(
                    update={
                        "quality_score": score,
                        "quality": self._tier_from_score(score),
                        "liquidity_score": liq,
                        "historical_score": hist,
                    },
                ),
            )
        return enriched

    def upstream_confluence_score(
        self,
        *,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
    ) -> Decimal:
        """Optional upstream confluence boost when context is available."""
        boost = Decimal("0")
        if order_blocks:
            active = sum(
                1 for block in order_blocks if block.status is not OrderBlockStatus.INVALIDATED
            )
            boost += Decimal(str(min(active, 3))) * Decimal("0.01")
        if fair_value_gap_state and fair_value_gap_state.active_gaps:
            boost += Decimal("0.02")
        if breaker_blocks:
            boost += Decimal(str(min(len(breaker_blocks), 2))) * Decimal("0.01")
        if mitigation_blocks:
            boost += Decimal(str(min(len(mitigation_blocks), 2))) * Decimal("0.01")
        return min(Decimal("0.08"), boost)

    def _tier_from_score(self, score: Decimal) -> SessionQualityTier:
        if score >= Decimal(str(self._config.high_quality_threshold)):
            return SessionQualityTier.HIGH
        if score >= Decimal(str(self._config.min_quality_score)):
            return SessionQualityTier.MEDIUM
        return SessionQualityTier.LOW
