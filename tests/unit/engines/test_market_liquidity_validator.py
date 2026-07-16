"""Unit tests for liquidity input validator."""

import pytest

from backend.engines.market_liquidity.exceptions import ValidationError
from backend.engines.market_liquidity.validator import LiquidityInputValidator
from tests.unit.engines.liquidity_conftest import build_sample_structure


def test_validate_candles_success(liquidity_candles) -> None:
    validator = LiquidityInputValidator()
    result = validator.validate_candles(liquidity_candles)
    assert result.is_valid


def test_validate_structure_mismatch(liquidity_candles) -> None:
    validator = LiquidityInputValidator()
    structure = build_sample_structure()
    result = validator.validate_structure(structure, symbol="OTHER", timeframe="H1")
    assert not result.is_valid


def test_validate_duplicate_zones() -> None:
    validator = LiquidityInputValidator()
    result = validator.validate_zones(["zone-1", "zone-1"])
    assert not result.is_valid


def test_validate_or_raise_structure(liquidity_candles) -> None:
    validator = LiquidityInputValidator()
    structure = build_sample_structure()
    structure = structure.model_copy(update={"symbol": "WRONG"})
    with pytest.raises(ValidationError):
        validator.validate_or_raise(liquidity_candles, structure)
