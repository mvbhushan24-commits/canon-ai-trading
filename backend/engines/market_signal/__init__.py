"""Market Signal Engine — institutional trading signal conversion.

Sprint 11.2: consumes validated TradeDecision outputs from the Decision Engine
and converts qualified BUY/SELL decisions into lifecycle-managed trading signals.
"""

from backend.engines.market_decision import EvidenceSummaryItem, QualityTier, RiskSummary
from backend.engines.market_signal.config import (
    MarketSignalConfig,
    load_market_signal_config,
)
from backend.engines.market_signal.detector import DuplicateDetector
from backend.engines.market_signal.engine import MarketSignalEngine
from backend.engines.market_signal.events import ENGINE_ID, SignalAnalysisEvent
from backend.engines.market_signal.exceptions import (
    ConfigurationError,
    DuplicateSignalError,
    InvalidDecisionError,
    InvalidRiskError,
    LowConfidenceError,
    SignalEngineError,
    SignalExpiredError,
    SignalNotFoundError,
    SignalValidationError,
)
from backend.engines.market_signal.lifecycle import SignalLifecycleManager
from backend.engines.market_signal.publisher import SignalEventPublisher
from backend.engines.market_signal.quality import SignalQualityScorer
from backend.engines.market_signal.schemas import (
    LifecycleUpdateResult,
    PIPELINE_VERSION,
    SignalCreationResult,
    SignalDirection,
    SignalMetadata,
    SignalRejection,
    SignalState,
    TERMINAL_SIGNAL_STATES,
    TRADEABLE_SIGNAL_STATES,
    TradingSignal,
)
from backend.engines.market_signal.validator import (
    ConfidenceValidator,
    DecisionValidator,
    EntryNormalizer,
    ExpiryValidator,
    RiskValidator,
    SessionValidator,
    SignalInputValidator,
    TakeProfitMapper,
)

__all__ = [
    "ConfidenceValidator",
    "ConfigurationError",
    "DecisionValidator",
    "DuplicateDetector",
    "DuplicateSignalError",
    "ENGINE_ID",
    "EntryNormalizer",
    "EvidenceSummaryItem",
    "ExpiryValidator",
    "InvalidDecisionError",
    "InvalidRiskError",
    "LifecycleUpdateResult",
    "LowConfidenceError",
    "MarketSignalConfig",
    "MarketSignalEngine",
    "PIPELINE_VERSION",
    "QualityTier",
    "RiskSummary",
    "RiskValidator",
    "SessionValidator",
    "SignalAnalysisEvent",
    "SignalCreationResult",
    "SignalDirection",
    "SignalEngineError",
    "SignalEventPublisher",
    "SignalExpiredError",
    "SignalInputValidator",
    "SignalLifecycleManager",
    "SignalMetadata",
    "SignalNotFoundError",
    "SignalQualityScorer",
    "SignalRejection",
    "SignalState",
    "SignalValidationError",
    "TERMINAL_SIGNAL_STATES",
    "TRADEABLE_SIGNAL_STATES",
    "TakeProfitMapper",
    "TradingSignal",
    "load_market_signal_config",
]
