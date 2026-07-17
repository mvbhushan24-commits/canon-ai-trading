"""Unit tests for risk validation."""

from decimal import Decimal

from backend.engines.market_decision.risk import RiskValidator
from backend.engines.market_decision.schemas import TradeDirection
from tests.unit.engines.decision_conftest import blocking_news_hook, decision_config, relaxed_decision_config


def test_validate_risk_reward_passes_valid_ratio() -> None:
    entry = Decimal("2320")
    stop = Decimal("2310")
    targets = [Decimal("2340")]

    rr, summary, gate = RiskValidator(decision_config()).validate_risk_reward(entry, stop, targets)

    assert gate.passed is True
    assert rr == Decimal("2")
    assert summary.min_rr_met is True


def test_validate_risk_reward_rejects_low_ratio() -> None:
    entry = Decimal("2320")
    stop = Decimal("2310")
    targets = [Decimal("2325")]

    rr, _summary, gate = RiskValidator(decision_config()).validate_risk_reward(entry, stop, targets)

    assert gate.passed is False
    assert gate.error_code == "INVALID_RISK"
    assert rr is not None


def test_validate_rejects_excessive_spread() -> None:
    validator = RiskValidator(relaxed_decision_config())
    summary, gate = validator.validate(
        direction=TradeDirection.BUY,
        confidence=80,
        spread=Decimal("1.0"),
        stop_size_pips=Decimal("20"),
        session_allowed=True,
        symbol="XAUUSD",
        timestamp_utc=None,
    )

    assert gate.passed is False
    assert gate.error_code == "INVALID_RISK"
    assert summary.spread_acceptable is False


def test_validate_blocks_news_restriction_hook() -> None:
    config = relaxed_decision_config(news_restriction={"enabled": True})
    validator = RiskValidator(config, news_hook=blocking_news_hook)
    summary, gate = validator.validate(
        direction=TradeDirection.BUY,
        confidence=80,
        spread=Decimal("0.2"),
        stop_size_pips=Decimal("20"),
        session_allowed=True,
        symbol="XAUUSD",
        timestamp_utc=None,
    )

    assert gate.passed is False
    assert summary.news_blocked is True
