"""Input validation for order block analysis."""

from datetime import datetime

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.schemas import LiquidityAnalysis
from backend.engines.market_order_block.exceptions import (
    InvalidLiquidityError,
    InvalidStructureError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_order_block.schemas import OrderBlockState
from backend.engines.market_structure.schemas import MarketStructure


class ValidationResultModel:
    """Validation outcome for order block inputs."""

    def __init__(
        self,
        *,
        is_valid: bool,
        errors: list[str] | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.errors = errors or []


class OrderBlockInputValidator:
    """Validate candles and upstream context before order block analysis."""

    def validate_candles(self, candles: list[NormalizedCandle]) -> ValidationResultModel:
        """Validate normalized candle batch."""
        errors: list[str] = []

        if not candles:
            errors.append("Candle list is empty")
            return ValidationResultModel(is_valid=False, errors=errors)

        symbol = candles[0].symbol
        timeframe = candles[0].timeframe
        seen_times: set[datetime] = set()

        for index, candle in enumerate(candles):
            if candle.symbol != symbol:
                errors.append(f"Mixed symbols at index {index}")
            if candle.timeframe != timeframe:
                errors.append(f"Mixed timeframes at index {index}")
            if candle.high < candle.low:
                errors.append(f"Invalid OHLC at index {index}: high < low")
            if candle.high < max(candle.open, candle.close):
                errors.append(f"Invalid OHLC at index {index}: high below body")
            if candle.low > min(candle.open, candle.close):
                errors.append(f"Invalid OHLC at index {index}: low above body")
            if candle.open_time_utc in seen_times:
                errors.append(f"Duplicate timestamp at index {index}")
            seen_times.add(candle.open_time_utc)

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_structure(
        self,
        structure: MarketStructure | None,
        *,
        symbol: str,
        timeframe: str,
    ) -> ValidationResultModel:
        """Validate market structure context when provided."""
        if structure is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if structure.symbol != symbol:
            errors.append("Structure symbol mismatch")
        if structure.timeframe.upper() != timeframe.upper():
            errors.append("Structure timeframe mismatch")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_liquidity(
        self,
        liquidity: LiquidityAnalysis | None,
        *,
        symbol: str,
        timeframe: str,
    ) -> ValidationResultModel:
        """Validate liquidity context when provided."""
        if liquidity is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if liquidity.symbol != symbol:
            errors.append("Liquidity symbol mismatch")
        if liquidity.timeframe.upper() != timeframe.upper():
            errors.append("Liquidity timeframe mismatch")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_state(self, state: OrderBlockState | None) -> ValidationResultModel:
        """Validate prior state for duplicate block identifiers."""
        if state is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if state.bar_count < 0:
            errors.append("State bar_count cannot be negative")

        seen: set[str] = set()
        for block in state.active_blocks:
            if block.block_id in seen:
                errors.append(f"Duplicate block id in state: {block.block_id}")
            seen.add(block.block_id)

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_or_raise(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
        prior_state: OrderBlockState | None = None,
    ) -> None:
        """Validate inputs and raise on failure."""
        candle_result = self.validate_candles(candles)
        if not candle_result.is_valid:
            raise ValidationError(
                "Candle validation failed",
                details={"errors": candle_result.errors},
            )

        if candles:
            symbol = candles[0].symbol
            timeframe = candles[0].timeframe

            structure_result = self.validate_structure(
                structure,
                symbol=symbol,
                timeframe=timeframe,
            )
            if not structure_result.is_valid:
                raise InvalidStructureError(
                    "Structure validation failed",
                    details={"errors": structure_result.errors},
                )

            liquidity_result = self.validate_liquidity(
                liquidity,
                symbol=symbol,
                timeframe=timeframe,
            )
            if not liquidity_result.is_valid:
                raise InvalidLiquidityError(
                    "Liquidity validation failed",
                    details={"errors": liquidity_result.errors},
                )

        state_result = self.validate_state(prior_state)
        if not state_result.is_valid:
            raise StateCorruptError(
                "Prior state validation failed",
                details={"errors": state_result.errors},
            )
