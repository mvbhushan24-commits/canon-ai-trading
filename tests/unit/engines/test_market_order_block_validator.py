"""Unit tests for order block input validator."""

import pytest

from backend.engines.market_liquidity.schemas import LiquidityAnalysis, LiquiditySide
from backend.engines.market_order_block.exceptions import (
    InvalidLiquidityError,
    InvalidStructureError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockQuality,
    OrderBlockState,
    OrderBlockStatus,
)
from backend.engines.market_order_block.validator import OrderBlockInputValidator
from tests.unit.engines.liquidity_conftest import build_sample_structure


def test_validate_candles_success(order_block_candles) -> None:
    validator = OrderBlockInputValidator()
    result = validator.validate_candles(order_block_candles)
    assert result.is_valid


def test_validate_structure_mismatch(order_block_candles) -> None:
    validator = OrderBlockInputValidator()
    structure = build_sample_structure()
    result = validator.validate_structure(structure, symbol="OTHER", timeframe="H1")
    assert not result.is_valid


def test_validate_liquidity_mismatch(order_block_candles) -> None:
    validator = OrderBlockInputValidator()
    liquidity = LiquidityAnalysis(
        symbol="WRONG",
        timeframe="H1",
        timestamp_utc=order_block_candles[0].open_time_utc,
        bias=LiquiditySide.BUY_SIDE,
    )
    result = validator.validate_liquidity(
        liquidity,
        symbol="XAUUSD",
        timeframe="H1",
    )
    assert not result.is_valid


def test_validate_state_duplicate_blocks() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = OrderBlockInputValidator()
    block = OrderBlock(
        block_id="ob-dup",
        direction=OrderBlockDirection.BULLISH,
        status=OrderBlockStatus.FRESH,
        high=Decimal("2310"),
        low=Decimal("2304"),
        origin_bar_index=10,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=12,
        quality=OrderBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        structure_alignment=False,
        liquidity_confluence=False,
    )
    state = OrderBlockState(active_blocks=[block, block])
    result = validator.validate_state(state)
    assert not result.is_valid


def test_validate_or_raise_structure(order_block_candles) -> None:
    validator = OrderBlockInputValidator()
    structure = build_sample_structure().model_copy(update={"symbol": "WRONG"})
    with pytest.raises(InvalidStructureError):
        validator.validate_or_raise(order_block_candles, structure)


def test_validate_or_raise_liquidity(order_block_candles) -> None:
    validator = OrderBlockInputValidator()
    liquidity = LiquidityAnalysis(
        symbol="WRONG",
        timeframe="H1",
        timestamp_utc=order_block_candles[0].open_time_utc,
        bias=LiquiditySide.BUY_SIDE,
    )
    with pytest.raises(InvalidLiquidityError):
        validator.validate_or_raise(order_block_candles, None, liquidity)


def test_validate_or_raise_state(order_block_candles) -> None:
    validator = OrderBlockInputValidator()
    state = OrderBlockState(bar_count=-1)
    with pytest.raises(StateCorruptError):
        validator.validate_or_raise(order_block_candles, prior_state=state)


def test_validate_or_raise_bad_candles(order_block_config, sample_structure) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from tests.unit.engines.conftest import make_candle

    validator = OrderBlockInputValidator()
    bad = make_candle(
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    with pytest.raises(ValidationError):
        validator.validate_or_raise([bad] * 12)
