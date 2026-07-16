"""Unit tests for breaker block input validator."""

import pytest

pytest_plugins = ["tests.unit.engines.order_breaker_conftest"]

from backend.engines.market_breaker.exceptions import (
    InvalidFVGStateError,
    InvalidLiquidityStateError,
    InvalidOrderBlocksError,
    InvalidStructureError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_breaker.schemas import (
    BreakerBlock,
    BreakerBlockDirection,
    BreakerBlockQuality,
    BreakerBlockState,
    BreakerBlockStatus,
)
from backend.engines.market_breaker.validator import BreakerBlockInputValidator
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity.schemas import LiquidityState
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockQuality,
    OrderBlockStatus,
)
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.order_breaker_conftest import (
    build_breaker_base_candles,
    invalidated_bullish_order_block,
)


def test_validate_candles_success(breaker_candles) -> None:
    validator = BreakerBlockInputValidator()
    result = validator.validate_candles(breaker_candles)
    assert result.is_valid


def test_validate_candles_empty() -> None:
    validator = BreakerBlockInputValidator()
    result = validator.validate_candles([])
    assert not result.is_valid
    assert "empty" in result.errors[0].lower()


def test_validate_structure_mismatch(breaker_candles) -> None:
    validator = BreakerBlockInputValidator()
    structure = build_sample_structure()
    result = validator.validate_structure(structure, symbol="OTHER", timeframe="H1")
    assert not result.is_valid


def test_validate_liquidity_state_bar_count(breaker_candles) -> None:
    validator = BreakerBlockInputValidator()
    state = LiquidityState(bar_count=999)
    result = validator.validate_liquidity_state(state, bar_count=len(breaker_candles))
    assert not result.is_valid


def test_validate_fvg_state_bar_count(breaker_candles) -> None:
    validator = BreakerBlockInputValidator()
    state = FairValueGapState(bar_count=999)
    result = validator.validate_fvg_state(state, bar_count=len(breaker_candles))
    assert not result.is_valid


def test_validate_order_blocks_requires_invalidated_status() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = BreakerBlockInputValidator()
    fresh_block = OrderBlock(
        block_id="ob-fresh",
        direction=OrderBlockDirection.BULLISH,
        status=OrderBlockStatus.FRESH,
        high=Decimal("2316"),
        low=Decimal("2308"),
        origin_bar_index=10,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=12,
        quality=OrderBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        structure_alignment=False,
        liquidity_confluence=False,
    )
    result = validator.validate_order_blocks([fresh_block])
    assert not result.is_valid


def test_validate_state_duplicate_breakers() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = BreakerBlockInputValidator()
    breaker = BreakerBlock(
        breaker_id="brk-dup",
        direction=BreakerBlockDirection.BEARISH,
        status=BreakerBlockStatus.CANDIDATE,
        high=Decimal("2316"),
        low=Decimal("2308"),
        source_type="order_block",
        source_id="ob-1",
        source_direction="bullish",
        invalidation_bar_index=17,
        invalidation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        formation_bar_index=18,
        formation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        quality=BreakerBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="Awaiting retest",
        structure_alignment=False,
        liquidity_confluence=False,
        fvg_confluence=False,
    )
    state = BreakerBlockState(active_breakers=[breaker, breaker])
    result = validator.validate_state(state)
    assert not result.is_valid


def test_validate_or_raise_structure(breaker_candles) -> None:
    validator = BreakerBlockInputValidator()
    structure = build_sample_structure().model_copy(update={"symbol": "WRONG"})
    with pytest.raises(InvalidStructureError):
        validator.validate_or_raise(breaker_candles, structure)


def test_validate_or_raise_liquidity_state(breaker_candles) -> None:
    validator = BreakerBlockInputValidator()
    state = LiquidityState(bar_count=999)
    with pytest.raises(InvalidLiquidityStateError):
        validator.validate_or_raise(breaker_candles, liquidity_state=state)


def test_validate_or_raise_fvg_state(breaker_candles) -> None:
    validator = BreakerBlockInputValidator()
    state = FairValueGapState(bar_count=999)
    with pytest.raises(InvalidFVGStateError):
        validator.validate_or_raise(breaker_candles, fair_value_gap_state=state)


def test_validate_or_raise_invalidated_order_blocks(breaker_candles) -> None:
    candles = build_breaker_base_candles()
    validator = BreakerBlockInputValidator()
    block = invalidated_bullish_order_block(candles).model_copy(
        update={"status": OrderBlockStatus.FRESH},
    )
    with pytest.raises(InvalidOrderBlocksError):
        validator.validate_or_raise(candles, invalidated_order_blocks=[block])


def test_validate_or_raise_state(breaker_candles) -> None:
    validator = BreakerBlockInputValidator()
    state = BreakerBlockState(bar_count=-1)
    with pytest.raises(StateCorruptError):
        validator.validate_or_raise(breaker_candles, prior_state=state)


def test_validate_or_raise_bad_candles() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from tests.unit.engines.conftest import make_candle

    validator = BreakerBlockInputValidator()
    bad = make_candle(
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    with pytest.raises(ValidationError):
        validator.validate_or_raise([bad] * 12)
