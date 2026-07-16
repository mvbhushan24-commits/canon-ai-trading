"""Fair Value Gap Engine — institutional fair value gap detection and lifecycle.

Sprint 5.2: bullish/bearish FVG detection, fill/mitigation lifecycle, MTF alignment.
Consumes NormalizedCandle from Market Data Engine, MarketStructure from Market Structure
Engine, and optional LiquidityState and OrderBlockState from upstream engines.
"""

from backend.engines.market_fvg.config import (
    FairValueGapConfig,
    QualityWeights,
    load_fair_value_gap_config,
)
from backend.engines.market_fvg.detector import FairValueGapDetector
from backend.engines.market_fvg.engine import FairValueGapEngine
from backend.engines.market_fvg.events import FairValueGapAnalysisEvent
from backend.engines.market_fvg.exceptions import (
    DuplicateGapError,
    FairValueGapError,
    InsufficientDataError,
    InvalidLiquidityStateError,
    InvalidOrderBlockStateError,
    InvalidStructureError,
    StateCorruptError,
    UnsupportedTimeframeError,
    ValidationError,
)
from backend.engines.market_fvg.publisher import FairValueGapEventPublisher
from backend.engines.market_fvg.schemas import (
    FVGFormationCandidate,
    FairValueGap,
    FairValueGapAnalysis,
    FairValueGapBias,
    FairValueGapDirection,
    FairValueGapEvent,
    FairValueGapEventKind,
    FairValueGapQuality,
    FairValueGapState,
    FairValueGapStatus,
    MTFGapAlignment,
    PremiumDiscountZone,
)
from backend.engines.market_fvg.validator import FairValueGapInputValidator

__all__ = [
    "DuplicateGapError",
    "FVGFormationCandidate",
    "FairValueGap",
    "FairValueGapAnalysis",
    "FairValueGapAnalysisEvent",
    "FairValueGapBias",
    "FairValueGapConfig",
    "FairValueGapDetector",
    "FairValueGapDirection",
    "FairValueGapEngine",
    "FairValueGapError",
    "FairValueGapEvent",
    "FairValueGapEventKind",
    "FairValueGapEventPublisher",
    "FairValueGapInputValidator",
    "FairValueGapQuality",
    "FairValueGapState",
    "FairValueGapStatus",
    "InsufficientDataError",
    "InvalidLiquidityStateError",
    "InvalidOrderBlockStateError",
    "InvalidStructureError",
    "MTFGapAlignment",
    "PremiumDiscountZone",
    "QualityWeights",
    "StateCorruptError",
    "UnsupportedTimeframeError",
    "ValidationError",
    "load_fair_value_gap_config",
]
