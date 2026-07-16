"""Market Structure Engine — Smart Money Concepts structure analysis.

Sprint 2: swing detection, BOS, CHoCH, trend classification.
Consumes NormalizedCandle from Market Data Engine only.
"""

from backend.engines.market_structure.config import (
    MarketStructureConfig,
    load_market_structure_config,
)
from backend.engines.market_structure.engine import MarketStructureEngine
from backend.engines.market_structure.events import StructureAnalysisEvent
from backend.engines.market_structure.exceptions import (
    InsufficientDataError,
    InvalidCandleError,
    MarketStructureError,
    StateCorruptError,
    UnsupportedTimeframeError,
    ValidationError,
)
from backend.engines.market_structure.publisher import StructureEventPublisher
from backend.engines.market_structure.schemas import (
    BOSDirection,
    BOSEvent,
    CHoCHDirection,
    CHoCHEvent,
    MarketStructure,
    StructureEvent,
    StructureEventKind,
    StructureState,
    SwingKind,
    SwingLabel,
    SwingPoint,
    TrendDirection,
)

__all__ = [
    "BOSDirection",
    "BOSEvent",
    "CHoCHDirection",
    "CHoCHEvent",
    "InsufficientDataError",
    "InvalidCandleError",
    "MarketStructure",
    "MarketStructureConfig",
    "MarketStructureEngine",
    "MarketStructureError",
    "StateCorruptError",
    "StructureAnalysisEvent",
    "StructureEvent",
    "StructureEventKind",
    "StructureEventPublisher",
    "StructureState",
    "SwingKind",
    "SwingLabel",
    "SwingPoint",
    "TrendDirection",
    "UnsupportedTimeframeError",
    "ValidationError",
    "load_market_structure_config",
]
