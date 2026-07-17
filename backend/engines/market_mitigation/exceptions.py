"""Mitigation Block Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class MitigationBlockError(CanonTradingError):
    """Base exception for Mitigation Block Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MMBE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class InsufficientDataError(MitigationBlockError):
    """Not enough candles for mitigation block analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_INSUFFICIENT_DATA", details=details)


class ValidationError(MitigationBlockError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_VALIDATION_FAILED", details=details)


class InvalidStructureError(MitigationBlockError):
    """Invalid or mismatched market structure context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_INVALID_STRUCTURE", details=details)


class InvalidLiquidityStateError(MitigationBlockError):
    """Invalid or inconsistent liquidity state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_INVALID_LIQUIDITY_STATE", details=details)


class InvalidOrderBlocksError(MitigationBlockError):
    """Invalid or mismatched order blocks."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_INVALID_ORDER_BLOCKS", details=details)


class InvalidFVGStateError(MitigationBlockError):
    """Invalid or inconsistent fair value gap state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_INVALID_FVG_STATE", details=details)


class InvalidBreakerBlocksError(MitigationBlockError):
    """Invalid or mismatched breaker blocks."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_INVALID_BREAKER_BLOCKS", details=details)


class InvalidHTFBlocksError(MitigationBlockError):
    """Invalid higher-timeframe mitigation block input."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_INVALID_HTF_BLOCKS", details=details)


class UnsupportedTimeframeError(MitigationBlockError):
    """Timeframe not configured for mitigation block analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_TIMEFRAME_UNSUPPORTED", details=details)


class DuplicateBlockError(MitigationBlockError):
    """Duplicate block identifier in state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_DUPLICATE_BLOCK", details=details)


class StateCorruptError(MitigationBlockError):
    """Prior state is unusable."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MMBE_STATE_CORRUPT", details=details)
