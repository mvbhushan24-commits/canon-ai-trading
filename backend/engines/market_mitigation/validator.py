"""Input validation for mitigation block analysis."""

from datetime import datetime

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
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
from backend.engines.market_mitigation.schemas import MitigationBlock, MitigationBlockState
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_structure import MarketStructure


class ValidationResultModel:
    """Validation outcome for mitigation block inputs."""

    def __init__(
        self,
        *,
        is_valid: bool,
        errors: list[str] | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.errors = errors or []


class MitigationBlockInputValidator:
    """Validate candles and upstream context before mitigation block analysis."""

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
        """Validate order blocks from upstream."""
        if not order_blocks:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        for index, block in enumerate(order_blocks):
            if block.high < block.low:
                errors.append(f"Invalid order block bounds at index {index}")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_breaker_blocks(
        self,
        breaker_blocks: list[BreakerBlock] | None,
    ) -> ValidationResultModel:
        """Validate breaker blocks from upstream."""
        if not breaker_blocks:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        for index, breaker in enumerate(breaker_blocks):
            if breaker.high < breaker.low:
                errors.append(f"Invalid breaker bounds at index {index}: {breaker.breaker_id}")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_htf_blocks(
        self,
        htf_blocks: list[MitigationBlock] | None,
        *,
        timeframe: str,
    ) -> ValidationResultModel:
        """Validate higher-timeframe mitigation blocks when provided."""
        if not htf_blocks:
            return ValidationResultModel(is_valid=True)

        errors: list[str] = []
        for index, block in enumerate(htf_blocks):
            if block.high < block.low:
                errors.append(f"Invalid HTF block bounds at index {index}")
            if block.direction.value not in {"bullish", "bearish"}:
                errors.append(f"Invalid HTF block direction at index {index}")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_state(self, state: MitigationBlockState | None) -> ValidationResultModel:
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
        liquidity_state: LiquidityState | None = None,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        prior_state: MitigationBlockState | None = None,
        htf_mitigation_blocks: list[MitigationBlock] | None = None,
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
            bar_count = len([c for c in candles if c.is_closed]) or len(candles)

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

            fvg_result = self.validate_fvg_state(
                fair_value_gap_state,
                bar_count=bar_count,
            )
            if not fvg_result.is_valid:
                raise InvalidFVGStateError(
                    "Fair value gap state validation failed",
                    details={"errors": fvg_result.errors},
                )

            blocks_result = self.validate_order_blocks(
                order_blocks,
                symbol=symbol,
                timeframe=timeframe,
            )
            if not blocks_result.is_valid:
                raise InvalidOrderBlocksError(
                    "Order block validation failed",
                    details={"errors": blocks_result.errors},
                )

            breaker_result = self.validate_breaker_blocks(breaker_blocks)
            if not breaker_result.is_valid:
                raise InvalidBreakerBlocksError(
                    "Breaker block validation failed",
                    details={"errors": breaker_result.errors},
                )

            htf_result = self.validate_htf_blocks(
                htf_mitigation_blocks,
                timeframe=timeframe,
            )
            if not htf_result.is_valid:
                raise InvalidHTFBlocksError(
                    "HTF mitigation block validation failed",
                    details={"errors": htf_result.errors},
                )

        state_result = self.validate_state(prior_state)
        if not state_result.is_valid:
            raise StateCorruptError(
                "Prior state validation failed",
                details={"errors": state_result.errors},
            )
