"""Fair Value Gap Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class FairValueGapError(CanonTradingError):
    """Base exception for Fair Value Gap Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "FVE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class InsufficientDataError(FairValueGapError):
    """Not enough candles for fair value gap analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="FVE_INSUFFICIENT_DATA", details=details)


class ValidationError(FairValueGapError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="FVE_VALIDATION_FAILED", details=details)


class InvalidStructureError(FairValueGapError):
    """Invalid or mismatched market structure context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="FVE_INVALID_STRUCTURE", details=details)


class InvalidLiquidityStateError(FairValueGapError):
    """Invalid or inconsistent liquidity state context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="FVE_INVALID_LIQUIDITY_STATE", details=details)


class InvalidOrderBlockStateError(FairValueGapError):
    """Invalid or inconsistent order block state context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="FVE_INVALID_ORDER_BLOCK_STATE", details=details)


class UnsupportedTimeframeError(FairValueGapError):
    """Timeframe not configured for fair value gap analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="FVE_TIMEFRAME_UNSUPPORTED", details=details)


class DuplicateGapError(FairValueGapError):
    """Duplicate fair value gap identifier in state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="FVE_DUPLICATE_GAP", details=details)


class StateCorruptError(FairValueGapError):
    """Prior state is unusable."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="FVE_STATE_CORRUPT", details=details)
