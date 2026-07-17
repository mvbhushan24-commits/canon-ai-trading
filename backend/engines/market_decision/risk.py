"""Risk validation and risk-reward checks."""

from decimal import Decimal

from backend.engines.market_decision.config import MarketDecisionConfig, NewsRestrictionHook
from backend.engines.market_decision.schemas import (
    GateResult,
    RiskRuleOutcome,
    RiskSummary,
    TradeDirection,
)


class RiskValidator:
    """Enforce spread, stop size, confidence, session, and news restrictions."""

    def __init__(
        self,
        config: MarketDecisionConfig,
        news_hook: NewsRestrictionHook | None = None,
    ) -> None:
        self._config = config
        self._news_hook = news_hook

    def validate_risk_reward(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: list[Decimal],
    ) -> tuple[Decimal | None, RiskSummary, GateResult]:
        if not take_profit:
            summary = RiskSummary()
            return (
                None,
                summary,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason="At least one take profit target is required",
                ),
            )

        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit[0] - entry_price)
        rr = reward / risk if risk > 0 else Decimal("0")

        min_rr = Decimal(str(self._config.risk.min_risk_reward))
        max_rr = Decimal(str(self._config.risk.max_risk_reward))
        min_met = rr >= min_rr
        max_met = rr <= max_rr

        outcomes = [
            RiskRuleOutcome(
                rule_name="min_risk_reward",
                passed=min_met,
                actual_value=rr.quantize(Decimal("0.01")),
                threshold=min_rr,
                message=f"R:R {rr.quantize(Decimal('0.01'))} vs minimum {min_rr}",
            ),
            RiskRuleOutcome(
                rule_name="max_risk_reward",
                passed=max_met,
                actual_value=rr.quantize(Decimal("0.01")),
                threshold=max_rr,
                message=f"R:R {rr.quantize(Decimal('0.01'))} vs maximum {max_rr}",
            ),
        ]

        summary = RiskSummary(
            risk_reward_ratio=rr.quantize(Decimal("0.01")),
            min_rr_met=min_met,
            max_rr_met=max_met,
            rule_outcomes=outcomes,
        )

        if not min_met:
            return (
                rr,
                summary,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason=f"Risk-reward {rr.quantize(Decimal('0.01'))} below minimum {min_rr}",
                ),
            )
        if not max_met:
            return (
                rr,
                summary,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason=f"Risk-reward {rr.quantize(Decimal('0.01'))} exceeds maximum {max_rr}",
                ),
            )

        return rr, summary, GateResult(passed=True)

    def validate(
        self,
        *,
        direction: TradeDirection,
        confidence: int,
        spread: Decimal | None,
        stop_size_pips: Decimal | None,
        session_allowed: bool,
        symbol: str,
        timestamp_utc,
        existing_summary: RiskSummary | None = None,
    ) -> tuple[RiskSummary, GateResult]:
        summary = existing_summary or RiskSummary()
        outcomes = list(summary.rule_outcomes)

        confidence_ok = confidence >= self._config.risk.min_confidence
        outcomes.append(
            RiskRuleOutcome(
                rule_name="min_confidence",
                passed=confidence_ok,
                actual_value=Decimal(str(confidence)),
                threshold=Decimal(str(self._config.risk.min_confidence)),
                message=f"Confidence {confidence} vs minimum {self._config.risk.min_confidence}",
            ),
        )
        summary.confidence_acceptable = confidence_ok

        spread_pips: Decimal | None = None
        spread_ok = True
        if spread is not None:
            spread_pips = spread / self._config.pip_size_decimal
            spread_ok = spread_pips <= Decimal(str(self._config.risk.max_spread_pips))
            outcomes.append(
                RiskRuleOutcome(
                    rule_name="max_spread",
                    passed=spread_ok,
                    actual_value=spread_pips.quantize(Decimal("0.1")),
                    threshold=Decimal(str(self._config.risk.max_spread_pips)),
                    message=f"Spread {spread_pips.quantize(Decimal('0.1'))} pips",
                ),
            )
        summary.spread_pips = spread_pips.quantize(Decimal("0.1")) if spread_pips is not None else None
        summary.spread_acceptable = spread_ok

        stop_ok = True
        if stop_size_pips is not None:
            stop_ok = stop_size_pips <= Decimal(str(self._config.risk.max_stop_size_pips))
            outcomes.append(
                RiskRuleOutcome(
                    rule_name="max_stop_size",
                    passed=stop_ok,
                    actual_value=stop_size_pips.quantize(Decimal("0.1")),
                    threshold=Decimal(str(self._config.risk.max_stop_size_pips)),
                    message=f"Stop size {stop_size_pips.quantize(Decimal('0.1'))} pips",
                ),
            )
        summary.stop_size_pips = stop_size_pips.quantize(Decimal("0.1")) if stop_size_pips else None
        summary.stop_size_acceptable = stop_ok
        summary.session_allowed = session_allowed
        summary.rule_outcomes = outcomes

        if not confidence_ok:
            return (
                summary,
                GateResult(
                    passed=False,
                    error_code="LOW_CONFIDENCE",
                    blocking_reason=(
                        f"Confidence {confidence} below minimum {self._config.risk.min_confidence}"
                    ),
                ),
            )
        if not spread_ok:
            return (
                summary,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason=f"Spread {spread_pips} pips exceeds maximum {self._config.risk.max_spread_pips}",
                ),
            )
        if not stop_ok:
            return (
                summary,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason=(
                        f"Stop size {stop_size_pips} pips exceeds maximum "
                        f"{self._config.risk.max_stop_size_pips}"
                    ),
                ),
            )
        if not session_allowed:
            return (
                summary,
                GateResult(
                    passed=False,
                    error_code="INVALID_SESSION",
                    blocking_reason="Session restrictions block trading",
                ),
            )

        if self._config.news_restriction.enabled:
            hook = self._news_hook or self._config.default_news_hook
            result = hook(symbol, timestamp_utc)
            summary.news_blocked = result.blocked
            summary.news_block_reason = result.reason or None
            if result.blocked:
                return (
                    summary,
                    GateResult(
                        passed=False,
                        error_code="INVALID_RISK",
                        blocking_reason=result.reason or "News restriction hook blocked trading",
                    ),
                )

        if direction is TradeDirection.NONE:
            return summary, GateResult(passed=False, blocking_reason="No trade direction")

        return summary, GateResult(passed=True)
