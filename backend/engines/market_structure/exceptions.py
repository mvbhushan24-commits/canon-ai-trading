"""Market Structure Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class MarketStructureError(CanonTradingError):
    """Base exception for Market Structure Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MSE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class InsufficientDataError(MarketStructureError):
    """Not enough candles for analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_INSUFFICIENT_DATA", details=details)


class InvalidCandleError(MarketStructureError):
    """Malformed or invalid candle input."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_INVALID_CANDLE", details=details)


class StateCorruptError(MarketStructureError):
    """Prior state cannot be used."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_STATE_CORRUPT", details=details)


class UnsupportedTimeframeError(MarketStructureError):
    """Timeframe not configured for analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_TIMEFRAME_UNSUPPORTED", details=details)


class ValidationError(MarketStructureError):
    """Input candle validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_VALIDATION_FAILED", details=details)
