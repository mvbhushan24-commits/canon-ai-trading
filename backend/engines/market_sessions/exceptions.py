"""Kill Zones & Trading Sessions Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class MarketSessionsError(CanonTradingError):
    """Base exception for Kill Zones & Sessions Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MS_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class InsufficientDataError(MarketSessionsError):
    """Not enough candles for requested session features."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_INSUFFICIENT_DATA", details=details)


class ValidationError(MarketSessionsError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_VALIDATION_FAILED", details=details)


class InvalidTimestampError(MarketSessionsError):
    """Invalid or naive timestamp."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_INVALID_TIMESTAMP", details=details)


class InvalidTimezoneError(MarketSessionsError):
    """Unrecognized IANA timezone."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_INVALID_TIMEZONE", details=details)


class UnsupportedTimeframeError(MarketSessionsError):
    """Timeframe not configured for session analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_TIMEFRAME_UNSUPPORTED", details=details)


class InvalidStructureError(MarketSessionsError):
    """Invalid or mismatched market structure context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_INVALID_STRUCTURE", details=details)


class InvalidLiquidityStateError(MarketSessionsError):
    """Invalid or inconsistent liquidity state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_INVALID_LIQUIDITY_STATE", details=details)


class InvalidPremiumDiscountError(MarketSessionsError):
    """Invalid premium / discount context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_INVALID_PREMIUM_DISCOUNT", details=details)


class ConfigInvalidError(MarketSessionsError):
    """Session configuration is invalid."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_CONFIG_INVALID", details=details)


class StateCorruptError(MarketSessionsError):
    """Prior continuity state is unusable."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MS_STATE_CORRUPT", details=details)
