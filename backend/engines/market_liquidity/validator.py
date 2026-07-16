"""Input validation for liquidity analysis."""

from datetime import datetime

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.exceptions import ValidationError
from backend.engines.market_structure.schemas import MarketStructure


class ValidationResultModel:
    """Validation outcome for liquidity inputs."""

    def __init__(
        self,
        *,
        is_valid: bool,
        errors: list[str] | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.errors = errors or []


class LiquidityInputValidator:
    """Validate candles and structure context before liquidity analysis."""

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
        if not structure.swing_highs and not structure.swing_lows:
            errors.append("Structure contains no swing points")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_zones(self, zone_ids: list[str]) -> ValidationResultModel:
        """Reject duplicate zone identifiers."""
        seen: set[str] = set()
        errors: list[str] = []
        for zone_id in zone_ids:
            if zone_id in seen:
                errors.append(f"Duplicate zone id: {zone_id}")
            seen.add(zone_id)
        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_or_raise(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
    ) -> None:
        """Validate inputs and raise on failure."""
        candle_result = self.validate_candles(candles)
        if not candle_result.is_valid:
            raise ValidationError(
                "Candle validation failed",
                details={"errors": candle_result.errors},
            )

        if candles:
            structure_result = self.validate_structure(
                structure,
                symbol=candles[0].symbol,
                timeframe=candles[0].timeframe,
            )
            if not structure_result.is_valid:
                raise ValidationError(
                    "Structure validation failed",
                    details={"errors": structure_result.errors},
                )
