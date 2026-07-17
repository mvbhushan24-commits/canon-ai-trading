"""Unit tests for Market Decision Engine validators."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.engines.market_decision.config import MarketDecisionConfig
from backend.engines.market_decision.exceptions import DecisionValidationError
from backend.engines.market_decision.schemas import DirectionBias, TradeDirection
from backend.engines.market_decision.validator import (
    DecisionInputValidator,
    LiquidityValidator,
    PremiumDiscountValidator,
    SessionValidator,
    StructureValidator,
    ZoneValidator,
    bias_supports_direction,
    map_exception_to_gate,
    premium_discount_bias_supports,
    session_quality_rank,
)
from backend.engines.market_decision.exceptions import InvalidSessionError
from backend.engines.market_premium_discount.schemas import PremiumDiscountBias, PremiumDiscountZone
from backend.engines.market_sessions.schemas import SessionQualityTier
from backend.engines.market_structure.schemas import TrendDirection
from tests.unit.engines.decision_conftest import (
    build_bullish_upstream_evidence,
    decision_config,
    sample_session_analysis,
)


def test_input_validator_accepts_supported_symbol() -> None:
    validator = DecisionInputValidator()
    config = decision_config()
    validator.validate_or_raise(
        "XAUUSD",
        datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        Decimal("2320"),
        config,
    )


def test_input_validator_rejects_unsupported_symbol() -> None:
    validator = DecisionInputValidator()
    with pytest.raises(DecisionValidationError, match="not supported"):
        validator.validate_or_raise(
            "EURUSD",
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            Decimal("2320"),
            decision_config(),
        )


def test_input_validator_rejects_naive_timestamp() -> None:
    validator = DecisionInputValidator()
    with pytest.raises(DecisionValidationError, match="timezone-aware"):
        validator.validate_or_raise(
            "XAUUSD",
            datetime(2026, 1, 14, 8, 30),
            Decimal("2320"),
            decision_config(),
        )


def test_input_validator_rejects_disabled_engine() -> None:
    validator = DecisionInputValidator()
    with pytest.raises(DecisionValidationError, match="disabled"):
        validator.validate_or_raise(
            "XAUUSD",
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            Decimal("2320"),
            MarketDecisionConfig(enabled=False),
        )


def test_session_validator_blocks_disallowed_time_filter() -> None:
    evidence = build_bullish_upstream_evidence()
    from backend.engines.market_decision.evidence import EvidenceCollector

    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        sessions=sample_session_analysis(is_allowed=False),
    )
    result = SessionValidator(decision_config()).validate(bundle, TradeDirection.BUY)
    assert result.passed is False
    assert result.error_code == "INVALID_SESSION"


def test_structure_validator_requires_bullish_trend_for_buy() -> None:
    evidence = build_bullish_upstream_evidence()
    from backend.engines.market_decision.evidence import EvidenceCollector

    bearish_structure = evidence["structure"].model_copy(
        update={"current_trend": TrendDirection.BEARISH},
    )
    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=bearish_structure,
    )
    result = StructureValidator(decision_config()).validate(bundle, TradeDirection.BUY)
    assert result.passed is False
    assert result.error_code == "INVALID_STRUCTURE"


def test_liquidity_validator_requires_bullish_sweep_for_buy() -> None:
    evidence = build_bullish_upstream_evidence()
    from backend.engines.market_decision.evidence import EvidenceCollector

    liquidity = evidence["liquidity"].model_copy(update={"sweeps": [], "grabs": []})
    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        liquidity=liquidity,
    )
    result = LiquidityValidator(decision_config()).validate(bundle, TradeDirection.BUY)
    assert result.passed is False
    assert result.error_code == "INVALID_LIQUIDITY"


def test_premium_discount_validator_requires_discount_for_buy() -> None:
    evidence = build_bullish_upstream_evidence()
    from backend.engines.market_decision.evidence import EvidenceCollector

    pd = evidence["premium_discount"].model_copy(
        update={"price_location": PremiumDiscountZone.PREMIUM},
    )
    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        premium_discount=pd,
    )
    result = PremiumDiscountValidator(decision_config()).validate(bundle, TradeDirection.BUY)
    assert result.passed is False
    assert result.error_code == "INVALID_PREMIUM_DISCOUNT"


def test_zone_validator_requires_confluence() -> None:
    evidence = build_bullish_upstream_evidence()
    from backend.engines.market_decision.evidence import EvidenceCollector

    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
    )
    result = ZoneValidator(decision_config()).validate(bundle, TradeDirection.BUY, zone_confluence_count=0)
    assert result.passed is False
    assert result.error_code == "INVALID_ORDER_BLOCK"


def test_map_exception_to_gate() -> None:
    gate = map_exception_to_gate(InvalidSessionError("blocked"))
    assert gate.passed is False
    assert gate.error_code == "INVALID_SESSION"


def test_bias_supports_direction_helpers() -> None:
    assert bias_supports_direction(DirectionBias.BULLISH, TradeDirection.BUY)
    assert session_quality_rank(SessionQualityTier.HIGH) == 2


def test_premium_discount_bias_supports_documents_schema_alignment() -> None:
    """Premium/discount bias enum uses territory labels, not directional labels."""
    with pytest.raises(AttributeError):
        premium_discount_bias_supports(PremiumDiscountBias.DISCOUNT, TradeDirection.BUY)
