"""Market Data Engine exceptions."""

from typing import Any

from backend.core.exceptions import CanonTradingError


class MarketDataError(CanonTradingError):
    """Base exception for Market Data Engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MDE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class MT5ConnectionError(MarketDataError):
    """MT5 initialization or terminal connection failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_CONN_FAILED", details=details)


class MT5AuthenticationError(MarketDataError):
    """MT5 login credentials are invalid."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_AUTH_FAILED", details=details)


class SymbolUnavailableError(MarketDataError):
    """Requested symbol is not available in MT5."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_SYMBOL_UNAVAILABLE", details=details)


class StaleFeedError(MarketDataError):
    """Market data feed has exceeded the stale threshold."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_STALE_FEED", details=details)


class GapDetectedError(MarketDataError):
    """Missing bars detected in candle sequence."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_GAP_DETECTED", details=details)


class HistoryLoadError(MarketDataError):
    """Historical data request failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_HISTORY_FAILED", details=details)


class InvalidTimeframeError(MarketDataError):
    """Unsupported or invalid timeframe."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="MDE_INVALID_TIMEFRAME", details=details)
