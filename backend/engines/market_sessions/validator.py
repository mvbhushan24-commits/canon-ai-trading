"""Input validation for kill zones and session analysis."""

from datetime import UTC, datetime

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_mitigation.schemas import MitigationBlock
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_premium_discount.schemas import PremiumDiscountAnalysis
from backend.engines.market_sessions.config import MarketSessionsConfig, validate_config_timezones
from backend.engines.market_sessions.exceptions import (
    ConfigInvalidError,
    InsufficientDataError,
    InvalidLiquidityStateError,
    InvalidPremiumDiscountError,
    InvalidStructureError,
    InvalidTimestampError,
    InvalidTimezoneError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_sessions.schemas import MarketSessionsState
from backend.engines.market_sessions.timezone import validate_timezone
from backend.engines.market_structure import MarketStructure


class ValidationResultModel:
    """Validation outcome."""

    def __init__(
        self,
        *,
        is_valid: bool,
        errors: list[str] | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.errors = errors or []


class MarketSessionsInputValidator:
    """Validate candles and upstream context before session analysis."""

    def __init__(self, config: MarketSessionsConfig | None = None) -> None:
        self._config = config

    def validate_timestamp(self, timestamp_utc: datetime) -> ValidationResultModel:
        """Validate timezone-aware UTC timestamp."""
        errors: list[str] = []
        if timestamp_utc.tzinfo is None:
            errors.append("timestamp_utc must be timezone-aware")
        else:
            normalized = timestamp_utc.astimezone(UTC)
            offset = normalized.utcoffset()
            if offset is not None and offset.total_seconds() != 0:
                errors.append("timestamp_utc must be UTC")
        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_broker_timezone(self, broker_timezone: str) -> ValidationResultModel:
        """Validate IANA broker timezone."""
        errors: list[str] = []
        try:
            validate_timezone(broker_timezone)
        except InvalidTimezoneError as exc:
            errors.append(str(exc))
        return ValidationResultModel(is_valid=not errors, errors=errors)

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

    def validate_premium_discount(
        self,
        premium_discount: PremiumDiscountAnalysis | None,
        *,
        symbol: str,
        timeframe: str,
    ) -> ValidationResultModel:
        """Validate premium / discount context when provided."""
        if premium_discount is None:
            return ValidationResultModel(is_valid=True)
        errors: list[str] = []
        if premium_discount.symbol != symbol:
            errors.append("Premium/discount symbol mismatch")
        if premium_discount.timeframe.upper() != timeframe.upper():
            errors.append("Premium/discount timeframe mismatch")
        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_prior_state(
        self,
        prior_state: MarketSessionsState | None,
    ) -> ValidationResultModel:
        """Validate continuity state when provided."""
        if prior_state is None:
            return ValidationResultModel(is_valid=True)
        errors: list[str] = []
        if prior_state.bar_count < 0:
            errors.append("Prior state bar_count cannot be negative")
        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_configuration(self, config: MarketSessionsConfig) -> ValidationResultModel:
        """Validate session, kill zone, overlap, and calendar configuration."""
        errors: list[str] = []
        try:
            validate_config_timezones(config)
        except ConfigInvalidError as exc:
            errors.append(str(exc))

        if config.opening_range.duration_minutes <= 0:
            errors.append("opening_range.duration_minutes must be positive")
        if config.initial_balance.duration_minutes <= 0:
            errors.append("initial_balance.duration_minutes must be positive")

        holidays = config.calendar.holidays
        if holidays.enabled and holidays.file:
            from pathlib import Path

            if not Path(holidays.file).exists():
                errors.append(f"Holiday calendar file not found: {holidays.file}")

        for session_id, session_cfg in config.sessions.items():
            if not session_cfg.enabled:
                continue
            if session_cfg.local_start == session_cfg.local_end:
                errors.append(f"Invalid session window for {session_id}")

        for kz_id, kz_cfg in config.kill_zones.items():
            if not kz_cfg.enabled:
                continue
            if kz_cfg.utc_start == kz_cfg.utc_end:
                errors.append(f"Invalid kill zone window for {kz_id}")

        return ValidationResultModel(is_valid=not errors, errors=errors)

    def validate_or_raise_configuration(self, config: MarketSessionsConfig) -> None:
        """Validate configuration and raise on failure."""
        result = self.validate_configuration(config)
        if not result.is_valid:
            raise ConfigInvalidError(
                "; ".join(result.errors),
                details={"errors": result.errors},
            )

    def validate_or_raise(
        self,
        candles: list[NormalizedCandle],
        timestamp_utc: datetime,
        broker_timezone: str,
        *,
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
        prior_state: MarketSessionsState | None = None,
        timeframe: str | None = None,
        strict_candle_count: bool = True,
    ) -> None:
        """Run all validations and raise on failure."""
        candle_result = self.validate_candles(candles)
        if not candle_result.is_valid:
            raise ValidationError(
                "; ".join(candle_result.errors),
                details={"errors": candle_result.errors},
            )

        ts_result = self.validate_timestamp(timestamp_utc)
        if not ts_result.is_valid:
            raise InvalidTimestampError(
                "; ".join(ts_result.errors),
                details={"errors": ts_result.errors},
            )

        tz_result = self.validate_broker_timezone(broker_timezone)
        if not tz_result.is_valid:
            raise InvalidTimezoneError(
                "; ".join(tz_result.errors),
                details={"errors": tz_result.errors},
            )

        target_timeframe = (timeframe or candles[0].timeframe).upper()
        structure_result = self.validate_structure(
            structure,
            symbol=candles[0].symbol,
            timeframe=target_timeframe,
        )
        if not structure_result.is_valid:
            raise InvalidStructureError(
                "; ".join(structure_result.errors),
                details={"errors": structure_result.errors},
            )

        closed_count = sum(1 for c in candles if c.is_closed)
        liquidity_result = self.validate_liquidity_state(
            liquidity_state,
            bar_count=closed_count,
        )
        if not liquidity_result.is_valid:
            raise InvalidLiquidityStateError(
                "; ".join(liquidity_result.errors),
                details={"errors": liquidity_result.errors},
            )

        pd_result = self.validate_premium_discount(
            premium_discount,
            symbol=candles[0].symbol,
            timeframe=target_timeframe,
        )
        if not pd_result.is_valid:
            raise InvalidPremiumDiscountError(
                "; ".join(pd_result.errors),
                details={"errors": pd_result.errors},
            )

        state_result = self.validate_prior_state(prior_state)
        if not state_result.is_valid:
            raise StateCorruptError(
                "; ".join(state_result.errors),
                details={"errors": state_result.errors},
            )

        if self._config is not None:
            config_result = self.validate_configuration(self._config)
            if not config_result.is_valid and not self._config.allow_partial_analysis:
                raise ConfigInvalidError(
                    "; ".join(config_result.errors),
                    details={"errors": config_result.errors},
                )

        if strict_candle_count and self._config is not None:
            allow_partial = self._config.allow_partial_analysis
            min_candles = self._config.min_candles
            if closed_count < min_candles and not allow_partial:
                raise InsufficientDataError(
                    f"Need at least {min_candles} closed candles",
                    details={"received": closed_count},
                )
