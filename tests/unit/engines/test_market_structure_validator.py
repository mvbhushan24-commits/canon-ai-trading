"""Unit tests for structure input validation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.engines.market_structure.exceptions import ValidationError
from backend.engines.market_structure.validator import StructureInputValidator
from tests.unit.engines.conftest import make_candle


def test_validate_candles_success() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start + timedelta(hours=i),
            open_price=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
        )
        for i in range(3)
    ]
    result = StructureInputValidator().validate_candles(candles)
    assert result.is_valid is True


def test_validate_duplicate_timestamp() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candle = make_candle(
        open_time=start,
        open_price=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
    )
    result = StructureInputValidator().validate_candles([candle, candle])
    assert result.is_valid is False
    assert any("Duplicate" in error for error in result.errors)


def test_validate_invalid_ohlc() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candle = make_candle(
        open_time=start,
        open_price=Decimal("100"),
        high=Decimal("98"),
        low=Decimal("99"),
        close=Decimal("100"),
    )
    result = StructureInputValidator().validate_candles([candle])
    assert result.is_valid is False


def test_validate_or_raise() -> None:
    with pytest.raises(ValidationError):
        StructureInputValidator().validate_or_raise([])
