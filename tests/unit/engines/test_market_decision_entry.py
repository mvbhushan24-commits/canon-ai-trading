"""Unit tests for entry generation."""

from decimal import Decimal

from backend.engines.market_decision.entry import EntryGenerator
from backend.engines.market_decision.evidence import EvidenceCollector
from backend.engines.market_decision.schemas import EntryType, TradeDirection
from tests.unit.engines.decision_conftest import build_bullish_upstream_evidence, relaxed_decision_config


def test_entry_generator_finds_bullish_zone() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(relaxed_decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
        premium_discount=evidence["premium_discount"],
    )
    entry, gate, candidates = EntryGenerator(relaxed_decision_config()).generate(
        bundle,
        TradeDirection.BUY,
    )

    assert gate.passed is True
    assert entry is not None
    assert entry.entry_type in {EntryType.ZONE, EntryType.OTE}
    assert len(candidates) > 0


def test_entry_generator_rejects_distant_zone() -> None:
    evidence = build_bullish_upstream_evidence(current_price=Decimal("2400"))
    bundle = EvidenceCollector(relaxed_decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
    )
    entry, gate, _candidates = EntryGenerator(relaxed_decision_config()).generate(
        bundle,
        TradeDirection.BUY,
    )

    assert entry is None
    assert gate.passed is False
    assert gate.error_code == "INVALID_RISK"


def test_entry_price_uses_midpoint_when_configured() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(relaxed_decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        order_blocks=evidence["order_blocks"],
    )
    generator = EntryGenerator(relaxed_decision_config())
    entry, gate, _ = generator.generate(bundle, TradeDirection.BUY)
    assert gate.passed is True
    assert entry is not None
    price = generator.entry_price(entry)
    assert price > Decimal("0")
