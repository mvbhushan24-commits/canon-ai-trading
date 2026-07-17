"""Mitigation Block Engine — institutional mitigation block detection and lifecycle.

Sprint 7.2: bullish/bearish mitigation blocks, partial/full mitigation, multi-touch,
nested/internal/external scope, HTF/LTF alignment, confirmation, and invalidation.
Consumes NormalizedCandle from Market Data Engine, MarketStructure from Market Structure
Engine, OrderBlock from Order Block Engine, and optional LiquidityState, FairValueGapState,
and BreakerBlock from upstream engines.
"""

from backend.engines.market_mitigation.config import (
    MitigationBlockConfig,
    QualityWeights,
    load_market_mitigation_config,
)
from backend.engines.market_mitigation.engine import MitigationBlockEngine
from backend.engines.market_mitigation.events import MitigationBlockAnalysisEvent
from backend.engines.market_mitigation.exceptions import (
    DuplicateBlockError,
    InsufficientDataError,
    InvalidBreakerBlocksError,
    InvalidFVGStateError,
    InvalidHTFBlocksError,
    InvalidLiquidityStateError,
    InvalidOrderBlocksError,
    InvalidStructureError,
    MitigationBlockError,
    StateCorruptError,
    UnsupportedTimeframeError,
    ValidationError,
)
from backend.engines.market_mitigation.publisher import MitigationBlockEventPublisher
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockAnalysis,
    MitigationBlockBias,
    MitigationBlockDirection,
    MitigationBlockEvent,
    MitigationBlockEventKind,
    MitigationBlockQuality,
    MitigationBlockState,
    MitigationBlockStatus,
    MitigationCandidate,
    MitigationSourceType,
    MitigationTouch,
    MTFMitigationAlignment,
    StructureScope,
)

__all__ = [
    "DuplicateBlockError",
    "InsufficientDataError",
    "InvalidBreakerBlocksError",
    "InvalidFVGStateError",
    "InvalidHTFBlocksError",
    "InvalidLiquidityStateError",
    "InvalidOrderBlocksError",
    "InvalidStructureError",
    "MTFMitigationAlignment",
    "MitigationBlock",
    "MitigationBlockAnalysis",
    "MitigationBlockAnalysisEvent",
    "MitigationBlockBias",
    "MitigationBlockConfig",
    "MitigationBlockDirection",
    "MitigationBlockEngine",
    "MitigationBlockError",
    "MitigationBlockEvent",
    "MitigationBlockEventKind",
    "MitigationBlockEventPublisher",
    "MitigationBlockQuality",
    "MitigationBlockState",
    "MitigationBlockStatus",
    "MitigationCandidate",
    "MitigationSourceType",
    "MitigationTouch",
    "QualityWeights",
    "StateCorruptError",
    "StructureScope",
    "UnsupportedTimeframeError",
    "ValidationError",
    "load_market_mitigation_config",
]
