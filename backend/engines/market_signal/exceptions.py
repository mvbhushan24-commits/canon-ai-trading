"""Market Signal Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class SignalEngineError(CanonTradingError):
    """Base exception for Market Signal Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MSE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class SignalValidationError(SignalEngineError):
    """Input or session validation failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_SIGNAL_VALIDATION_FAILED", details=details)


class SignalExpiredError(SignalEngineError):
    """Decision or signal past validity."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_SIGNAL_EXPIRED", details=details)


class LowConfidenceError(SignalEngineError):
    """Confidence or quality below threshold."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_LOW_CONFIDENCE", details=details)


class DuplicateSignalError(SignalEngineError):
    """Duplicate active signal detected."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_DUPLICATE_SIGNAL", details=details)


class InvalidDecisionError(SignalEngineError):
    """Decision not eligible for signal creation."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_INVALID_DECISION", details=details)


class InvalidRiskError(SignalEngineError):
    """Risk re-validation failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_INVALID_RISK", details=details)


class ConfigurationError(SignalEngineError):
    """Invalid configuration."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_CONFIG_INVALID", details=details)


class SignalNotFoundError(SignalEngineError):
    """Signal ID not found in registry."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MSE_SIGNAL_NOT_FOUND", details=details)
