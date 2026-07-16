"""Input validation for market structure analysis."""

from datetime import datetime

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure.exceptions import ValidationError


class ValidationResultModel:
    """Validation outcome for candle batches."""

    def __init__(
        self,
        *,
        is_valid: bool,
        errors: list[str] | None = None,
        duplicate_swing_indices: int = 0,
    ) -> None:
        self.is_valid = is_valid
        self.errors = errors or []
        self.duplicate_swing_indices = duplicate_swing_indices


class StructureInputValidator:
    """Validate normalized candles before structure analysis."""

    def validate_candles(self, candles: list[NormalizedCandle]) -> ValidationResultModel:
        """Validate candle sequence for structure analysis."""
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
            if candle.open > candle.high or candle.open < candle.low:
                errors.append(f"Invalid OHLC at index {index}: open outside range")
            if candle.close > candle.high or candle.close < candle.low:
                errors.append(f"Invalid OHLC at index {index}: close outside range")
            if candle.open_time_utc in seen_times:
                errors.append(f"Duplicate timestamp at index {index}")
            seen_times.add(candle.open_time_utc)

        sorted_candles = sorted(candles, key=lambda c: c.open_time_utc)
        for previous, current in zip(sorted_candles, sorted_candles[1:], strict=False):
            if current.open_time_utc <= previous.open_time_utc:
                errors.append("Broken timestamp order in candle sequence")
                break

        duplicate_count = len(candles) - len(seen_times)
        is_valid = not errors
        return ValidationResultModel(
            is_valid=is_valid,
            errors=errors,
            duplicate_swing_indices=duplicate_count,
        )

    def validate_or_raise(self, candles: list[NormalizedCandle]) -> None:
        """Validate candles and raise on failure."""
        result = self.validate_candles(candles)
        if not result.is_valid:
            raise ValidationError(
                "Candle validation failed",
                details={"errors": result.errors},
            )


# Alias for schema consistency in tests
ValidationResult = ValidationResultModel
