"""Unit tests for take profit generation."""

from decimal import Decimal

from backend.engines.market_decision.entry import EntryGenerator
from backend.engines.market_decision.evidence import EvidenceCollector
from backend.engines.market_decision.schemas import TradeDirection
from backend.engines.market_decision.stop_loss import StopLossGenerator
from backend.engines.market_decision.take_profit import TakeProfitGenerator
from tests.unit.engines.decision_conftest import build_bullish_upstream_evidence, relaxed_decision_config


def test_take_profit_targets_above_entry_for_buy() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(relaxed_decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=evidence["structure"],
        liquidity=evidence["liquidity"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
        premium_discount=evidence["premium_discount"],
    )
    entry_gen = EntryGenerator(relaxed_decision_config())
    entry, gate, _ = entry_gen.generate(bundle, TradeDirection.BUY)
    entry_price = entry_gen.entry_price(entry)
    stop, stop_gate = StopLossGenerator(relaxed_decision_config()).generate(
        bundle,
        TradeDirection.BUY,
        entry,
        entry_price,
    )
    assert stop_gate.passed is True

    targets = TakeProfitGenerator(relaxed_decision_config()).generate(
        bundle,
        TradeDirection.BUY,
        entry_price,
        stop,
    )

    assert len(targets) >= 1
    assert all(target > entry_price for target in targets)


def test_take_profit_fallback_when_no_targets() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(relaxed_decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
    )
    entry_price = Decimal("2320")
    stop = Decimal("2310")

    targets = TakeProfitGenerator(relaxed_decision_config()).generate(
        bundle,
        TradeDirection.BUY,
        entry_price,
        stop,
    )

    assert len(targets) == 1
    assert targets[0] > entry_price
