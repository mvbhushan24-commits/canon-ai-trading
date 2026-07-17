"""Unit tests for evidence collection and normalization."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_decision.evidence import (
    EvidenceCollector,
    EvidenceNormalizer,
    resolve_provisional_direction,
)
from backend.engines.market_decision.schemas import DirectionBias, TradeDirection
from tests.unit.engines.decision_conftest import build_bullish_upstream_evidence, decision_config


def test_collector_marks_all_engines_available() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=evidence["structure"],
        liquidity=evidence["liquidity"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
        breaker_blocks=evidence["breaker_blocks"],
        mitigation_blocks=evidence["mitigation_blocks"],
        premium_discount=evidence["premium_discount"],
        sessions=evidence["sessions"],
    )

    assert bundle.availability.available_count == 8
    assert bundle.availability.stale_count >= 0


def test_collector_flags_stale_evidence() -> None:
    evidence = build_bullish_upstream_evidence()
    stale_structure = evidence["structure"].model_copy(
        update={
            "timestamp_utc": evidence["timestamp_utc"] - timedelta(seconds=600),
        },
    )
    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=stale_structure,
    )

    assert bundle.availability.structure_available is True
    assert bundle.availability.structure_stale is True


def test_normalizer_maps_structure_trend_to_bias() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        structure=evidence["structure"],
        liquidity=evidence["liquidity"],
        order_blocks=evidence["order_blocks"],
        fair_value_gaps=evidence["fair_value_gaps"],
        breaker_blocks=evidence["breaker_blocks"],
        mitigation_blocks=evidence["mitigation_blocks"],
        premium_discount=evidence["premium_discount"],
        sessions=evidence["sessions"],
    )
    normalized = EvidenceNormalizer().normalize(bundle)
    engine_ids = {item.engine_id for item in normalized}

    assert "market_structure" in engine_ids
    structure_record = next(item for item in normalized if item.engine_id == "market_structure")
    assert structure_record.direction_bias is DirectionBias.BULLISH
    assert structure_record.available is True


def test_normalizer_maps_liquidity_sell_side_to_bullish() -> None:
    evidence = build_bullish_upstream_evidence()
    bundle = EvidenceCollector(decision_config()).collect(
        "XAUUSD",
        evidence["timestamp_utc"],
        evidence["current_price"],
        liquidity=evidence["liquidity"],
    )
    normalized = EvidenceNormalizer().normalize(bundle)
    liquidity_record = next(item for item in normalized if item.engine_id == "market_liquidity")
    assert liquidity_record.direction_bias is DirectionBias.BULLISH


def test_resolve_provisional_direction_buy() -> None:
    direction = resolve_provisional_direction(
        Decimal("0.50"),
        Decimal("0.10"),
        min_directional_weight=0.35,
    )
    assert direction is TradeDirection.BUY


def test_resolve_provisional_direction_sell() -> None:
    direction = resolve_provisional_direction(
        Decimal("0.10"),
        Decimal("0.50"),
        min_directional_weight=0.35,
    )
    assert direction is TradeDirection.SELL


def test_resolve_provisional_direction_none_when_insufficient() -> None:
    direction = resolve_provisional_direction(
        Decimal("0.20"),
        Decimal("0.15"),
        min_directional_weight=0.35,
    )
    assert direction is TradeDirection.NONE
