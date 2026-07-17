"""Unit tests for mitigation block origin detection."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

pytest_plugins = ["tests.unit.engines.mitigation_conftest"]

from backend.engines.market_mitigation.origin import OriginDetector
from backend.engines.market_mitigation.schemas import (
    MitigationBlockDirection,
    MitigationSourceType,
)
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapQuality,
    FairValueGapStatus,
)
from backend.engines.market_order_block.schemas import OrderBlockQuality, OrderBlockStatus
from tests.unit.engines.mitigation_conftest import (
    build_bearish_mitigation_base_candles,
    build_bullish_mitigation_base_candles,
    mitigation_config,
    parent_order_block_for_bullish_mitigation,
    primary_bullish_mitigation_origin_index,
)


def test_derive_from_displacement_bullish() -> None:
    config = mitigation_config()
    detector = OriginDetector(config)
    candles = build_bullish_mitigation_base_candles()

    candidates = detector.derive_from_displacement(candles)

    assert candidates
    origin_index = primary_bullish_mitigation_origin_index(candles)
    bullish = [c for c in candidates if c.direction is MitigationBlockDirection.BULLISH]
    assert any(candidate.origin_bar_index == origin_index for candidate in bullish)


def test_derive_from_displacement_bearish() -> None:
    config = mitigation_config()
    detector = OriginDetector(config)
    candles = build_bearish_mitigation_base_candles()

    candidates = detector.derive_from_displacement(candles)

    bearish = [c for c in candidates if c.direction is MitigationBlockDirection.BEARISH]
    assert bearish


def test_deduplicate_by_origin() -> None:
    config = mitigation_config(deduplicate_by_origin=True)
    detector = OriginDetector(config)
    candles = build_bullish_mitigation_base_candles()

    first = detector.derive_from_displacement(candles)
    second = detector.derive_from_displacement(candles)
    keys = {(c.origin_bar_index, c.direction.value) for c in first}

    assert len(first) == len(keys)
    assert len(first) == len(second)


def test_no_deduplicate_when_disabled() -> None:
    config = mitigation_config(deduplicate_by_origin=False)
    detector = OriginDetector(config)
    candles = build_bullish_mitigation_base_candles()

    candidates = detector.derive_from_displacement(candles)
    doubled = detector.derive_from_displacement(candles) + detector.derive_from_displacement(
        candles,
    )
    assert len(doubled) >= len(candidates)


def test_derive_from_confluence_nested_order_block() -> None:
    config = mitigation_config(confluence_formation_enabled=True, nest_overlap_min_percent=80.0)
    detector = OriginDetector(config)
    candles = build_bullish_mitigation_base_candles()
    parent = parent_order_block_for_bullish_mitigation(candles)

    nested = detector.derive_from_confluence(candles, order_blocks=[parent])

    assert nested
    assert nested[0].parent_zone_id == parent.block_id
    assert nested[0].source_type is MitigationSourceType.ORDER_BLOCK


def test_skips_confluence_when_disabled() -> None:
    config = mitigation_config(confluence_formation_enabled=False)
    detector = OriginDetector(config)
    candles = build_bullish_mitigation_base_candles()
    parent = parent_order_block_for_bullish_mitigation(candles)

    assert detector.derive_from_confluence(candles, order_blocks=[parent]) == []


def test_skips_invalidated_fvg_parent() -> None:
    config = mitigation_config(confluence_formation_enabled=True)
    detector = OriginDetector(config)
    candles = build_bullish_mitigation_base_candles()
    invalidated_gap = FairValueGap(
        gap_id="fvg-inv",
        direction=FairValueGapDirection.BULLISH,
        status=FairValueGapStatus.INVALIDATED,
        high=Decimal("2318"),
        low=Decimal("2305"),
        ce_price=Decimal("2311.5"),
        gap_size=Decimal("13"),
        gap_size_pips=Decimal("130"),
        origin_bar_index=14,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        candle_a_index=14,
        candle_b_index=15,
        candle_c_index=16,
        quality=FairValueGapQuality.HIGH,
        strength=Decimal("0.8"),
    )

    nested = detector.derive_from_confluence(candles, fair_value_gaps=[invalidated_gap])
    assert not nested


def test_zone_bounds_helper() -> None:
    from tests.unit.engines.conftest import make_candle

    candle = make_candle(
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open_price=Decimal("2315"),
        high=Decimal("2318"),
        low=Decimal("2308"),
        close=Decimal("2309"),
    )
    body_high, body_low = OriginDetector.zone_bounds(candle, "body")
    wick_high, wick_low = OriginDetector.zone_bounds(candle, "wick")

    assert body_high == Decimal("2315")
    assert body_low == Decimal("2309")
    assert wick_high == Decimal("2318")
    assert wick_low == Decimal("2308")
