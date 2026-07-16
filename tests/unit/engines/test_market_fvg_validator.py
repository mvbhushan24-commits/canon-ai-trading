"""Unit tests for fair value gap input validator."""

import pytest

from backend.engines.market_fvg.exceptions import (
    InvalidLiquidityStateError,
    InvalidOrderBlockStateError,
    InvalidStructureError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapQuality,
    FairValueGapState,
    FairValueGapStatus,
)
from backend.engines.market_fvg.validator import FairValueGapInputValidator
from backend.engines.market_liquidity.schemas import LiquidityState
from backend.engines.market_order_block.schemas import OrderBlockState
from tests.unit.engines.liquidity_conftest import build_sample_structure


def test_validate_candles_success(fvg_candles) -> None:
    validator = FairValueGapInputValidator()
    result = validator.validate_candles(fvg_candles)
    assert result.is_valid


def test_validate_candles_empty() -> None:
    validator = FairValueGapInputValidator()
    result = validator.validate_candles([])
    assert not result.is_valid
    assert "empty" in result.errors[0].lower()


def test_validate_structure_mismatch(fvg_candles) -> None:
    validator = FairValueGapInputValidator()
    structure = build_sample_structure()
    result = validator.validate_structure(structure, symbol="OTHER", timeframe="H1")
    assert not result.is_valid


def test_validate_liquidity_state_bar_count(fvg_candles) -> None:
    validator = FairValueGapInputValidator()
    state = LiquidityState(bar_count=999)
    result = validator.validate_liquidity_state(state, bar_count=len(fvg_candles))
    assert not result.is_valid


def test_validate_order_block_state_bar_count(fvg_candles) -> None:
    validator = FairValueGapInputValidator()
    state = OrderBlockState(bar_count=999)
    result = validator.validate_order_block_state(state, bar_count=len(fvg_candles))
    assert not result.is_valid


def test_validate_state_duplicate_gaps() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = FairValueGapInputValidator()
    gap = FairValueGap(
        gap_id="fvg-dup",
        direction=FairValueGapDirection.BULLISH,
        status=FairValueGapStatus.OPEN,
        high=Decimal("2305"),
        low=Decimal("2300"),
        ce_price=Decimal("2302.5"),
        gap_size=Decimal("5"),
        gap_size_pips=Decimal("50"),
        origin_bar_index=10,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        candle_a_index=10,
        candle_b_index=11,
        candle_c_index=12,
        quality=FairValueGapQuality.MEDIUM,
        strength=Decimal("0.6"),
    )
    state = FairValueGapState(active_gaps=[gap, gap])
    result = validator.validate_state(state)
    assert not result.is_valid


def test_validate_or_raise_structure(fvg_candles) -> None:
    validator = FairValueGapInputValidator()
    structure = build_sample_structure().model_copy(update={"symbol": "WRONG"})
    with pytest.raises(InvalidStructureError):
        validator.validate_or_raise(fvg_candles, structure)


def test_validate_or_raise_liquidity_state(fvg_candles) -> None:
    validator = FairValueGapInputValidator()
    state = LiquidityState(bar_count=999)
    with pytest.raises(InvalidLiquidityStateError):
        validator.validate_or_raise(fvg_candles, liquidity_state=state)


def test_validate_or_raise_order_block_state(fvg_candles) -> None:
    validator = FairValueGapInputValidator()
    state = OrderBlockState(bar_count=999)
    with pytest.raises(InvalidOrderBlockStateError):
        validator.validate_or_raise(fvg_candles, order_block_state=state)


def test_validate_or_raise_state(fvg_candles) -> None:
    validator = FairValueGapInputValidator()
    state = FairValueGapState(bar_count=-1)
    with pytest.raises(StateCorruptError):
        validator.validate_or_raise(fvg_candles, prior_state=state)


def test_validate_or_raise_bad_candles(sample_structure) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from tests.unit.engines.conftest import make_candle

    validator = FairValueGapInputValidator()
    bad = make_candle(
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    with pytest.raises(ValidationError):
        validator.validate_or_raise([bad] * 12, sample_structure)
