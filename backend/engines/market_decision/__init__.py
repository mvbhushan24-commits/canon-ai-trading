"""Market Decision Engine — institutional trade decision synthesis.

Sprint 10.2: consumes completed evidence from Sprints 2–9 and produces
explainable BUY, SELL, or NO_TRADE decisions.
"""

from backend.engines.market_decision.config import (
    MarketDecisionConfig,
    load_market_decision_config,
)
from backend.engines.market_decision.engine import MarketDecisionEngine
from backend.engines.market_decision.events import DecisionAnalysisEvent, ENGINE_ID
from backend.engines.market_decision.exceptions import (
    ConfigurationError,
    ConflictingEvidenceError,
    DecisionEngineError,
    DecisionValidationError,
    InsufficientEvidenceError,
    InvalidBreakerError,
    InvalidFVGError,
    InvalidLiquidityError,
    InvalidMitigationError,
    InvalidOrderBlockError,
    InvalidPremiumDiscountError,
    InvalidRiskError,
    InvalidSessionError,
    InvalidStructureError,
    LowConfidenceError,
)
from backend.engines.market_decision.publisher import DecisionEventPublisher
from backend.engines.market_decision.schemas import (
    DecisionMetadata,
    DecisionState,
    DirectionBias,
    EntrySpec,
    EntryType,
    EvidenceBundle,
    EvidenceCache,
    EvidenceSummaryItem,
    NewsRestrictionResult,
    PIPELINE_VERSION,
    QualityTier,
    RiskSummary,
    TradeDecision,
    TradeDirection,
)

__all__ = [
    "ConfigurationError",
    "ConflictingEvidenceError",
    "DecisionAnalysisEvent",
    "DecisionEngineError",
    "DecisionEventPublisher",
    "DecisionMetadata",
    "DecisionState",
    "DecisionValidationError",
    "DirectionBias",
    "ENGINE_ID",
    "EntrySpec",
    "EntryType",
    "EvidenceBundle",
    "EvidenceCache",
    "EvidenceSummaryItem",
    "InsufficientEvidenceError",
    "InvalidBreakerError",
    "InvalidFVGError",
    "InvalidLiquidityError",
    "InvalidMitigationError",
    "InvalidOrderBlockError",
    "InvalidPremiumDiscountError",
    "InvalidRiskError",
    "InvalidSessionError",
    "InvalidStructureError",
    "LowConfidenceError",
    "MarketDecisionConfig",
    "MarketDecisionEngine",
    "NewsRestrictionResult",
    "PIPELINE_VERSION",
    "QualityTier",
    "RiskSummary",
    "TradeDecision",
    "TradeDirection",
    "load_market_decision_config",
]
