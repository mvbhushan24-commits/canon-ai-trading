"""Order Block Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class OrderBlockError(CanonTradingError):
    """Base exception for Order Block Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "OBE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class InsufficientDataError(OrderBlockError):
    """Not enough candles for order block analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="OBE_INSUFFICIENT_DATA", details=details)


class ValidationError(OrderBlockError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="OBE_VALIDATION_FAILED", details=details)


class InvalidStructureError(OrderBlockError):
    """Invalid or mismatched market structure context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="OBE_INVALID_STRUCTURE", details=details)


class InvalidLiquidityError(OrderBlockError):
    """Invalid or mismatched liquidity context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="OBE_INVALID_LIQUIDITY", details=details)


class UnsupportedTimeframeError(OrderBlockError):
    """Timeframe not configured for order block analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="OBE_TIMEFRAME_UNSUPPORTED", details=details)


class DuplicateBlockError(OrderBlockError):
    """Duplicate order block identifier in state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="OBE_DUPLICATE_BLOCK", details=details)


class StateCorruptError(OrderBlockError):
    """Prior state is unusable."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="OBE_STATE_CORRUPT", details=details)
