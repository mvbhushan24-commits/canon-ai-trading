"""Unit tests for bullish mitigation block detection."""

from decimal import Decimal

import pytest

pytest_plugins = ["tests.unit.engines.mitigation_conftest"]

from backend.engines.market_mitigation.bullish import BullishMitigationDetector
from backend.engines.market_mitigation.engine import MitigationBlockEngine
from backend.engines.market_mitigation.schemas import MitigationBlockDirection
from tests.unit.engines.mitigation_conftest import (
    build_bullish_mitigation_base_candles,
    mitigation_config,
    primary_bullish_mitigation_origin_index,
)


def test_bullish_detector_finds_displacement_formation() -> None:
    candles = build_bullish_mitigation_base_candles()
    config = mitigation_config()
    formations = BullishMitigationDetector(config).find_formations(candles)

    assert formations
    origin_index = primary_bullish_mitigation_origin_index(candles)
    assert any(candidate.origin_bar_index == origin_index for candidate in formations)


def test_bullish_zone_bounds_body_mode() -> None:
    candles = build_bullish_mitigation_base_candles()
    origin_index = primary_bullish_mitigation_origin_index(candles)
    origin = candles[origin_index]
    config = mitigation_config(zone_bound_mode="body")
    formations = BullishMitigationDetector(config).find_formations(candles)
    candidate = next(c for c in formations if c.origin_bar_index == origin_index)

    assert candidate.high == max(origin.open, origin.close)
    assert candidate.low == min(origin.open, origin.close)
    assert candidate.direction is MitigationBlockDirection.BULLISH


def test_bullish_displacement_magnitude() -> None:
    candles = build_bullish_mitigation_base_candles()
    config = mitigation_config(min_displacement_pips=5.0)
    formations = BullishMitigationDetector(config).find_formations(candles)

    assert formations
    assert all(
        candidate.displacement_magnitude >= config.min_displacement_price
        for candidate in formations
    )


def test_bullish_skips_bullish_origin_candles() -> None:
    from datetime import UTC, datetime, timedelta

    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start + timedelta(hours=index),
            open_price=Decimal("2300"),
            high=Decimal("2310"),
            low=Decimal("2299"),
            close=Decimal("2308"),
        )
        for index in range(15)
    ]
    config = mitigation_config()
    assert not BullishMitigationDetector(config).find_formations(candles)


def test_bullish_skips_tiny_zones() -> None:
    from datetime import UTC, datetime, timedelta

    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    for index in range(12):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2300"),
                high=Decimal("2302"),
                low=Decimal("2298"),
                close=Decimal("2301"),
            )
        )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=12),
            open_price=Decimal("2301.00"),
            high=Decimal("2301.05"),
            low=Decimal("2300.95"),
            close=Decimal("2300.98"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=13),
            open_price=Decimal("2300.98"),
            high=Decimal("2310"),
            low=Decimal("2300.97"),
            close=Decimal("2309"),
        )
    )
    config = mitigation_config(min_zone_size_pips=100.0)
    assert not BullishMitigationDetector(config).find_formations(candles)


def test_engine_detect_bullish_blocks(mitigation_block_config) -> None:
    candles = build_bullish_mitigation_base_candles()
    engine = MitigationBlockEngine(config=mitigation_block_config)
    blocks = engine.detect_bullish_blocks(candles)

    assert blocks
    assert all(block.direction is MitigationBlockDirection.BULLISH for block in blocks)


def test_bullish_evidence_includes_displacement(mitigation_block_config) -> None:
    candles = build_bullish_mitigation_base_candles()
    engine = MitigationBlockEngine(config=mitigation_block_config)
    blocks = engine.detect_bullish_blocks(candles)

    assert blocks
    assert any("Displacement magnitude" in item for item in blocks[0].evidence)


def test_bullish_wick_zone_bound_mode() -> None:
    candles = build_bullish_mitigation_base_candles()
    origin_index = primary_bullish_mitigation_origin_index(candles)
    origin = candles[origin_index]
    config = mitigation_config(zone_bound_mode="wick")
    formations = BullishMitigationDetector(config).find_formations(candles)
    candidate = next(c for c in formations if c.origin_bar_index == origin_index)

    assert candidate.high == origin.high
    assert candidate.low == origin.low
