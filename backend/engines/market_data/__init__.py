"""Market Data Engine for XMGlobal via MetaTrader 5.

Sprint 1: production Market Data Engine implementation.
"""

from backend.engines.market_data.config import MarketDataConfig, load_market_data_config
from backend.engines.market_data.engine import MarketDataEngine
from backend.engines.market_data.events import EventPublisher, MarketEvent
from backend.engines.market_data.exceptions import (
    GapDetectedError,
    HistoryLoadError,
    InvalidTimeframeError,
    MarketDataError,
    MT5AuthenticationError,
    MT5ConnectionError,
    StaleFeedError,
    SymbolUnavailableError,
)
from backend.engines.market_data.schemas import (
    EngineConnectionStatus,
    EngineStatus,
    GapInfo,
    HistoryRequest,
    HistoryResponse,
    NormalizedCandle,
    NormalizedTick,
    SymbolMetadata,
    ValidationResult,
)
from backend.engines.market_data.timeframes import (
    SUPPORTED_TIMEFRAMES,
    Timeframe,
    validate_timeframe,
)

__all__ = [
    "EngineConnectionStatus",
    "EngineStatus",
    "EventPublisher",
    "GapDetectedError",
    "GapInfo",
    "HistoryLoadError",
    "HistoryRequest",
    "HistoryResponse",
    "InvalidTimeframeError",
    "MarketDataConfig",
    "MarketDataEngine",
    "MarketDataError",
    "MarketEvent",
    "MT5AuthenticationError",
    "MT5ConnectionError",
    "NormalizedCandle",
    "NormalizedTick",
    "StaleFeedError",
    "SymbolMetadata",
    "SymbolUnavailableError",
    "SUPPORTED_TIMEFRAMES",
    "Timeframe",
    "ValidationResult",
    "load_market_data_config",
    "validate_timeframe",
]
