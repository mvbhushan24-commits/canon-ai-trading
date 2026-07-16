"""Breaker Block Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class BreakerBlockError(CanonTradingError):
    """Base exception for Breaker Block Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MBE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class InsufficientDataError(BreakerBlockError):
    """Not enough candles for breaker block analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_INSUFFICIENT_DATA", details=details)


class ValidationError(BreakerBlockError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_VALIDATION_FAILED", details=details)


class InvalidStructureError(BreakerBlockError):
    """Invalid or mismatched market structure context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_INVALID_STRUCTURE", details=details)


class InvalidLiquidityStateError(BreakerBlockError):
    """Invalid or inconsistent liquidity state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_INVALID_LIQUIDITY_STATE", details=details)


class InvalidOrderBlocksError(BreakerBlockError):
    """Invalid or non-invalidated order blocks."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_INVALID_ORDER_BLOCKS", details=details)


class InvalidFVGStateError(BreakerBlockError):
    """Invalid or inconsistent fair value gap state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_INVALID_FVG_STATE", details=details)


class UnsupportedTimeframeError(BreakerBlockError):
    """Timeframe not configured for breaker block analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_TIMEFRAME_UNSUPPORTED", details=details)


class DuplicateBreakerError(BreakerBlockError):
    """Duplicate breaker identifier in state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_DUPLICATE_BREAKER", details=details)


class StateCorruptError(BreakerBlockError):
    """Prior state is unusable."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MBE_STATE_CORRUPT", details=details)
