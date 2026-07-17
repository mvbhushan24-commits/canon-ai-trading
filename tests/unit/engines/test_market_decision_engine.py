"""Unit tests for MarketDecisionEngine orchestration."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

pytest_plugins = ["tests.unit.engines.decision_conftest"]

from backend.engines.market_decision import MarketDecisionEngine, MarketDecisionConfig
from backend.engines.market_decision.config import EvidenceConfig
from backend.engines.market_decision.evidence import EvidenceCollector
from backend.engines.market_decision.exceptions import DecisionValidationError
from backend.engines.market_decision.schemas import DecisionState, TradeDirection
from backend.engines.market_decision.validator import DecisionInputValidator
from tests.unit.engines.decision_conftest import (
    build_bearish_upstream_evidence,
    build_bullish_upstream_evidence,
    decision_config,
    relaxed_decision_config,
)


def test_decide_returns_no_data_for_invalid_price() -> None:
    engine = MarketDecisionEngine(config=decision_config())
    decision = engine.decide(
        "XAUUSD",
        datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        Decimal("0"),
    )
    assert decision.state is DecisionState.NO_DATA


def test_decide_returns_invalid_for_bad_symbol() -> None:
    engine = MarketDecisionEngine(config=decision_config())
    decision = engine.decide(
        "EURUSD",
        datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        Decimal("2320"),
    )
    assert decision.state is DecisionState.INVALID
    assert "DECISION_VALIDATION_FAILED" in decision.error_codes or "VALIDATION" in str(decision.error_codes)


def test_decide_returns_no_trade_for_insufficient_evidence() -> None:
    engine = MarketDecisionEngine(config=decision_config())
    decision = engine.decide(
        "XAUUSD",
        datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        Decimal("2320"),
        structure=build_bullish_upstream_evidence()["structure"],
    )
    assert decision.state is DecisionState.NO_TRADE
    assert "INSUFFICIENT_EVIDENCE" in decision.error_codes


def test_decide_generates_buy_signal() -> None:
    evidence = build_bullish_upstream_evidence()
    engine = MarketDecisionEngine(config=relaxed_decision_config())
    decision = engine.decide(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        spread=evidence["spread"],
        structure=evidence["structure"],
        liquidity=evidence["liquidity"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
        breaker_blocks=evidence["breaker_blocks"],
        mitigation_blocks=evidence["mitigation_blocks"],
        premium_discount=evidence["premium_discount"],
        sessions=evidence["sessions"],
    )

    assert decision.state is DecisionState.BUY
    assert decision.direction is TradeDirection.BUY
    assert decision.stop_loss is not None
    assert decision.take_profit
    assert decision.risk_reward_ratio is not None
    assert decision.valid_until_utc is not None


def test_decide_generates_no_trade_on_structure_mismatch() -> None:
    evidence = build_bullish_upstream_evidence()
    from backend.engines.market_liquidity.schemas import LiquiditySide, LiquiditySweep, SweepDirection, SweepQuality
    from backend.engines.market_premium_discount.schemas import PremiumDiscountBias, PremiumDiscountZone
    from backend.engines.market_structure.schemas import TrendDirection

    bearish_structure = evidence["structure"].model_copy(
        update={"current_trend": TrendDirection.BEARISH, "confidence": Decimal("0.95")},
    )
    bearish_sweep = LiquiditySweep(
        direction=SweepDirection.BEARISH,
        swept_level=Decimal("2340"),
        sweep_price=Decimal("2342"),
        reclaim_price=Decimal("2335"),
        timestamp_utc=evidence["timestamp_utc"],
        bar_index=20,
        timeframe="H1",
        quality=SweepQuality.STRONG,
    )
    bearish_liquidity = evidence["liquidity"].model_copy(
        update={
            "sweeps": [bearish_sweep],
            "bias": LiquiditySide.BUY_SIDE,
            "confidence": Decimal("0.95"),
        },
    )
    bearish_pd = evidence["premium_discount"].model_copy(
        update={
            "price_location": PremiumDiscountZone.PREMIUM,
            "bias": PremiumDiscountBias.PREMIUM,
            "confidence": Decimal("0.95"),
        },
    )
    engine = MarketDecisionEngine(config=relaxed_decision_config())
    decision = engine.decide(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        spread=evidence["spread"],
        structure=bearish_structure,
        liquidity=bearish_liquidity,
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
        breaker_blocks=evidence["breaker_blocks"],
        mitigation_blocks=evidence["mitigation_blocks"],
        premium_discount=bearish_pd,
        sessions=evidence["sessions"],
    )

    assert decision.state is DecisionState.NO_TRADE
    assert decision.error_codes


def test_dependency_injection_uses_provided_components() -> None:
    validator = MagicMock(spec=DecisionInputValidator)
    validator.validate_or_raise.side_effect = DecisionValidationError("injected")
    engine = MarketDecisionEngine(
        config=decision_config(),
        validator=validator,
    )
    decision = engine.decide(
        "XAUUSD",
        datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        Decimal("2320"),
    )
    validator.validate_or_raise.assert_called_once()
    assert decision.state is DecisionState.INVALID


def test_graceful_degradation_with_partial_evidence() -> None:
    evidence = build_bullish_upstream_evidence()
    config = relaxed_decision_config(
        evidence=EvidenceConfig(min_required_engines=3),
    )
    engine = MarketDecisionEngine(config=config)
    decision = engine.decide(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=evidence["structure"],
        liquidity=evidence["liquidity"],
        order_blocks=evidence["order_blocks"],
    )

    assert any("Partial evidence" in warning for warning in decision.warnings) or decision.state in {
        DecisionState.BUY,
        DecisionState.NO_TRADE,
    }


def test_evaluate_cached_requires_price() -> None:
    engine = MarketDecisionEngine(config=decision_config())
    decision = engine.evaluate_cached("XAUUSD")
    assert decision.state is DecisionState.NO_DATA


def test_event_handlers_update_cache() -> None:
    evidence = build_bullish_upstream_evidence()
    engine = MarketDecisionEngine(config=decision_config())
    engine.handle_structure_completed(evidence["structure"].model_dump(mode="json"))
    engine.handle_tick_received(
        {
            "payload": {
                "symbol": "XAUUSD",
                "bid": "2320.0",
                "ask": "2320.2",
                "timestamp_utc": evidence["timestamp_utc"].isoformat(),
            },
        },
    )

    assert engine.evidence_cache.structure is not None
    assert engine.evidence_cache.current_price == Decimal("2320.1")


def test_expire_decisions_publishes_expired_event(decision_publisher) -> None:
    evidence = build_bullish_upstream_evidence()
    events: list[str] = []
    decision_publisher.subscribe("*", lambda event: events.append(event.event_type))
    engine = MarketDecisionEngine(config=relaxed_decision_config(), publisher=decision_publisher)
    decision = engine.decide(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        spread=evidence["spread"],
        structure=evidence["structure"],
        liquidity=evidence["liquidity"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
        breaker_blocks=evidence["breaker_blocks"],
        mitigation_blocks=evidence["mitigation_blocks"],
        premium_discount=evidence["premium_discount"],
        sessions=evidence["sessions"],
    )
    assert decision.state is DecisionState.BUY

    expired = engine.expire_decisions(decision.valid_until_utc + timedelta(minutes=1))
    assert len(expired) == 1
    assert "DecisionExpired" in events


def test_publish_wait_event_when_configured(decision_publisher) -> None:
    from backend.engines.market_decision.schemas import TradeDecision, DecisionMetadata

    events: list[str] = []
    decision_publisher.subscribe("*", lambda event: events.append(event.event_type))
    config = relaxed_decision_config(publish_wait_events=True)
    engine = MarketDecisionEngine(config=config, publisher=decision_publisher)
    wait_decision = TradeDecision(
        decision_id="wait-1",
        symbol="XAUUSD",
        timestamp_utc=datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        state=DecisionState.WAIT,
        direction=TradeDirection.NONE,
        metadata=DecisionMetadata(),
    )
    engine.publish_events(wait_decision)
    assert "decision.wait.published" in events


def test_handle_config_updated_rebuilds_components() -> None:
    engine = MarketDecisionEngine(config=decision_config())
    new_config = relaxed_decision_config(decision_validity_minutes=90)
    engine.handle_config_updated(new_config)
    assert engine.config.decision_validity_minutes == 90
