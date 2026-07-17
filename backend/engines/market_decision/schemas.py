"""Canonical schemas for the Market Decision Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.engines.market_breaker import BreakerBlockAnalysis
from backend.engines.market_fvg import FairValueGapAnalysis
from backend.engines.market_liquidity import LiquidityAnalysis
from backend.engines.market_mitigation import MitigationBlockAnalysis
from backend.engines.market_order_block import OrderBlockAnalysis
from backend.engines.market_premium_discount import PremiumDiscountAnalysis
from backend.engines.market_sessions import SessionAnalysis
from backend.engines.market_structure import MarketStructure

PIPELINE_VERSION = "0.1.0"


class DecisionState(StrEnum):
    """Terminal or interim decision states."""

    NO_DATA = "NO_DATA"
    WAIT = "WAIT"
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"
    INVALID = "INVALID"


class TradeDirection(StrEnum):
    """Trade direction."""

    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


class QualityTier(StrEnum):
    """Decision quality tier."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DirectionBias(StrEnum):
    """Normalized directional bias from upstream evidence."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNDETERMINED = "undetermined"


class EntryType(StrEnum):
    """Entry specification type."""

    POINT = "point"
    ZONE = "zone"
    OTE = "ote"


class ConflictSeverity(StrEnum):
    """Evidence conflict severity."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PriceLevel(BaseModel):
    """Relevant price level from normalized evidence."""

    model_config = ConfigDict(frozen=True)

    level_id: str
    price: Decimal
    zone_high: Decimal | None = None
    zone_low: Decimal | None = None
    source_engine: str
    label: str = ""


class EntrySpec(BaseModel):
    """Entry specification for a trade decision."""

    price: Decimal | None = None
    zone_high: Decimal | None = None
    zone_low: Decimal | None = None
    entry_type: EntryType = EntryType.ZONE
    source_engine: str = ""
    source_zone_id: str | None = None
    distance_pips: Decimal = Decimal("0")


class RiskRuleOutcome(BaseModel):
    """Per-rule risk validation outcome."""

    rule_name: str
    passed: bool
    actual_value: Decimal | None = None
    threshold: Decimal | None = None
    message: str = ""


class RiskSummary(BaseModel):
    """Risk validation summary."""

    risk_reward_ratio: Decimal | None = None
    stop_size_pips: Decimal | None = None
    spread_pips: Decimal | None = None
    min_rr_met: bool = False
    max_rr_met: bool = False
    spread_acceptable: bool = True
    stop_size_acceptable: bool = True
    confidence_acceptable: bool = True
    session_allowed: bool = True
    news_blocked: bool = False
    news_block_reason: str | None = None
    rule_outcomes: list[RiskRuleOutcome] = Field(default_factory=list)


class EvidenceSummaryItem(BaseModel):
    """Per-engine evidence summary for explainability."""

    engine_id: str
    available: bool
    stale: bool
    direction_bias: str
    confidence: Decimal
    weight: Decimal
    weighted_contribution: Decimal
    quality_tier: str | None = None
    key_evidence: list[str] = Field(default_factory=list)


class DecisionMetadata(BaseModel):
    """Pipeline execution metadata."""

    pipeline_version: str = PIPELINE_VERSION
    config_hash: str = ""
    duration_ms: int = 0
    engines_available: int = 0
    engines_stale: int = 0
    conflict_severity: str = ConflictSeverity.NONE.value
    zone_confluence_count: int = 0


class TradeDecision(BaseModel):
    """Primary trade decision output."""

    decision_id: str
    symbol: str
    timestamp_utc: datetime
    state: DecisionState
    direction: TradeDirection
    entry: EntrySpec = Field(default_factory=EntrySpec)
    stop_loss: Decimal | None = None
    take_profit: list[Decimal] = Field(default_factory=list)
    risk_reward_ratio: Decimal | None = None
    confidence: int = 0
    quality_score: int = 0
    quality_tier: QualityTier = QualityTier.LOW
    reasons: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    evidence_summary: list[EvidenceSummaryItem] = Field(default_factory=list)
    risk_summary: RiskSummary = Field(default_factory=RiskSummary)
    warnings: list[str] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)
    valid_until_utc: datetime | None = None
    metadata: DecisionMetadata = Field(default_factory=DecisionMetadata)


class EvidenceAvailability(BaseModel):
    """Per-engine availability flags."""

    structure_available: bool = False
    liquidity_available: bool = False
    order_block_available: bool = False
    fvg_available: bool = False
    breaker_available: bool = False
    mitigation_available: bool = False
    premium_discount_available: bool = False
    sessions_available: bool = False
    structure_stale: bool = False
    liquidity_stale: bool = False
    order_block_stale: bool = False
    fvg_stale: bool = False
    breaker_stale: bool = False
    mitigation_stale: bool = False
    premium_discount_stale: bool = False
    sessions_stale: bool = False

    @property
    def available_count(self) -> int:
        return sum(
            [
                self.structure_available,
                self.liquidity_available,
                self.order_block_available,
                self.fvg_available,
                self.breaker_available,
                self.mitigation_available,
                self.premium_discount_available,
                self.sessions_available,
            ],
        )

    @property
    def stale_count(self) -> int:
        return sum(
            [
                self.structure_stale,
                self.liquidity_stale,
                self.order_block_stale,
                self.fvg_stale,
                self.breaker_stale,
                self.mitigation_stale,
                self.premium_discount_stale,
                self.sessions_stale,
            ],
        )


class EvidenceBundle(BaseModel):
    """Unified upstream evidence bundle."""

    symbol: str
    timestamp_utc: datetime
    current_price: Decimal
    spread: Decimal | None = None
    structure: MarketStructure | None = None
    liquidity: LiquidityAnalysis | None = None
    order_blocks: OrderBlockAnalysis | None = None
    fair_value_gaps: FairValueGapAnalysis | None = None
    breaker_blocks: BreakerBlockAnalysis | None = None
    mitigation_blocks: MitigationBlockAnalysis | None = None
    premium_discount: PremiumDiscountAnalysis | None = None
    sessions: SessionAnalysis | None = None
    availability: EvidenceAvailability = Field(default_factory=EvidenceAvailability)


class NormalizedEvidence(BaseModel):
    """Per-engine normalized evidence record."""

    engine_id: str
    direction_bias: DirectionBias
    confidence: Decimal
    strength: Decimal
    quality_tier: str | None = None
    key_levels: list[PriceLevel] = Field(default_factory=list)
    invalidation_level: Decimal | None = None
    evidence: list[str] = Field(default_factory=list)
    available: bool = False
    stale: bool = False


class ConflictReport(BaseModel):
    """Directional conflict analysis."""

    bullish_weight: Decimal = Decimal("0")
    bearish_weight: Decimal = Decimal("0")
    conflict_ratio: Decimal = Decimal("0")
    dominant_direction: TradeDirection = TradeDirection.NONE
    conflicting_engines: list[tuple[str, str]] = Field(default_factory=list)
    severity: ConflictSeverity = ConflictSeverity.NONE


class WeightedEvidenceResult(BaseModel):
    """Weighted evidence scoring result."""

    normalized: list[NormalizedEvidence] = Field(default_factory=list)
    summary: list[EvidenceSummaryItem] = Field(default_factory=list)
    bullish_weight: Decimal = Decimal("0")
    bearish_weight: Decimal = Decimal("0")
    confidence: int = 0
    warnings: list[str] = Field(default_factory=list)


class NewsRestrictionResult(BaseModel):
    """News restriction hook result."""

    blocked: bool = False
    reason: str = ""
    expires_utc: datetime | None = None


class CandidateZone(BaseModel):
    """Institutional zone candidate for entry."""

    zone_id: str
    engine_id: str
    zone_high: Decimal
    zone_low: Decimal
    midpoint: Decimal
    direction: TradeDirection
    quality: str
    strength: Decimal
    distance_pips: Decimal


class GateResult(BaseModel):
    """Domain validation gate result."""

    passed: bool
    error_code: str | None = None
    blocking_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class EvidenceCache(BaseModel):
    """Latest upstream envelopes for event-driven mode."""

    symbol: str = ""
    current_price: Decimal | None = None
    spread: Decimal | None = None
    price_timestamp_utc: datetime | None = None
    structure: MarketStructure | None = None
    liquidity: LiquidityAnalysis | None = None
    order_blocks: OrderBlockAnalysis | None = None
    fair_value_gaps: FairValueGapAnalysis | None = None
    breaker_blocks: BreakerBlockAnalysis | None = None
    mitigation_blocks: MitigationBlockAnalysis | None = None
    premium_discount: PremiumDiscountAnalysis | None = None
    sessions: SessionAnalysis | None = None
