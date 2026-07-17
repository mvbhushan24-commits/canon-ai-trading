"""Premium / Discount Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class PremiumDiscountError(CanonTradingError):
    """Base exception for Premium / Discount Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "PD_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class InsufficientDataError(PremiumDiscountError):
    """Not enough candles for premium / discount analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_INSUFFICIENT_DATA", details=details)


class ValidationError(PremiumDiscountError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_VALIDATION_FAILED", details=details)


class InvalidStructureError(PremiumDiscountError):
    """Invalid or mismatched market structure context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_INVALID_STRUCTURE", details=details)


class InvalidLiquidityStateError(PremiumDiscountError):
    """Invalid or inconsistent liquidity state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_INVALID_LIQUIDITY_STATE", details=details)


class InvalidOrderBlocksError(PremiumDiscountError):
    """Invalid or mismatched order blocks."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_INVALID_ORDER_BLOCKS", details=details)


class InvalidFVGStateError(PremiumDiscountError):
    """Invalid or inconsistent fair value gap state."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_INVALID_FVG_STATE", details=details)


class InvalidBreakerBlocksError(PremiumDiscountError):
    """Invalid or mismatched breaker blocks."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_INVALID_BREAKER_BLOCKS", details=details)


class InvalidMitigationBlocksError(PremiumDiscountError):
    """Invalid or mismatched mitigation blocks."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_INVALID_MITIGATION_BLOCKS", details=details)


class InvalidHTFContextError(PremiumDiscountError):
    """Invalid higher-timeframe premium / discount context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_INVALID_HTF_CONTEXT", details=details)


class UnsupportedTimeframeError(PremiumDiscountError):
    """Timeframe not configured for premium / discount analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_TIMEFRAME_UNSUPPORTED", details=details)


class DealingRangeInvalidError(PremiumDiscountError):
    """Dealing range construction failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_DEALING_RANGE_INVALID", details=details)


class StateCorruptError(PremiumDiscountError):
    """Prior state is unusable."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PD_STATE_CORRUPT", details=details)
