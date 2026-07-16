"""Application-wide exception types (foundation only)."""

from typing import Any


class CanonTradingError(Exception):
    """Base exception for Canon AI Trading."""

    def __init__(
        self, message: str, *, code: str = "CANON_ERROR", details: dict[str, Any] | None = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ConfigurationError(CanonTradingError):
    """Raised when required configuration is missing or invalid."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)
