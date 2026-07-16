"""Order Block Engine — institutional order block detection and lifecycle.

Sprint 4.2: bullish/bearish order blocks, fresh/mitigated/invalidated lifecycle.
Consumes NormalizedCandle from Market Data Engine, MarketStructure from
Market Structure Engine, and optional LiquidityAnalysis from Market Liquidity Engine.
"""

from backend.engines.market_order_block.config import (
    OrderBlockConfig,
    QualityWeights,
    load_order_block_config,
)
from backend.engines.market_order_block.engine import OrderBlockEngine
from backend.engines.market_order_block.events import OrderBlockAnalysisEvent
from backend.engines.market_order_block.exceptions import (
    DuplicateBlockError,
    InsufficientDataError,
    InvalidLiquidityError,
    InvalidStructureError,
    OrderBlockError,
    StateCorruptError,
    UnsupportedTimeframeError,
    ValidationError,
)
from backend.engines.market_order_block.publisher import OrderBlockEventPublisher
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockAnalysis,
    OrderBlockBias,
    OrderBlockDirection,
    OrderBlockEvent,
    OrderBlockEventKind,
    OrderBlockQuality,
    OrderBlockState,
    OrderBlockStatus,
    OriginCandidate,
)

__all__ = [
    "DuplicateBlockError",
    "InsufficientDataError",
    "InvalidLiquidityError",
    "InvalidStructureError",
    "OrderBlock",
    "OrderBlockAnalysis",
    "OrderBlockAnalysisEvent",
    "OrderBlockBias",
    "OrderBlockConfig",
    "OrderBlockDirection",
    "OrderBlockEngine",
    "OrderBlockEvent",
    "OrderBlockEventKind",
    "OrderBlockEventPublisher",
    "OrderBlockError",
    "OrderBlockQuality",
    "OrderBlockState",
    "OrderBlockStatus",
    "OriginCandidate",
    "QualityWeights",
    "StateCorruptError",
    "UnsupportedTimeframeError",
    "ValidationError",
    "load_order_block_config",
]
