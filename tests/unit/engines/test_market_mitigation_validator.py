"""Unit tests for mitigation block input validator."""

import pytest

pytest_plugins = ["tests.unit.engines.mitigation_conftest"]

from backend.engines.market_mitigation.exceptions import (
    InvalidBreakerBlocksError,
    InvalidFVGStateError,
    InvalidHTFBlocksError,
    InvalidLiquidityStateError,
    InvalidOrderBlocksError,
    InvalidStructureError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockDirection,
    MitigationBlockQuality,
    MitigationBlockState,
    MitigationBlockStatus,
)
from backend.engines.market_mitigation.validator import MitigationBlockInputValidator
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity.schemas import LiquidityState
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockQuality,
    OrderBlockStatus,
)
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.mitigation_conftest import build_bullish_mitigation_base_candles


def test_validate_candles_success(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    result = validator.validate_candles(mitigation_candles)
    assert result.is_valid


def test_validate_candles_empty() -> None:
    validator = MitigationBlockInputValidator()
    result = validator.validate_candles([])
    assert not result.is_valid
    assert "empty" in result.errors[0].lower()


def test_validate_structure_mismatch(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    structure = build_sample_structure()
    result = validator.validate_structure(structure, symbol="OTHER", timeframe="H1")
    assert not result.is_valid


def test_validate_liquidity_state_bar_count(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    state = LiquidityState(bar_count=999)
    result = validator.validate_liquidity_state(state, bar_count=len(mitigation_candles))
    assert not result.is_valid


def test_validate_fvg_state_bar_count(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    state = FairValueGapState(bar_count=999)
    result = validator.validate_fvg_state(state, bar_count=len(mitigation_candles))
    assert not result.is_valid


def test_validate_order_blocks_invalid_bounds() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = MitigationBlockInputValidator()
    bad_block = OrderBlock(
        block_id="ob-bad",
        direction=OrderBlockDirection.BULLISH,
        status=OrderBlockStatus.FRESH,
        high=Decimal("2300"),
        low=Decimal("2310"),
        origin_bar_index=10,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=12,
        quality=OrderBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        structure_alignment=False,
        liquidity_confluence=False,
    )
    result = validator.validate_order_blocks([bad_block], symbol="XAUUSD", timeframe="H1")
    assert not result.is_valid


def test_validate_state_duplicate_blocks() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = MitigationBlockInputValidator()
    block = MitigationBlock(
        block_id="mb-dup",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("2315"),
        low=Decimal("2309"),
        origin_bar_index=14,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=15,
        displacement_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=16,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=MitigationBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="Test",
    )
    state = MitigationBlockState(active_blocks=[block, block], bar_count=10)
    result = validator.validate_state(state)
    assert not result.is_valid


def test_validate_htf_blocks_invalid_bounds() -> None:
    validator = MitigationBlockInputValidator()
    from datetime import UTC, datetime
    from decimal import Decimal

    bad_htf = MitigationBlock(
        block_id="mb-htf-bad",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("2300"),
        low=Decimal("2310"),
        origin_bar_index=5,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=6,
        displacement_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=6,
        formation_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        quality=MitigationBlockQuality.LOW,
        strength=Decimal("0.3"),
        is_confirmed=False,
        confirmation_reason="Test",
    )
    result = validator.validate_htf_blocks([bad_htf], timeframe="H1")
    assert not result.is_valid


def test_validate_or_raise_success(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    structure = build_sample_structure()
    validator.validate_or_raise(mitigation_candles, structure)


def test_validate_or_raise_candle_failure() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from tests.unit.engines.conftest import make_candle

    validator = MitigationBlockInputValidator()
    bad = make_candle(
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    with pytest.raises(ValidationError):
        validator.validate_or_raise([bad] * 12)


def test_validate_or_raise_structure_failure(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    structure = build_sample_structure().model_copy(update={"symbol": "EURUSD"})
    with pytest.raises(InvalidStructureError):
        validator.validate_or_raise(
            mitigation_candles,
            structure,
        )


def test_validate_or_raise_liquidity_failure(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    with pytest.raises(InvalidLiquidityStateError):
        validator.validate_or_raise(
            mitigation_candles,
            liquidity_state=LiquidityState(bar_count=9999),
        )


def test_validate_or_raise_fvg_failure(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    with pytest.raises(InvalidFVGStateError):
        validator.validate_or_raise(
            mitigation_candles,
            fair_value_gap_state=FairValueGapState(bar_count=9999),
        )


def test_validate_or_raise_order_blocks_failure(mitigation_candles) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = MitigationBlockInputValidator()
    bad_block = OrderBlock(
        block_id="ob-bad",
        direction=OrderBlockDirection.BULLISH,
        status=OrderBlockStatus.FRESH,
        high=Decimal("2300"),
        low=Decimal("2310"),
        origin_bar_index=10,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=12,
        quality=OrderBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        structure_alignment=False,
        liquidity_confluence=False,
    )
    with pytest.raises(InvalidOrderBlocksError):
        validator.validate_or_raise(mitigation_candles, order_blocks=[bad_block])


def test_validate_or_raise_state_failure(mitigation_candles) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = MitigationBlockInputValidator()
    block = MitigationBlock(
        block_id="mb-dup",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("2315"),
        low=Decimal("2309"),
        origin_bar_index=14,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=15,
        displacement_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=16,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=MitigationBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="Test",
    )
    with pytest.raises(StateCorruptError):
        validator.validate_or_raise(
            mitigation_candles,
            prior_state=MitigationBlockState(active_blocks=[block, block]),
        )


def test_validate_breaker_blocks_invalid_bounds() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from backend.engines.market_breaker.schemas import (
        BreakerBlock,
        BreakerBlockDirection,
        BreakerBlockQuality,
        BreakerBlockStatus,
        BreakerSourceType,
    )

    validator = MitigationBlockInputValidator()
    bad_breaker = BreakerBlock(
        breaker_id="brk-bad",
        direction=BreakerBlockDirection.BEARISH,
        status=BreakerBlockStatus.CANDIDATE,
        high=Decimal("2300"),
        low=Decimal("2310"),
        source_type=BreakerSourceType.ORDER_BLOCK,
        source_id="ob-1",
        source_direction="bullish",
        invalidation_bar_index=10,
        invalidation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        formation_bar_index=12,
        formation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        quality=BreakerBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="Test",
        structure_alignment=False,
        liquidity_confluence=False,
        fvg_confluence=False,
    )
    result = validator.validate_breaker_blocks([bad_breaker])
    assert not result.is_valid


def test_validate_or_raise_breaker_failure(mitigation_candles) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from backend.engines.market_breaker.schemas import (
        BreakerBlock,
        BreakerBlockDirection,
        BreakerBlockQuality,
        BreakerBlockStatus,
        BreakerSourceType,
    )

    validator = MitigationBlockInputValidator()
    bad_breaker = BreakerBlock(
        breaker_id="brk-bad",
        direction=BreakerBlockDirection.BEARISH,
        status=BreakerBlockStatus.CANDIDATE,
        high=Decimal("2300"),
        low=Decimal("2310"),
        source_type=BreakerSourceType.ORDER_BLOCK,
        source_id="ob-1",
        source_direction="bullish",
        invalidation_bar_index=10,
        invalidation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        formation_bar_index=12,
        formation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        quality=BreakerBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="Test",
        structure_alignment=False,
        liquidity_confluence=False,
        fvg_confluence=False,
    )
    with pytest.raises(InvalidBreakerBlocksError):
        validator.validate_or_raise(mitigation_candles, breaker_blocks=[bad_breaker])


def test_validate_or_raise_htf_failure(mitigation_candles) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    validator = MitigationBlockInputValidator()
    bad_htf = MitigationBlock(
        block_id="mb-htf-bad",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("2300"),
        low=Decimal("2310"),
        origin_bar_index=5,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=6,
        displacement_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=6,
        formation_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        quality=MitigationBlockQuality.LOW,
        strength=Decimal("0.3"),
        is_confirmed=False,
        confirmation_reason="Test",
    )
    with pytest.raises(InvalidHTFBlocksError):
        validator.validate_or_raise(mitigation_candles, htf_mitigation_blocks=[bad_htf])


def test_validate_candles_chronological(mitigation_candles) -> None:
    validator = MitigationBlockInputValidator()
    reversed_candles = list(reversed(mitigation_candles))
    result = validator.validate_candles(reversed_candles)
    assert not result.is_valid


def test_validate_order_blocks_success(mitigation_candles) -> None:
    from tests.unit.engines.mitigation_conftest import parent_order_block_for_bullish_mitigation

    validator = MitigationBlockInputValidator()
    block = parent_order_block_for_bullish_mitigation(mitigation_candles)
    result = validator.validate_order_blocks(
        [block],
        symbol=mitigation_candles[0].symbol,
        timeframe=mitigation_candles[0].timeframe,
    )
    assert result.is_valid
