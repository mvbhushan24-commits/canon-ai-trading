"""Input validation and decision-derived gates for the Market Signal Engine."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_decision import (
    DecisionState,
    EntryType,
    TradeDecision,
    TradeDirection,
)
from backend.engines.market_signal.config import MarketSignalConfig, SUPPORTED_SYMBOLS
from backend.engines.market_signal.exceptions import (
    InvalidDecisionError,
    InvalidRiskError,
    LowConfidenceError,
    SignalExpiredError,
    SignalValidationError,
)
from backend.engines.market_signal.schemas import NormalizedLevels, ValidationGateResult


class SignalInputValidator:
    """Validate signal pipeline inputs and configuration."""

    def validate_or_raise(
        self,
        decision: TradeDecision,
        config: MarketSignalConfig,
    ) -> None:
        if not config.enabled:
            raise SignalValidationError(
                "Market Signal Engine is disabled",
                details={"enabled": config.enabled},
            )
        normalized_symbol = decision.symbol.strip().upper().replace("GOLD.I#", "GOLD.i#")
        if (
            normalized_symbol not in SUPPORTED_SYMBOLS
            and decision.symbol.strip() not in SUPPORTED_SYMBOLS
        ):
            raise SignalValidationError(
                f"Symbol '{decision.symbol}' not supported; expected XAUUSD/GOLD.i#",
                details={"symbol": decision.symbol},
            )
        if decision.timestamp_utc.tzinfo is None:
            raise SignalValidationError(
                "timestamp_utc must be timezone-aware UTC",
                details={"timestamp_utc": str(decision.timestamp_utc)},
            )


class DecisionValidator:
    """Validate decision state and required fields for signal creation."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def validate(self, decision: TradeDecision) -> ValidationGateResult:
        state = decision.state

        if state in {DecisionState.NO_TRADE, DecisionState.WAIT, DecisionState.NO_DATA}:
            return ValidationGateResult(passed=False, error_code=None)

        if state is DecisionState.INVALID:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason="Decision state is INVALID",
            )

        if state not in {DecisionState.BUY, DecisionState.SELL}:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason=f"Decision state '{state.value}' is not signal-eligible",
            )

        expected_direction = (
            TradeDirection.BUY if state is DecisionState.BUY else TradeDirection.SELL
        )
        if decision.direction is not expected_direction:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason=(
                    f"Direction '{decision.direction.value}' does not match state '{state.value}'"
                ),
            )

        if decision.entry is None or (
            decision.entry.entry_type is EntryType.POINT and decision.entry.price is None
        ):
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason="Entry specification missing or invalid",
            )

        if decision.entry.entry_type in {EntryType.ZONE, EntryType.OTE}:
            if decision.entry.zone_low is None or decision.entry.zone_high is None:
                return ValidationGateResult(
                    passed=False,
                    error_code="INVALID_DECISION",
                    blocking_reason="Zone/OTE entry requires zone_low and zone_high",
                )

        if decision.stop_loss is None:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason="stop_loss is required",
            )

        if self._config.take_profit.require_minimum_one and not decision.take_profit:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason="At least one take profit target is required",
            )

        if decision.risk_reward_ratio is None:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason="risk_reward_ratio is required",
            )

        if not 0 <= decision.confidence <= 100:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason="confidence must be between 0 and 100",
            )

        if (
            self._config.validation.require_evidence_summary
            and not decision.evidence_summary
        ):
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason="evidence_summary is required and must be non-empty",
            )

        if self._config.validation.require_risk_summary and decision.risk_summary is None:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_DECISION",
                blocking_reason="risk_summary is required",
            )

        return ValidationGateResult(passed=True)

    def validate_or_raise(self, decision: TradeDecision) -> None:
        result = self.validate(decision)
        if result.passed:
            return
        if result.error_code is None:
            return
        raise InvalidDecisionError(
            result.blocking_reason or "Decision validation failed",
            details={"decision_id": decision.decision_id, "state": decision.state.value},
        )


class ExpiryValidator:
    """Validate decision freshness and validity window."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def validate(
        self,
        decision: TradeDecision,
        *,
        now_utc: datetime,
    ) -> ValidationGateResult:
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=UTC)

        if decision.valid_until_utc is not None:
            valid_until = decision.valid_until_utc
            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=UTC)
            if now_utc > valid_until:
                return ValidationGateResult(
                    passed=False,
                    error_code="SIGNAL_EXPIRED",
                    blocking_reason="Decision valid_until_utc has elapsed",
                )

        decision_ts = decision.timestamp_utc
        if decision_ts.tzinfo is None:
            decision_ts = decision_ts.replace(tzinfo=UTC)
        age_seconds = (now_utc - decision_ts).total_seconds()
        if age_seconds > self._config.max_decision_age_seconds:
            return ValidationGateResult(
                passed=False,
                error_code="SIGNAL_EXPIRED",
                blocking_reason=(
                    f"Decision age {int(age_seconds)}s exceeds maximum "
                    f"{self._config.max_decision_age_seconds}s"
                ),
            )

        return ValidationGateResult(passed=True)

    def validate_or_raise(self, decision: TradeDecision, *, now_utc: datetime) -> None:
        result = self.validate(decision, now_utc=now_utc)
        if not result.passed:
            raise SignalExpiredError(
                result.blocking_reason or "Decision expired",
                details={"decision_id": decision.decision_id},
            )


class ConfidenceValidator:
    """Enforce confidence and decision quality thresholds."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def validate(self, decision: TradeDecision) -> ValidationGateResult:
        minimum = self._config.validation.min_confidence
        if decision.confidence < minimum:
            return ValidationGateResult(
                passed=False,
                error_code="LOW_CONFIDENCE",
                blocking_reason=(
                    f"Decision confidence {decision.confidence} below signal minimum {minimum}"
                ),
            )

        min_quality = self._config.validation.min_decision_quality
        if min_quality > 0 and decision.quality_score < min_quality:
            return ValidationGateResult(
                passed=False,
                error_code="LOW_CONFIDENCE",
                blocking_reason=(
                    f"Decision quality {decision.quality_score} below minimum {min_quality}"
                ),
            )

        return ValidationGateResult(passed=True)

    def validate_or_raise(self, decision: TradeDecision) -> None:
        result = self.validate(decision)
        if not result.passed:
            raise LowConfidenceError(
                result.blocking_reason or "Confidence below threshold",
                details={"decision_id": decision.decision_id},
            )


class SessionValidator:
    """Re-validate session context from decision fields only."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def validate(self, decision: TradeDecision) -> ValidationGateResult:
        if not self._config.session.enabled:
            return ValidationGateResult(passed=True)

        risk = decision.risk_summary
        if (
            self._config.session.require_session_allowed
            and not risk.session_allowed
        ):
            return ValidationGateResult(
                passed=False,
                error_code="SIGNAL_VALIDATION_FAILED",
                blocking_reason="risk_summary.session_allowed is false",
            )

        blocked = [item.lower() for item in self._config.session.blocked_sessions]
        if blocked:
            session_text = self._extract_session_context(decision).lower()
            for session_name in blocked:
                if session_name in session_text:
                    return ValidationGateResult(
                        passed=False,
                        error_code="SIGNAL_VALIDATION_FAILED",
                        blocking_reason=f"Session '{session_name}' is blocked for signals",
                    )

        return ValidationGateResult(passed=True)

    def validate_or_raise(self, decision: TradeDecision) -> None:
        result = self.validate(decision)
        if not result.passed:
            raise SignalValidationError(
                result.blocking_reason or "Session validation failed",
                details={"decision_id": decision.decision_id},
            )

    def _extract_session_context(self, decision: TradeDecision) -> str:
        parts: list[str] = list(decision.warnings) + list(decision.reasons)
        for item in decision.evidence_summary:
            if item.engine_id == "market_sessions":
                parts.extend(item.key_evidence)
        return " ".join(parts)


class RiskValidator:
    """Re-validate risk summary from decision fields only."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def validate(self, decision: TradeDecision) -> ValidationGateResult:
        risk = decision.risk_summary
        cfg = self._config.risk

        if cfg.require_min_rr_met and not risk.min_rr_met:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_RISK",
                blocking_reason="risk_summary.min_rr_met is false",
            )

        if cfg.require_max_rr_met and not risk.max_rr_met:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_RISK",
                blocking_reason="risk_summary.max_rr_met is false",
            )

        if cfg.require_spread_acceptable and not risk.spread_acceptable:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_RISK",
                blocking_reason="risk_summary.spread_acceptable is false",
            )

        if cfg.require_stop_size_acceptable and not risk.stop_size_acceptable:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_RISK",
                blocking_reason="risk_summary.stop_size_acceptable is false",
            )

        if cfg.require_confidence_acceptable and not risk.confidence_acceptable:
            return ValidationGateResult(
                passed=False,
                error_code="INVALID_RISK",
                blocking_reason="risk_summary.confidence_acceptable is false",
            )

        if decision.risk_reward_ratio is not None:
            rr = float(decision.risk_reward_ratio)
            if rr < cfg.min_risk_reward:
                return ValidationGateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason=(
                        f"risk_reward_ratio {rr} below minimum {cfg.min_risk_reward}"
                    ),
                )
            if rr > cfg.max_risk_reward:
                return ValidationGateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason=(
                        f"risk_reward_ratio {rr} above maximum {cfg.max_risk_reward}"
                    ),
                )

        return ValidationGateResult(passed=True)

    def validate_or_raise(self, decision: TradeDecision) -> None:
        result = self.validate(decision)
        if not result.passed:
            raise InvalidRiskError(
                result.blocking_reason or "Risk validation failed",
                details={"decision_id": decision.decision_id},
            )


class EntryNormalizer:
    """Resolve EntrySpec to a single entry price."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def normalize(self, decision: TradeDecision) -> Decimal:
        entry = decision.entry
        entry_type = entry.entry_type

        if entry_type is EntryType.POINT:
            if entry.price is None:
                msg = "Point entry requires price"
                raise InvalidDecisionError(msg)
            return entry.price

        zone_low = entry.zone_low
        zone_high = entry.zone_high
        if zone_low is None or zone_high is None:
            msg = "Zone/OTE entry requires zone bounds"
            raise InvalidDecisionError(msg)

        resolution = self._config.entry.zone_resolution
        if resolution == "midpoint":
            return (zone_low + zone_high) / Decimal("2")

        if decision.state is DecisionState.BUY:
            if resolution == "aggressive":
                return zone_low if self._config.entry.buy_zone_edge == "zone_low" else zone_high
            return zone_high

        if resolution == "aggressive":
            return zone_high if self._config.entry.sell_zone_edge == "zone_high" else zone_low
        return zone_low


class TakeProfitMapper:
    """Map decision take profit list to TP1/TP2/TP3."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def map(self, decision: TradeDecision) -> NormalizedLevels:
        entry_normalizer = EntryNormalizer(self._config)
        entry_price = entry_normalizer.normalize(decision)
        targets = decision.take_profit[: self._config.take_profit.max_targets]

        tp1 = targets[0]
        tp2 = targets[1] if len(targets) > 1 else None
        tp3 = targets[2] if len(targets) > 2 else None

        return NormalizedLevels(
            entry_price=entry_price,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            entry_type=decision.entry.entry_type.value,
            tp_count=len(targets),
        )


def resolve_expiry_time(
    decision: TradeDecision,
    config: MarketSignalConfig,
    *,
    now_utc: datetime,
) -> datetime:
    """Resolve signal expiry from decision or configuration."""
    if decision.valid_until_utc is not None:
        expiry = decision.valid_until_utc
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return expiry
    return now_utc + timedelta(minutes=config.signal_validity_minutes)
