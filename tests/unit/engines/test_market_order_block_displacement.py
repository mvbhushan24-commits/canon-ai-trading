"""Unit tests for order block displacement validation."""

from decimal import Decimal

from backend.engines.market_order_block.displacement import DisplacementValidator
from backend.engines.market_order_block.origin import OriginDetector
from backend.engines.market_order_block.schemas import OrderBlockDirection
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.order_block_conftest import build_bullish_order_block_candles


def test_valid_displacement(order_block_config) -> None:
    candles = build_bullish_order_block_candles()
    origin_detector = OriginDetector(order_block_config)
    validator = DisplacementValidator(order_block_config)
    origins = origin_detector.find_bullish_origins(candles)

    assert origins
    candidate = origins[0]
    valid, displacement_index, magnitude, evidence = validator.validate(
        candidate,
        candles,
        build_sample_structure(),
    )

    assert valid is True
    assert displacement_index >= candidate.displacement_start_index
    assert magnitude >= Decimal(str(order_block_config.min_displacement_price))
    assert evidence


def test_insufficient_displacement_rejected(order_block_config) -> None:
    from datetime import UTC, datetime, timedelta

    from tests.unit.engines.conftest import make_candle

    strict_config = order_block_config.model_copy(update={"min_displacement_pips": 500.0})
    validator = DisplacementValidator(strict_config)
    origin_detector = OriginDetector(strict_config)

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start,
            open_price=Decimal("2300"),
            high=Decimal("2302"),
            low=Decimal("2298"),
            close=Decimal("2301"),
        ),
        make_candle(
            open_time=start + timedelta(hours=1),
            open_price=Decimal("2310"),
            high=Decimal("2311"),
            low=Decimal("2303"),
            close=Decimal("2304"),
        ),
        make_candle(
            open_time=start + timedelta(hours=2),
            open_price=Decimal("2304"),
            high=Decimal("2306"),
            low=Decimal("2303"),
            close=Decimal("2305"),
        ),
        make_candle(
            open_time=start + timedelta(hours=3),
            open_price=Decimal("2305"),
            high=Decimal("2307"),
            low=Decimal("2304"),
            close=Decimal("2306"),
        ),
    ]

    origins = origin_detector.find_bullish_origins(candles)
    assert origins
    valid, _, magnitude, _ = validator.validate(origins[0], candles)
    assert valid is False
    assert magnitude < Decimal(str(strict_config.min_displacement_price))
