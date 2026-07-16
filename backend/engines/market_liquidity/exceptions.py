"""Market Liquidity Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class MarketLiquidityError(CanonTradingError):
    """Base exception for Market Liquidity Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "LQE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class InsufficientDataError(MarketLiquidityError):
    """Not enough candles for liquidity analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="LQE_INSUFFICIENT_DATA", details=details)


class InvalidStructureError(MarketLiquidityError):
    """Invalid or missing market structure context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="LQE_INVALID_STRUCTURE", details=details)


class UnsupportedTimeframeError(MarketLiquidityError):
    """Timeframe not configured for liquidity analysis."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="LQE_TIMEFRAME_UNSUPPORTED", details=details)


class ValidationError(MarketLiquidityError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="LQE_VALIDATION_FAILED", details=details)


class DuplicateZoneError(MarketLiquidityError):
    """Duplicate liquidity zone detected."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="LQE_DUPLICATE_ZONE", details=details)
