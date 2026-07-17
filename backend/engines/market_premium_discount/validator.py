"""Input validation for premium / discount analysis."""

from datetime import datetime
from decimal import Decimal

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_mitigation.schemas import MitigationBlock
from backend.engines.market_order_block import OrderBlock
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
from backend.engines.market_premium_discount.schemas import (
    PremiumDiscountContext,
    PremiumDiscountState,
)
from backend.engines.market_structure import MarketStructure


class ValidationResultModel:
    """Validation outcome for premium / discount inputs."""

    def __init__(
        self,
        *,
        is_valid: bool,
        errors: list[str] | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.errors = errors or []


class PremiumDiscountInputValidator:
    """Validate candles and upstream context before premium / discount analysis."""

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

    def validate_fvg_state(
        self,
        fair_value_gap_state: FairValueGapState | None,
        *,
        bar_count: int,
    ) -> ValidationResultModel:
        """Validate fair value gap state consistency when provided."""
        if fair_value_gap_state is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if fair_value_gap_state.bar_count < 0:
            errors.append("FVG state bar_count cannot be negative")
        if bar_count > 0 and fair_value_gap_state.bar_count > bar_count:
            errors.append("FVG state bar_count exceeds candle batch size")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_order_blocks(
        self,
        order_blocks: list[OrderBlock] | None,
        *,
        symbol: str,
        timeframe: str,
    ) -> ValidationResultModel:
        """Validate order block scope when provided."""
        if not order_blocks:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        for index, block in enumerate(order_blocks):
            if block.high < block.low:
                errors.append(f"Invalid order block bounds at index {index}")
            if block.strength < Decimal("0") or block.strength > Decimal("1"):
                errors.append(f"Invalid order block strength at index {index}")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_breaker_blocks(
        self,
        breaker_blocks: list[BreakerBlock] | None,
        *,
        symbol: str,
        timeframe: str,
    ) -> ValidationResultModel:
        """Validate breaker block scope when provided."""
        if not breaker_blocks:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        for index, block in enumerate(breaker_blocks):
            if block.high < block.low:
                errors.append(f"Invalid breaker block bounds at index {index}")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_mitigation_blocks(
        self,
        mitigation_blocks: list[MitigationBlock] | None,
        *,
        symbol: str,
        timeframe: str,
    ) -> ValidationResultModel:
        """Validate mitigation block scope when provided."""
        if not mitigation_blocks:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        for index, block in enumerate(mitigation_blocks):
            if block.high < block.low:
                errors.append(f"Invalid mitigation block bounds at index {index}")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_htf_context(
        self,
        htf_context: PremiumDiscountContext | None,
    ) -> ValidationResultModel:
        """Validate HTF premium / discount context when provided."""
        if htf_context is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if not htf_context.timeframe.strip():
            errors.append("HTF context timeframe is empty")
        if not htf_context.dealing_range.is_valid:
            errors.append("HTF dealing range is invalid")
        if htf_context.dealing_range.high <= htf_context.dealing_range.low:
            errors.append("HTF dealing range bounds are invalid")
        if htf_context.equilibrium <= Decimal("0"):
            errors.append("HTF equilibrium must be positive")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_prior_state(
        self,
        prior_state: PremiumDiscountState | None,
    ) -> ValidationResultModel:
        """Validate prior continuity state when provided."""
        if prior_state is None:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        if prior_state.bar_count < 0:
            errors.append("Prior state bar_count cannot be negative")

        for label, active_range in (
            ("active_dealing_range", prior_state.active_dealing_range),
            ("active_external_range", prior_state.active_external_range),
            ("active_internal_range", prior_state.active_internal_range),
        ):
            if active_range is None:
                continue
            if active_range.high <= active_range.low:
                errors.append(f"{label} has invalid bounds in prior state")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_or_raise(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
        liquidity_state: LiquidityState | None,
        order_blocks: list[OrderBlock] | None,
        fair_value_gap_state: FairValueGapState | None,
        breaker_blocks: list[BreakerBlock] | None,
        mitigation_blocks: list[MitigationBlock] | None,
        prior_state: PremiumDiscountState | None,
        htf_context: PremiumDiscountContext | None,
    ) -> None:
        """Run all validations and raise on first failure category."""
        candle_result = self.validate_candles(candles)
        if not candle_result.is_valid:
            raise ValidationError(
                "; ".join(candle_result.errors),
                details={"errors": candle_result.errors},
            )

        symbol = candles[0].symbol
        timeframe = candles[0].timeframe.upper()
        bar_count = len(candles)

        checks = [
            (
                self.validate_structure(structure, symbol=symbol, timeframe=timeframe),
                InvalidStructureError,
            ),
            (
                self.validate_liquidity_state(liquidity_state, bar_count=bar_count),
                InvalidLiquidityStateError,
            ),
            (
                self.validate_fvg_state(fair_value_gap_state, bar_count=bar_count),
                InvalidFVGStateError,
            ),
            (
                self.validate_order_blocks(
                    order_blocks,
                    symbol=symbol,
                    timeframe=timeframe,
                ),
                InvalidOrderBlocksError,
            ),
            (
                self.validate_breaker_blocks(
                    breaker_blocks,
                    symbol=symbol,
                    timeframe=timeframe,
                ),
                InvalidBreakerBlocksError,
            ),
            (
                self.validate_mitigation_blocks(
                    mitigation_blocks,
                    symbol=symbol,
                    timeframe=timeframe,
                ),
                InvalidMitigationBlocksError,
            ),
            (self.validate_prior_state(prior_state), StateCorruptError),
            (self.validate_htf_context(htf_context), InvalidHTFContextError),
        ]

        for result, error_type in checks:
            if not result.is_valid:
                raise error_type(
                    "; ".join(result.errors),
                    details={"errors": result.errors},
                )
