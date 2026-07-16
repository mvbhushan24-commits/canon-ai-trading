"""Breaker Block Engine — institutional breaker block detection and lifecycle.

Sprint 6.2: bullish/bearish breaker blocks, confirmation, mitigation, invalidation.
Consumes NormalizedCandle from Market Data Engine, MarketStructure from Market Structure
Engine, invalidated OrderBlock from Order Block Engine, and optional LiquidityState and
FairValueGapState from upstream engines.
"""

from backend.engines.market_breaker.config import (
    BreakerBlockConfig,
    QualityWeights,
    load_market_breaker_config,
)
from backend.engines.market_breaker.engine import BreakerBlockEngine
from backend.engines.market_breaker.events import BreakerBlockAnalysisEvent
from backend.engines.market_breaker.exceptions import (
    BreakerBlockError,
    DuplicateBreakerError,
    InsufficientDataError,
    InvalidFVGStateError,
    InvalidLiquidityStateError,
    InvalidOrderBlocksError,
    InvalidStructureError,
    StateCorruptError,
    UnsupportedTimeframeError,
    ValidationError,
)
from backend.engines.market_breaker.publisher import BreakerBlockEventPublisher
from backend.engines.market_breaker.schemas import (
    BreakerBlock,
    BreakerBlockAnalysis,
    BreakerBlockBias,
    BreakerBlockDirection,
    BreakerBlockEvent,
    BreakerBlockEventKind,
    BreakerBlockQuality,
    BreakerBlockState,
    BreakerBlockStatus,
    BreakerCandidate,
    BreakerSourceType,
)

__all__ = [
    "BreakerBlock",
    "BreakerBlockAnalysis",
    "BreakerBlockAnalysisEvent",
    "BreakerBlockBias",
    "BreakerBlockConfig",
    "BreakerBlockDirection",
    "BreakerBlockEngine",
    "BreakerBlockError",
    "BreakerBlockEvent",
    "BreakerBlockEventKind",
    "BreakerBlockEventPublisher",
    "BreakerBlockQuality",
    "BreakerBlockState",
    "BreakerBlockStatus",
    "BreakerCandidate",
    "BreakerSourceType",
    "DuplicateBreakerError",
    "InsufficientDataError",
    "InvalidFVGStateError",
    "InvalidLiquidityStateError",
    "InvalidOrderBlocksError",
    "InvalidStructureError",
    "QualityWeights",
    "StateCorruptError",
    "UnsupportedTimeframeError",
    "ValidationError",
    "load_market_breaker_config",
]
