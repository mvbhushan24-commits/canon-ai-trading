"""Input and domain validation for the Market Decision Engine."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_decision.config import MarketDecisionConfig, SUPPORTED_SYMBOLS
from backend.engines.market_decision.exceptions import (
    DecisionValidationError,
    InvalidBreakerError,
    InvalidFVGError,
    InvalidLiquidityError,
    InvalidMitigationError,
    InvalidOrderBlockError,
    InvalidPremiumDiscountError,
    InvalidSessionError,
    InvalidStructureError,
)
from backend.engines.market_decision.schemas import (
    DirectionBias,
    EvidenceBundle,
    GateResult,
    TradeDirection,
)
from backend.engines.market_fvg.schemas import FairValueGapDirection, FairValueGapStatus
from backend.engines.market_liquidity.schemas import LiquiditySide, SweepDirection, SweepQuality
from backend.engines.market_mitigation.schemas import MitigationBlockDirection, MitigationBlockStatus
from backend.engines.market_order_block.schemas import OrderBlockDirection, OrderBlockStatus
from backend.engines.market_premium_discount.schemas import PremiumDiscountBias, PremiumDiscountZone
from backend.engines.market_sessions.schemas import SessionQualityTier
from backend.engines.market_structure.schemas import BOSDirection, TrendDirection


_QUALITY_RANK = {"low": 0, "medium": 1, "high": 2}
_SWEEP_QUALITY_RANK = {
    SweepQuality.INDETERMINATE.value: 0,
    SweepQuality.WEAK.value: 1,
    SweepQuality.STRONG.value: 2,
    "low": 1,
    "medium": 2,
    "high": 3,
}


class DecisionInputValidator:
    """Validate decision cycle inputs."""

    def validate_or_raise(
        self,
        symbol: str,
        timestamp_utc: datetime,
        current_price: Decimal | None,
        config: MarketDecisionConfig,
    ) -> None:
        normalized_symbol = symbol.strip().upper().replace("GOLD.I#", "GOLD.i#")
        if normalized_symbol not in SUPPORTED_SYMBOLS and symbol.strip() not in SUPPORTED_SYMBOLS:
            raise DecisionValidationError(
                f"Symbol '{symbol}' not supported; expected XAUUSD/GOLD.i#",
                details={"symbol": symbol},
            )
        if timestamp_utc.tzinfo is None:
            raise DecisionValidationError(
                "timestamp_utc must be timezone-aware UTC",
                details={"timestamp_utc": str(timestamp_utc)},
            )
        if current_price is None or current_price <= 0:
            raise DecisionValidationError(
                "current_price must be present and greater than zero",
                details={"current_price": str(current_price)},
            )
        if not config.enabled:
            raise DecisionValidationError(
                "Market Decision Engine is disabled",
                details={"enabled": config.enabled},
            )


class SessionValidator:
    """Session, kill zone, and time-of-day validation."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def validate(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
    ) -> GateResult:
        gate = self._config.gates.session
        if not gate.enabled:
            return GateResult(passed=True)

        sessions = bundle.sessions
        if sessions is None:
            return GateResult(
                passed=True,
                warnings=["Session evidence unavailable — session gate skipped"],
            )

        if not sessions.time_of_day_filter.is_allowed:
            reason = (
                sessions.time_of_day_filter.blocked_reasons[0]
                if sessions.time_of_day_filter.blocked_reasons
                else "Time-of-day filter blocked trading"
            )
            return GateResult(
                passed=False,
                error_code="INVALID_SESSION",
                blocking_reason=reason,
            )

        restrictions = self._config.risk.session_restrictions
        if restrictions.enabled:
            availability = sessions.market_availability.value
            if availability in restrictions.blocked_availability:
                return GateResult(
                    passed=False,
                    error_code="INVALID_SESSION",
                    blocking_reason=f"Market availability '{availability}' blocks trading",
                )
            phase = sessions.session_phase.value
            if phase in restrictions.blocked_session_phases:
                return GateResult(
                    passed=False,
                    error_code="INVALID_SESSION",
                    blocking_reason=f"Session phase '{phase}' blocks trading",
                )
            if restrictions.blocked_kill_zones:
                active_ids = {kz.kill_zone_id.value for kz in sessions.active_kill_zones}
                if active_ids & set(restrictions.blocked_kill_zones):
                    return GateResult(
                        passed=False,
                        error_code="INVALID_SESSION",
                        blocking_reason="Active kill zone is blocked by configuration",
                    )
            if restrictions.allowed_kill_zones:
                active_ids = {kz.kill_zone_id.value for kz in sessions.active_kill_zones}
                if active_ids and not active_ids & set(restrictions.allowed_kill_zones):
                    return GateResult(
                        passed=False,
                        error_code="INVALID_SESSION",
                        blocking_reason="No allowed kill zone is active",
                    )

        if gate.require_kill_zone and not sessions.active_kill_zones:
            return GateResult(
                passed=False,
                error_code="INVALID_SESSION",
                blocking_reason="Active kill zone required but none active",
            )

        if sessions.active_kill_zones:
            min_rank = _QUALITY_RANK.get(gate.min_kill_zone_quality.lower(), 1)
            best_quality = max(
                _QUALITY_RANK.get(kz.quality.value, 0) for kz in sessions.active_kill_zones
            )
            if best_quality < min_rank:
                return GateResult(
                    passed=False,
                    error_code="INVALID_SESSION",
                    blocking_reason=(
                        f"Kill zone quality below minimum '{gate.min_kill_zone_quality}'"
                    ),
                )

        if direction is TradeDirection.NONE:
            return GateResult(passed=True)

        return GateResult(passed=True)


class StructureValidator:
    """Trend and BOS alignment validation."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def validate(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
    ) -> GateResult:
        gate = self._config.gates.structure
        if not gate.enabled or direction is TradeDirection.NONE:
            return GateResult(passed=True)

        structure = bundle.structure
        if structure is None:
            return GateResult(
                passed=True,
                warnings=["Structure evidence unavailable — structure gate skipped"],
            )

        trend = structure.current_trend
        if trend is TrendDirection.RANGE and not gate.allow_range_trades:
            return GateResult(
                passed=False,
                error_code="INVALID_STRUCTURE",
                blocking_reason="Range market structure does not support directional trades",
            )
        if trend is TrendDirection.UNDETERMINED:
            return GateResult(
                passed=False,
                error_code="INVALID_STRUCTURE",
                blocking_reason="Market structure trend is undetermined",
            )

        if gate.require_trend_alignment:
            if direction is TradeDirection.BUY and trend is not TrendDirection.BULLISH:
                return GateResult(
                    passed=False,
                    error_code="INVALID_STRUCTURE",
                    blocking_reason="Bullish trend alignment required for BUY",
                )
            if direction is TradeDirection.SELL and trend is not TrendDirection.BEARISH:
                return GateResult(
                    passed=False,
                    error_code="INVALID_STRUCTURE",
                    blocking_reason="Bearish trend alignment required for SELL",
                )

        if gate.require_recent_bos and structure.bos_events:
            recent = structure.bos_events[-1]
            if direction is TradeDirection.BUY and recent.direction is not BOSDirection.BULLISH:
                return GateResult(
                    passed=False,
                    error_code="INVALID_STRUCTURE",
                    blocking_reason="Recent BOS does not support BUY direction",
                )
            if direction is TradeDirection.SELL and recent.direction is not BOSDirection.BEARISH:
                return GateResult(
                    passed=False,
                    error_code="INVALID_STRUCTURE",
                    blocking_reason="Recent BOS does not support SELL direction",
                )
        elif gate.require_recent_bos and not structure.bos_events:
            return GateResult(
                passed=False,
                error_code="INVALID_STRUCTURE",
                blocking_reason="Recent BOS required but none detected",
            )

        return GateResult(passed=True)


class LiquidityValidator:
    """Liquidity sweep/grab context validation."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def validate(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
    ) -> GateResult:
        gate = self._config.gates.liquidity
        if not gate.enabled or direction is TradeDirection.NONE:
            return GateResult(passed=True)

        liquidity = bundle.liquidity
        if liquidity is None:
            return GateResult(
                passed=True,
                warnings=["Liquidity evidence unavailable — liquidity gate skipped"],
            )

        if not gate.require_sweep_or_grab:
            return GateResult(passed=True)

        min_rank = _SWEEP_QUALITY_RANK.get(gate.min_sweep_quality.lower(), 0)
        sweeps = liquidity.sweeps[-gate.liquidity_lookback_bars :]
        grabs = liquidity.grabs[-gate.liquidity_lookback_bars :]

        if direction is TradeDirection.BUY:
            bullish_sweeps = [
                sweep
                for sweep in sweeps
                if sweep.direction is SweepDirection.BULLISH
                and _SWEEP_QUALITY_RANK.get(sweep.quality.value, 0) >= min_rank
            ]
            if bullish_sweeps or grabs:
                return GateResult(passed=True)
            return GateResult(
                passed=False,
                error_code="INVALID_LIQUIDITY",
                blocking_reason="No recent bullish sweep/grab supports BUY",
            )

        bearish_sweeps = [
            sweep
            for sweep in sweeps
            if sweep.direction is SweepDirection.BEARISH
            and _SWEEP_QUALITY_RANK.get(sweep.quality.value, 0) >= min_rank
        ]
        if bearish_sweeps or grabs:
            return GateResult(passed=True)
        return GateResult(
            passed=False,
            error_code="INVALID_LIQUIDITY",
            blocking_reason="No recent bearish sweep/grab supports SELL",
        )


class PremiumDiscountValidator:
    """Premium/discount location alignment validation."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def validate(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
    ) -> GateResult:
        gate = self._config.gates.premium_discount
        if not gate.enabled or direction is TradeDirection.NONE:
            return GateResult(passed=True)

        pd = bundle.premium_discount
        if pd is None:
            return GateResult(
                passed=True,
                warnings=["Premium/discount evidence unavailable — gate skipped"],
            )

        location = pd.price_location
        if gate.require_mtf_alignment:
            alignment = pd.mtf_discount_alignment if direction is TradeDirection.BUY else pd.mtf_premium_alignment
            if alignment is None or alignment.alignment_score < Decimal("0.5"):
                return GateResult(
                    passed=False,
                    error_code="INVALID_PREMIUM_DISCOUNT",
                    blocking_reason="MTF premium/discount alignment required but insufficient",
                )

        if gate.require_ote_for_entry and pd.ote_zone is None:
            return GateResult(
                passed=False,
                error_code="INVALID_PREMIUM_DISCOUNT",
                blocking_reason="OTE zone required for entry but not available",
            )

        if direction is TradeDirection.BUY:
            if location is PremiumDiscountZone.DISCOUNT:
                return GateResult(passed=True)
            if location is PremiumDiscountZone.EQUILIBRIUM and gate.allow_equilibrium:
                return GateResult(passed=True)
            return GateResult(
                passed=False,
                error_code="INVALID_PREMIUM_DISCOUNT",
                blocking_reason="BUY requires discount or allowed equilibrium location",
            )

        if location is PremiumDiscountZone.PREMIUM:
            return GateResult(passed=True)
        if location is PremiumDiscountZone.EQUILIBRIUM and gate.allow_equilibrium:
            return GateResult(passed=True)
        return GateResult(
            passed=False,
            error_code="INVALID_PREMIUM_DISCOUNT",
            blocking_reason="SELL requires premium or allowed equilibrium location",
        )


class ZoneValidator:
    """Institutional zone confluence validation."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def validate(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
        zone_confluence_count: int,
    ) -> GateResult:
        gate = self._config.gates.zones
        if not gate.enabled or direction is TradeDirection.NONE:
            return GateResult(passed=True)

        if gate.gate_mode == "grouped":
            if zone_confluence_count < gate.min_zone_confluence:
                return GateResult(
                    passed=False,
                    error_code="INVALID_ORDER_BLOCK",
                    blocking_reason=(
                        f"Zone confluence {zone_confluence_count} below minimum "
                        f"{gate.min_zone_confluence}"
                    ),
                )
            return GateResult(passed=True)

        requirements = gate.individual_requirements
        checks: list[tuple[bool, str, str]] = [
            (
                requirements.order_block,
                "INVALID_ORDER_BLOCK",
                self._has_order_block(bundle, direction),
            ),
            (
                requirements.fair_value_gap,
                "INVALID_FVG",
                self._has_fvg(bundle, direction),
            ),
            (
                requirements.market_breaker,
                "INVALID_BREAKER",
                self._has_breaker(bundle, direction),
            ),
            (
                requirements.market_mitigation,
                "INVALID_MITIGATION",
                self._has_mitigation(bundle, direction),
            ),
        ]
        for required, code, present in checks:
            if required and not present:
                return GateResult(
                    passed=False,
                    error_code=code,
                    blocking_reason=f"Required zone from {code} not aligned with direction",
                )
        return GateResult(passed=True)

    def count_aligned_zones(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
        current_price: Decimal,
    ) -> int:
        if direction is TradeDirection.NONE:
            return 0
        count = 0
        count += int(self._has_order_block(bundle, direction))
        count += int(self._has_fvg(bundle, direction))
        count += int(self._has_breaker(bundle, direction))
        count += int(self._has_mitigation(bundle, direction))
        return count

    def _has_order_block(self, bundle: EvidenceBundle, direction: TradeDirection) -> bool:
        ob = bundle.order_blocks
        if ob is None:
            return False
        target = OrderBlockDirection.BULLISH if direction is TradeDirection.BUY else OrderBlockDirection.BEARISH
        return any(
            block.direction is target and block.status is OrderBlockStatus.FRESH
            for block in ob.fresh_blocks
        )

    def _has_fvg(self, bundle: EvidenceBundle, direction: TradeDirection) -> bool:
        fvg = bundle.fair_value_gaps
        if fvg is None:
            return False
        target = FairValueGapDirection.BULLISH if direction is TradeDirection.BUY else FairValueGapDirection.BEARISH
        return any(
            gap.direction is target and gap.status in {FairValueGapStatus.OPEN, FairValueGapStatus.PARTIAL}
            for gap in fvg.open_gaps
        )

    def _has_breaker(self, bundle: EvidenceBundle, direction: TradeDirection) -> bool:
        breaker = bundle.breaker_blocks
        if breaker is None:
            return False
        target = "bullish" if direction is TradeDirection.BUY else "bearish"
        return any(block.direction.value == target for block in breaker.confirmed_breakers)

    def _has_mitigation(self, bundle: EvidenceBundle, direction: TradeDirection) -> bool:
        mitigation = bundle.mitigation_blocks
        if mitigation is None:
            return False
        target = MitigationBlockDirection.BULLISH if direction is TradeDirection.BUY else MitigationBlockDirection.BEARISH
        return any(
            block.direction is target
            and block.status in {MitigationBlockStatus.FRESH, MitigationBlockStatus.CONFIRMED}
            for block in mitigation.fresh_blocks + mitigation.confirmed_blocks
        )


def map_exception_to_gate(error: Exception) -> GateResult:
    """Map domain exceptions to gate results."""
    code_map = {
        InvalidSessionError: "INVALID_SESSION",
        InvalidStructureError: "INVALID_STRUCTURE",
        InvalidLiquidityError: "INVALID_LIQUIDITY",
        InvalidOrderBlockError: "INVALID_ORDER_BLOCK",
        InvalidFVGError: "INVALID_FVG",
        InvalidBreakerError: "INVALID_BREAKER",
        InvalidMitigationError: "INVALID_MITIGATION",
        InvalidPremiumDiscountError: "INVALID_PREMIUM_DISCOUNT",
    }
    for exc_type, code in code_map.items():
        if isinstance(error, exc_type):
            return GateResult(passed=False, error_code=code, blocking_reason=str(error))
    return GateResult(passed=False, error_code="MDE_ERROR", blocking_reason=str(error))


def bias_supports_direction(bias: DirectionBias, direction: TradeDirection) -> bool:
    """Check whether normalized bias supports trade direction."""
    if direction is TradeDirection.BUY:
        return bias is DirectionBias.BULLISH
    if direction is TradeDirection.SELL:
        return bias is DirectionBias.BEARISH
    return False


def premium_discount_bias_supports(
    bias: PremiumDiscountBias,
    direction: TradeDirection,
) -> bool:
    """Check premium/discount bias alignment."""
    if direction is TradeDirection.BUY:
        return bias in {PremiumDiscountBias.BULLISH, PremiumDiscountBias.NEUTRAL}
    if direction is TradeDirection.SELL:
        return bias in {PremiumDiscountBias.BEARISH, PremiumDiscountBias.NEUTRAL}
    return False


def liquidity_bias_supports(bias: LiquiditySide, direction: TradeDirection) -> bool:
    """Check liquidity side bias alignment."""
    if direction is TradeDirection.BUY:
        return bias in {LiquiditySide.SELL_SIDE, LiquiditySide.BALANCED}
    if direction is TradeDirection.SELL:
        return bias in {LiquiditySide.BUY_SIDE, LiquiditySide.BALANCED}
    return False


def session_quality_rank(tier: SessionQualityTier) -> int:
    """Map session quality tier to numeric rank."""
    return _QUALITY_RANK.get(tier.value, 0)
