"""Unit tests for stop loss generation."""

from decimal import Decimal

from backend.engines.market_decision.entry import EntryGenerator
from backend.engines.market_decision.evidence import EvidenceCollector
from backend.engines.market_decision.schemas import TradeDirection
from backend.engines.market_decision.stop_loss import StopLossGenerator
from tests.unit.engines.decision_conftest import build_bullish_upstream_evidence, relaxed_decision_config


def test_stop_loss_placed_below_entry_for_buy() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(relaxed_decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=evidence["structure"],
        order_blocks=evidence["order_blocks"],
        liquidity=evidence["liquidity"],
    )
    generator = EntryGenerator(relaxed_decision_config())
    entry, gate, _ = generator.generate(bundle, TradeDirection.BUY)
    assert gate.passed is True
    entry_price = generator.entry_price(entry)

    stop, stop_gate = StopLossGenerator(relaxed_decision_config()).generate(
        bundle,
        TradeDirection.BUY,
        entry,
        entry_price,
    )

    assert stop_gate.passed is True
    assert stop is not None
    assert stop < entry_price


def test_stop_loss_rejects_oversized_stop() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(relaxed_decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=evidence["structure"],
        order_blocks=evidence["order_blocks"],
    )
    generator = EntryGenerator(relaxed_decision_config())
    entry, gate, _ = generator.generate(bundle, TradeDirection.BUY)
    entry_price = generator.entry_price(entry)

    config = relaxed_decision_config(risk={"max_stop_size_pips": 5.0})
    stop, stop_gate = StopLossGenerator(config).generate(
        bundle,
        TradeDirection.BUY,
        entry,
        entry_price,
    )

    assert stop is None
    assert stop_gate.passed is False
    assert stop_gate.error_code == "INVALID_RISK"
