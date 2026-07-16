"""Input validation for fair value gap analysis."""

from datetime import datetime

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.exceptions import (
    InvalidLiquidityStateError,
    InvalidOrderBlockStateError,
    InvalidStructureError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_order_block import OrderBlockState
from backend.engines.market_structure import MarketStructure


class ValidationResultModel:
    """Validation outcome for fair value gap inputs."""

    def __init__(
        self,
        *,
        is_valid: bool,
        errors: list[str] | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.errors = errors or []


class FairValueGapInputValidator:
    """Validate candles and upstream context before fair value gap analysis."""

    def validate_candles(self, candles: list[NormalizedCandle]) -> ValidationResultModel:
        """Validate normalized candle batch."""
        errors: list[str] = []

        if not candles:
            errors.append("Candle list is empty")
            return ValidationResultModel(is_valid=False, errors=errors)

        symbol = candles[0].symbol
        timeframe = candles[0].timeframe
        seen_times: set[datetime] = set()
        previous_time: datetime | None = None

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
            if previous_time is not None and candle.open_time_utc < previous_time:
                errors.append(f"Candles not chronological at index {index}")
            previous_time = candle.open_time_utc

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

    def validate_liquidity_state(
        self,
        liquidity_state: LiquidityState | None,
        *,
        bar_count: int,
    ) -> ValidationResultModel:
        """Validate liquidity state consistency when provided."""
        if liquidity_state is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if liquidity_state.bar_count < 0:
            errors.append("Liquidity state bar_count cannot be negative")
        if bar_count > 0 and liquidity_state.bar_count > bar_count:
            errors.append("Liquidity state bar_count exceeds candle batch size")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_order_block_state(
        self,
        order_block_state: OrderBlockState | None,
        *,
        bar_count: int,
    ) -> ValidationResultModel:
        """Validate order block state consistency when provided."""
        if order_block_state is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if order_block_state.bar_count < 0:
            errors.append("Order block state bar_count cannot be negative")
        if bar_count > 0 and order_block_state.bar_count > bar_count:
            errors.append("Order block state bar_count exceeds candle batch size")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_state(self, state: FairValueGapState | None) -> ValidationResultModel:
        """Validate prior state for duplicate gap identifiers."""
        if state is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if state.bar_count < 0:
            errors.append("State bar_count cannot be negative")

        seen: set[str] = set()
        for gap in state.active_gaps:
            if gap.gap_id in seen:
                errors.append(f"Duplicate gap id in state: {gap.gap_id}")
            seen.add(gap.gap_id)

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_or_raise(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_block_state: OrderBlockState | None = None,
        prior_state: FairValueGapState | None = None,
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
            bar_count = len(candles)

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

            liquidity_result = self.validate_liquidity_state(
                liquidity_state,
                bar_count=bar_count,
            )
            if not liquidity_result.is_valid:
                raise InvalidLiquidityStateError(
                    "Liquidity state validation failed",
                    details={"errors": liquidity_result.errors},
                )

            order_block_result = self.validate_order_block_state(
                order_block_state,
                bar_count=bar_count,
            )
            if not order_block_result.is_valid:
                raise InvalidOrderBlockStateError(
                    "Order block state validation failed",
                    details={"errors": order_block_result.errors},
                )

        state_result = self.validate_state(prior_state)
        if not state_result.is_valid:
            raise StateCorruptError(
                "Prior state validation failed",
                details={"errors": state_result.errors},
            )
