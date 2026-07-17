"""Market Decision Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class DecisionEngineError(CanonTradingError):
    """Base exception for Market Decision Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MDE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class DecisionValidationError(DecisionEngineError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_DECISION_VALIDATION_FAILED", details=details)


class InsufficientEvidenceError(DecisionEngineError):
    """Below minimum required evidence engines."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INSUFFICIENT_EVIDENCE", details=details)


class ConflictingEvidenceError(DecisionEngineError):
    """Evidence conflict exceeds threshold."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_CONFLICTING_EVIDENCE", details=details)


class LowConfidenceError(DecisionEngineError):
    """Confidence below minimum threshold."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_LOW_CONFIDENCE", details=details)


class InvalidSessionError(DecisionEngineError):
    """Session gate failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_SESSION", details=details)


class InvalidStructureError(DecisionEngineError):
    """Structure gate failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_STRUCTURE", details=details)


class InvalidLiquidityError(DecisionEngineError):
    """Liquidity gate failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_LIQUIDITY", details=details)


class InvalidOrderBlockError(DecisionEngineError):
    """Order block zone gate failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_ORDER_BLOCK", details=details)


class InvalidFVGError(DecisionEngineError):
    """Fair value gap zone gate failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_FVG", details=details)


class InvalidBreakerError(DecisionEngineError):
    """Breaker block zone gate failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_BREAKER", details=details)


class InvalidMitigationError(DecisionEngineError):
    """Mitigation block zone gate failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_MITIGATION", details=details)


class InvalidPremiumDiscountError(DecisionEngineError):
    """Premium/discount gate failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_PREMIUM_DISCOUNT", details=details)


class InvalidRiskError(DecisionEngineError):
    """Risk rule failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_RISK", details=details)


class ConfigurationError(DecisionEngineError):
    """Invalid configuration."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_CONFIG_INVALID", details=details)
