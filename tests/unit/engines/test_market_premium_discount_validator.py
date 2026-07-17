"""Unit tests for premium / discount input validator."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

pytest_plugins = ["tests.unit.engines.premium_discount_conftest"]

from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity.schemas import LiquidityState
from backend.engines.market_mitigation.schemas import MitigationBlock, MitigationBlockDirection, MitigationBlockQuality, MitigationBlockStatus
from backend.engines.market_order_block.schemas import OrderBlockDirection, OrderBlockQuality, OrderBlockStatus
from backend.engines.market_premium_discount.exceptions import (
    InvalidBreakerBlocksError,
    InvalidFVGStateError,
    InvalidHTFContextError,
    InvalidLiquidityStateError,
    InvalidMitigationBlocksError,
    InvalidOrderBlocksError,
    InvalidStructureError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_premium_discount.schemas import PremiumDiscountState
from backend.engines.market_premium_discount.validator import PremiumDiscountInputValidator
from tests.unit.engines.conftest import make_candle
from tests.unit.engines.premium_discount_conftest import (
    build_premium_discount_candles,
    build_premium_discount_structure,
    build_valid_dealing_range,
    premium_config,
    premium_order_blocks,
    sample_htf_premium_discount_context,
)


def test_validate_candles_empty() -> None:
    validator = PremiumDiscountInputValidator()
    result = validator.validate_candles([])
    assert result.is_valid is False
    assert "empty" in result.errors[0].lower()


def test_validate_candles_mixed_symbols() -> None:
    validator = PremiumDiscountInputValidator()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(open_time=start, open_price=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100")),
        make_candle(
            open_time=start + timedelta(hours=1),
            open_price=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            symbol="EURUSD",
        ),
    ]
    result = validator.validate_candles(candles)
    assert result.is_valid is False
    assert any("Mixed symbols" in error for error in result.errors)


def test_validate_candles_invalid_ohlc() -> None:
    validator = PremiumDiscountInputValidator()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(open_time=start, open_price=Decimal("100"), high=Decimal("90"), low=Decimal("95"), close=Decimal("92")),
    ]
    result = validator.validate_candles(candles)
    assert result.is_valid is False


def test_validate_candles_duplicate_timestamp() -> None:
    validator = PremiumDiscountInputValidator()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candle = make_candle(open_time=start, open_price=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"))
    result = validator.validate_candles([candle, candle])
    assert result.is_valid is False
    assert any("Duplicate timestamp" in error for error in result.errors)


def test_validate_structure_mismatch() -> None:
    validator = PremiumDiscountInputValidator()
    structure = build_premium_discount_structure().model_copy(update={"symbol": "EURUSD"})
    result = validator.validate_structure(structure, symbol="XAUUSD", timeframe="H1")
    assert result.is_valid is False


def test_validate_liquidity_state_bar_count() -> None:
    validator = PremiumDiscountInputValidator()
    state = LiquidityState(bar_count=50)
    result = validator.validate_liquidity_state(state, bar_count=30)
    assert result.is_valid is False


def test_validate_fvg_state_bar_count() -> None:
    validator = PremiumDiscountInputValidator()
    state = FairValueGapState(bar_count=100)
    result = validator.validate_fvg_state(state, bar_count=20)
    assert result.is_valid is False


def test_validate_order_blocks_invalid_bounds() -> None:
    validator = PremiumDiscountInputValidator()
    blocks = premium_order_blocks()
    invalid = blocks[0].model_copy(update={"high": Decimal("1"), "low": Decimal("5")})
    result = validator.validate_order_blocks([invalid], symbol="XAUUSD", timeframe="H1")
    assert result.is_valid is False


def test_validate_order_blocks_invalid_strength() -> None:
    validator = PremiumDiscountInputValidator()
    blocks = premium_order_blocks()
    invalid = blocks[0].model_copy(update={"strength": Decimal("1.5")})
    result = validator.validate_order_blocks([invalid], symbol="XAUUSD", timeframe="H1")
    assert result.is_valid is False


def test_validate_breaker_blocks_invalid_bounds() -> None:
    from backend.engines.market_breaker.schemas import (
        BreakerBlock,
        BreakerBlockDirection,
        BreakerBlockQuality,
        BreakerBlockStatus,
        BreakerSourceType,
    )

    validator = PremiumDiscountInputValidator()
    block = BreakerBlock(
        breaker_id="brk-1",
        direction=BreakerBlockDirection.BULLISH,
        status=BreakerBlockStatus.CONFIRMED,
        high=Decimal("100"),
        low=Decimal("110"),
        source_type=BreakerSourceType.ORDER_BLOCK,
        source_id="ob-1",
        source_direction="bullish",
        origin_bar_index=5,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        invalidation_bar_index=6,
        invalidation_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=7,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=BreakerBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=True,
        confirmation_reason="Test breaker",
        structure_alignment=False,
        liquidity_confluence=False,
        fvg_confluence=False,
    )
    result = validator.validate_breaker_blocks([block], symbol="XAUUSD", timeframe="H1")
    assert result.is_valid is False


def test_validate_mitigation_blocks_invalid_bounds() -> None:
    validator = PremiumDiscountInputValidator()
    block = MitigationBlock(
        block_id="mb-1",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("100"),
        low=Decimal("110"),
        origin_bar_index=5,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=6,
        displacement_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=7,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=MitigationBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="test",
    )
    result = validator.validate_mitigation_blocks([block], symbol="XAUUSD", timeframe="H1")
    assert result.is_valid is False


def test_validate_htf_context_invalid_range() -> None:
    validator = PremiumDiscountInputValidator()
    invalid_range = build_valid_dealing_range().model_copy(update={"is_valid": False})
    context = sample_htf_premium_discount_context(invalid_range)
    result = validator.validate_htf_context(context)
    assert result.is_valid is False


def test_validate_prior_state_corrupt_bounds() -> None:
    validator = PremiumDiscountInputValidator()
    invalid_range = build_valid_dealing_range().model_copy(update={"high": Decimal("100"), "low": Decimal("200")})
    state = PremiumDiscountState(active_dealing_range=invalid_range, bar_count=-1)
    result = validator.validate_prior_state(state)
    assert result.is_valid is False


def test_validate_or_raise_candles_failure() -> None:
    validator = PremiumDiscountInputValidator()
    with pytest.raises(ValidationError):
        validator.validate_or_raise([], None, None, None, None, None, None, None, None)


def test_validate_or_raise_structure_failure() -> None:
    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    structure = build_premium_discount_structure().model_copy(update={"symbol": "EURUSD"})
    with pytest.raises(InvalidStructureError):
        validator.validate_or_raise(candles, structure, None, None, None, None, None, None, None)


def test_validate_or_raise_liquidity_failure() -> None:
    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    with pytest.raises(InvalidLiquidityStateError):
        validator.validate_or_raise(
            candles,
            None,
            LiquidityState(bar_count=100),
            None,
            None,
            None,
            None,
            None,
            None,
        )


def test_validate_or_raise_order_blocks_failure() -> None:
    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    blocks = premium_order_blocks()
    invalid = blocks[0].model_copy(update={"high": Decimal("1"), "low": Decimal("5")})
    with pytest.raises(InvalidOrderBlocksError):
        validator.validate_or_raise(candles, None, None, [invalid], None, None, None, None, None)


def test_validate_or_raise_fvg_failure() -> None:
    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    with pytest.raises(InvalidFVGStateError):
        validator.validate_or_raise(
            candles,
            None,
            None,
            None,
            FairValueGapState(bar_count=100),
            None,
            None,
            None,
            None,
        )


def test_validate_or_raise_breaker_failure() -> None:
    from backend.engines.market_breaker.schemas import (
        BreakerBlock,
        BreakerBlockDirection,
        BreakerBlockQuality,
        BreakerBlockStatus,
        BreakerSourceType,
    )

    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    block = BreakerBlock(
        breaker_id="brk-1",
        direction=BreakerBlockDirection.BULLISH,
        status=BreakerBlockStatus.CONFIRMED,
        high=Decimal("100"),
        low=Decimal("110"),
        source_type=BreakerSourceType.ORDER_BLOCK,
        source_id="ob-1",
        source_direction="bullish",
        origin_bar_index=5,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        invalidation_bar_index=6,
        invalidation_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=7,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=BreakerBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=True,
        confirmation_reason="Test breaker",
        structure_alignment=False,
        liquidity_confluence=False,
        fvg_confluence=False,
    )
    with pytest.raises(InvalidBreakerBlocksError):
        validator.validate_or_raise(candles, None, None, None, None, [block], None, None, None)


def test_validate_or_raise_mitigation_failure() -> None:
    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    block = MitigationBlock(
        block_id="mb-1",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("100"),
        low=Decimal("110"),
        origin_bar_index=5,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=6,
        displacement_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=7,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=MitigationBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="test",
    )
    with pytest.raises(InvalidMitigationBlocksError):
        validator.validate_or_raise(candles, None, None, None, None, None, [block], None, None)


def test_validate_or_raise_htf_failure() -> None:
    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    invalid_range = build_valid_dealing_range().model_copy(update={"is_valid": False})
    context = sample_htf_premium_discount_context(invalid_range)
    with pytest.raises(InvalidHTFContextError):
        validator.validate_or_raise(candles, None, None, None, None, None, None, None, context)


def test_validate_or_raise_state_corrupt() -> None:
    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    invalid_range = build_valid_dealing_range().model_copy(update={"high": Decimal("100"), "low": Decimal("200")})
    state = PremiumDiscountState(active_dealing_range=invalid_range)
    with pytest.raises(StateCorruptError):
        validator.validate_or_raise(candles, None, None, None, None, None, None, state, None)


def test_validate_or_raise_success() -> None:
    validator = PremiumDiscountInputValidator()
    candles = build_premium_discount_candles(12)
    structure = build_premium_discount_structure()
    validator.validate_or_raise(
        candles,
        structure,
        None,
        premium_order_blocks(),
        None,
        None,
        None,
        None,
        sample_htf_premium_discount_context(),
    )
