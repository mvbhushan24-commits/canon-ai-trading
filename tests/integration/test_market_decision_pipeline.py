"""Integration tests for full upstream pipeline → Market Decision Engine."""

from decimal import Decimal

from backend.engines.market_decision import MarketDecisionEngine
from backend.engines.market_premium_discount import PremiumDiscountEngine
from backend.engines.market_sessions import MarketSessionsEngine
from tests.integration.test_market_premium_discount_pipeline import _premium_config, _run_upstream_chain
from tests.unit.engines.conftest import build_bullish_structure_candles
from tests.unit.engines.decision_conftest import (
    build_bullish_upstream_evidence,
    relaxed_decision_config,
    sample_session_analysis,
)
from tests.unit.engines.market_sessions_conftest import london_open_timestamp


def test_pipeline_full_chain_to_decision() -> None:
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

    assert decision.symbol == "XAUUSD"
    assert decision.metadata.engines_available == 8
    assert decision.state.value in {"BUY", "NO_TRADE"}


def test_pipeline_preserves_symbol_and_metadata() -> None:
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

    assert decision.symbol == evidence["structure"].symbol
    assert decision.metadata.pipeline_version == "0.1.0"
    assert decision.metadata.duration_ms >= 0


def test_pipeline_event_driven_cache_evaluation() -> None:
    evidence = build_bullish_upstream_evidence()
    engine = MarketDecisionEngine(config=relaxed_decision_config())
    engine.handle_structure_completed(evidence["structure"].model_dump(mode="json"))
    engine.handle_liquidity_completed(evidence["liquidity"].model_dump(mode="json"))
    engine.handle_order_block_completed(evidence["order_blocks"].model_dump(mode="json"))
    engine.handle_fvg_completed(evidence["fair_value_gaps"].model_dump(mode="json"))
    engine.handle_breaker_completed(evidence["breaker_blocks"].model_dump(mode="json"))
    engine.handle_mitigation_completed(evidence["mitigation_blocks"].model_dump(mode="json"))
    engine.handle_premium_discount_completed(evidence["premium_discount"].model_dump(mode="json"))
    engine.handle_session_completed(evidence["sessions"].model_dump(mode="json"))
    engine.handle_tick_received(
        {
            "payload": {
                "symbol": "XAUUSD",
                "bid": str(evidence["current_price"] - Decimal("0.1")),
                "ask": str(evidence["current_price"] + Decimal("0.1")),
                "timestamp_utc": evidence["timestamp_utc"].isoformat(),
            },
        },
    )

    decision = engine.evaluate_cached("XAUUSD")
    assert decision.symbol == "XAUUSD"
    assert decision.state.value in {"BUY", "NO_TRADE", "NO_DATA"}


def test_pipeline_upstream_engines_produce_compatible_envelopes() -> None:
    candles = build_bullish_structure_candles(30)
    structure, liquidity, order_blocks, fvg, breaker, mitigation = _run_upstream_chain(candles)
    premium_discount = PremiumDiscountEngine(config=_premium_config()).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg.state,
        breaker_blocks=breaker.breaker_blocks,
        mitigation_blocks=mitigation.mitigation_blocks,
        timeframe="H1",
    )
    sessions = sample_session_analysis(timestamp_utc=london_open_timestamp())

    reference = build_bullish_upstream_evidence()
    engine = MarketDecisionEngine(config=relaxed_decision_config())
    decision = engine.decide(
        "XAUUSD",
        london_open_timestamp(),
        reference["current_price"],
        spread=reference["spread"],
        structure=structure,
        liquidity=liquidity,
        order_blocks=order_blocks,
        fair_value_gaps=fvg,
        breaker_blocks=breaker,
        mitigation_blocks=mitigation,
        premium_discount=premium_discount,
        sessions=sessions,
    )

    assert decision.metadata.engines_available >= 5
    assert structure.symbol == candles[0].symbol
