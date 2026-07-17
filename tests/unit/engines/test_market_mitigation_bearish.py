"""Unit tests for bearish mitigation block detection."""

from decimal import Decimal

import pytest

pytest_plugins = ["tests.unit.engines.mitigation_conftest"]

from backend.engines.market_mitigation.bearish import BearishMitigationDetector
from backend.engines.market_mitigation.engine import MitigationBlockEngine
from backend.engines.market_mitigation.schemas import MitigationBlockDirection
from tests.unit.engines.mitigation_conftest import (
    build_bearish_mitigation_base_candles,
    mitigation_config,
    primary_bearish_mitigation_origin_index,
)


def test_bearish_detector_finds_displacement_formation() -> None:
    candles = build_bearish_mitigation_base_candles()
    config = mitigation_config()
    formations = BearishMitigationDetector(config).find_formations(candles)

    assert formations
    origin_index = primary_bearish_mitigation_origin_index(candles)
    assert any(candidate.origin_bar_index == origin_index for candidate in formations)


def test_bearish_zone_bounds_body_mode() -> None:
    candles = build_bearish_mitigation_base_candles()
    origin_index = primary_bearish_mitigation_origin_index(candles)
    origin = candles[origin_index]
    config = mitigation_config(zone_bound_mode="body")
    formations = BearishMitigationDetector(config).find_formations(candles)
    candidate = next(c for c in formations if c.origin_bar_index == origin_index)

    assert candidate.high == max(origin.open, origin.close)
    assert candidate.low == min(origin.open, origin.close)
    assert candidate.direction is MitigationBlockDirection.BEARISH


def test_bearish_displacement_magnitude() -> None:
    candles = build_bearish_mitigation_base_candles()
    config = mitigation_config(min_displacement_pips=5.0)
    formations = BearishMitigationDetector(config).find_formations(candles)

    assert formations
    assert all(
        candidate.displacement_magnitude >= config.min_displacement_price
        for candidate in formations
    )


def test_bearish_skips_bearish_origin_candles() -> None:
    from datetime import UTC, datetime, timedelta

    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start + timedelta(hours=index),
            open_price=Decimal("2350"),
            high=Decimal("2351"),
            low=Decimal("2340"),
            close=Decimal("2342"),
        )
        for index in range(15)
    ]
    config = mitigation_config()
    assert not BearishMitigationDetector(config).find_formations(candles)


def test_engine_detect_bearish_blocks(mitigation_block_config) -> None:
    candles = build_bearish_mitigation_base_candles()
    engine = MitigationBlockEngine(config=mitigation_block_config)
    blocks = engine.detect_bearish_blocks(candles)

    assert blocks
    assert all(block.direction is MitigationBlockDirection.BEARISH for block in blocks)


def test_bearish_evidence_includes_displacement(mitigation_block_config) -> None:
    candles = build_bearish_mitigation_base_candles()
    engine = MitigationBlockEngine(config=mitigation_block_config)
    blocks = engine.detect_bearish_blocks(candles)

    assert blocks
    assert any("Displacement magnitude" in item for item in blocks[0].evidence)


def test_bearish_wick_zone_bound_mode() -> None:
    candles = build_bearish_mitigation_base_candles()
    origin_index = primary_bearish_mitigation_origin_index(candles)
    origin = candles[origin_index]
    config = mitigation_config(zone_bound_mode="wick")
    formations = BearishMitigationDetector(config).find_formations(candles)
    candidate = next(c for c in formations if c.origin_bar_index == origin_index)

    assert candidate.high == origin.high
    assert candidate.low == origin.low
