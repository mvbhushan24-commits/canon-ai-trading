"""Canonical schemas for the Breaker Block Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.engines.market_fvg.schemas import PremiumDiscountZone


class BreakerBlockDirection(StrEnum):
    """Breaker block directional classification (post-flip role)."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class BreakerBlockStatus(StrEnum):
    """Breaker block lifecycle status."""

    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    MITIGATED = "mitigated"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class BreakerBlockQuality(StrEnum):
    """Breaker block quality classification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BreakerBlockBias(StrEnum):
    """Dominant breaker block bias."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNDETERMINED = "undetermined"


class BreakerSourceType(StrEnum):
    """Origin entity type for breaker formation."""

    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fair_value_gap"


class BreakerBlockEventKind(StrEnum):
    """Breaker block timeline event types."""

    BREAKER_BLOCK_DETECTED = "BreakerBlockDetected"
    BULLISH_BREAKER_BLOCK_DETECTED = "BullishBreakerBlockDetected"
    BEARISH_BREAKER_BLOCK_DETECTED = "BearishBreakerBlockDetected"
    CANDIDATE_BREAKER_BLOCK = "CandidateBreakerBlock"
    CONFIRMED_BREAKER_BLOCK = "ConfirmedBreakerBlock"
    MITIGATED_BREAKER_BLOCK = "MitigatedBreakerBlock"
    INVALIDATED_BREAKER_BLOCK = "InvalidatedBreakerBlock"
    EXPIRED_BREAKER_BLOCK = "ExpiredBreakerBlock"
    LIQUIDITY_CONFLUENCE_BREAKER = "LiquidityConfluenceBreaker"
    FVG_CONFLUENCE_BREAKER = "FVGConfluenceBreaker"
    BREAKER_BLOCK_UPDATED = "BreakerBlockUpdated"


class BreakerCandidate(BaseModel):
    """Internal breaker candidate before confirmation and scoring."""

    model_config = ConfigDict(frozen=True)

    source_type: BreakerSourceType
    source_id: str
    source_direction: str
    direction: BreakerBlockDirection
    high: Decimal
    low: Decimal
    invalidation_bar_index: int
    invalidation_time_utc: datetime
    source_strength: Decimal
    source_quality: str
    formation_bar_index: int
    formation_time_utc: datetime


class BreakerBlock(BaseModel):
    """Institutional breaker block zone."""

    model_config = ConfigDict(frozen=True)

    breaker_id: str
    direction: BreakerBlockDirection
    status: BreakerBlockStatus
    high: Decimal
    low: Decimal
    source_type: BreakerSourceType
    source_id: str
    source_direction: str
    invalidation_bar_index: int
    invalidation_time_utc: datetime
    formation_bar_index: int
    formation_time_utc: datetime
    confirmation_bar_index: int | None = None
    confirmation_time_utc: datetime | None = None
    mitigation_bar_index: int | None = None
    invalidation_breaker_bar_index: int | None = None
    expiration_bar_index: int | None = None
    quality: BreakerBlockQuality
    strength: Decimal
    is_confirmed: bool
    confirmation_reason: str
    structure_alignment: bool
    liquidity_confluence: bool
    fvg_confluence: bool
    liquidity_confluence_ids: list[str] = Field(default_factory=list)
    fvg_confluence_ids: list[str] = Field(default_factory=list)
    premium_discount: PremiumDiscountZone = PremiumDiscountZone.EQUILIBRIUM
    dealing_range_high: Decimal | None = None
    dealing_range_low: Decimal | None = None
    evidence: list[str] = Field(default_factory=list)


class BreakerBlockState(BaseModel):
    """Serializable breaker block engine state."""

    active_breakers: list[BreakerBlock] = Field(default_factory=list)
    last_analysis_utc: datetime | None = None
    bar_count: int = 0


class BreakerBlockEvent(BaseModel):
    """Timeline breaker block event."""

    model_config = ConfigDict(frozen=True)

    kind: BreakerBlockEventKind
    timestamp_utc: datetime
    timeframe: str
    description: str
    breaker_id: str | None = None
    direction: BreakerBlockDirection | None = None
    status: BreakerBlockStatus | None = None
    price: Decimal | None = None
    source_id: str | None = None


class BreakerBlockAnalysis(BaseModel):
    """Complete breaker block analysis output."""

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    breaker_blocks: list[BreakerBlock] = Field(default_factory=list)
    candidate_breakers: list[BreakerBlock] = Field(default_factory=list)
    confirmed_breakers: list[BreakerBlock] = Field(default_factory=list)
    mitigated_breakers: list[BreakerBlock] = Field(default_factory=list)
    invalidated_breakers: list[BreakerBlock] = Field(default_factory=list)
    expired_breakers: list[BreakerBlock] = Field(default_factory=list)
    bullish_breakers: list[BreakerBlock] = Field(default_factory=list)
    bearish_breakers: list[BreakerBlock] = Field(default_factory=list)
    bias: BreakerBlockBias = BreakerBlockBias.UNDETERMINED
    confidence: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)
    state: BreakerBlockState = Field(default_factory=BreakerBlockState)
    events: list[BreakerBlockEvent] = Field(default_factory=list)
