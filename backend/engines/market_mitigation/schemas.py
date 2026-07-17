"""Canonical schemas for the Mitigation Block Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.engines.market_fvg.schemas import PremiumDiscountZone


class MitigationBlockDirection(StrEnum):
    """Mitigation block directional classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class MitigationBlockStatus(StrEnum):
    """Mitigation block lifecycle status."""

    FRESH = "fresh"
    PARTIAL = "partial"
    CONFIRMED = "confirmed"
    USED = "used"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class MitigationBlockQuality(StrEnum):
    """Mitigation block quality classification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MitigationBlockBias(StrEnum):
    """Dominant mitigation block bias."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNDETERMINED = "undetermined"


class StructureScope(StrEnum):
    """Structure placement scope."""

    INTERNAL = "internal"
    EXTERNAL = "external"
    UNDETERMINED = "undetermined"


class MitigationSourceType(StrEnum):
    """Mitigation block formation source."""

    DISPLACEMENT = "displacement"
    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fair_value_gap"
    BREAKER_BLOCK = "breaker_block"
    MITIGATION_BLOCK = "mitigation_block"


class MitigationBlockEventKind(StrEnum):
    """Mitigation block timeline event types."""

    MITIGATION_BLOCK_DETECTED = "MitigationBlockDetected"
    BULLISH_MITIGATION_BLOCK_DETECTED = "BullishMitigationBlockDetected"
    BEARISH_MITIGATION_BLOCK_DETECTED = "BearishMitigationBlockDetected"
    FRESH_MITIGATION_BLOCK = "FreshMitigationBlock"
    PARTIAL_MITIGATION_BLOCK = "PartialMitigationBlock"
    FULL_MITIGATION_BLOCK = "FullMitigationBlock"
    MULTI_TOUCH_MITIGATION_BLOCK = "MultiTouchMitigationBlock"
    CONFIRMED_MITIGATION_BLOCK = "ConfirmedMitigationBlock"
    USED_MITIGATION_BLOCK = "UsedMitigationBlock"
    INVALIDATED_MITIGATION_BLOCK = "InvalidatedMitigationBlock"
    EXPIRED_MITIGATION_BLOCK = "ExpiredMitigationBlock"
    NESTED_MITIGATION_BLOCK = "NestedMitigationBlock"
    INTERNAL_MITIGATION_BLOCK = "InternalMitigationBlock"
    EXTERNAL_MITIGATION_BLOCK = "ExternalMitigationBlock"
    HTF_MITIGATION_ALIGNED = "HTFMitigationAligned"
    LTF_MITIGATION_NESTED = "LTFMitigationNested"
    LIQUIDITY_CONFLUENCE_MITIGATION = "LiquidityConfluenceMitigation"
    ORDER_BLOCK_CONFLUENCE_MITIGATION = "OrderBlockConfluenceMitigation"
    FVG_CONFLUENCE_MITIGATION = "FVGConfluenceMitigation"
    BREAKER_CONFLUENCE_MITIGATION = "BreakerConfluenceMitigation"
    MITIGATION_BLOCK_UPDATED = "MitigationBlockUpdated"


class MitigationCandidate(BaseModel):
    """Internal mitigation block candidate before scoring and lifecycle."""

    model_config = ConfigDict(frozen=True)

    direction: MitigationBlockDirection
    high: Decimal
    low: Decimal
    origin_bar_index: int
    origin_time_utc: datetime
    displacement_bar_index: int
    displacement_time_utc: datetime
    formation_bar_index: int
    formation_time_utc: datetime
    source_type: MitigationSourceType = MitigationSourceType.DISPLACEMENT
    parent_zone_id: str | None = None
    displacement_magnitude: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)


class MitigationTouch(BaseModel):
    """Recorded price interaction with a mitigation zone."""

    model_config = ConfigDict(frozen=True)

    bar_index: int
    timestamp_utc: datetime
    touch_price: Decimal
    touch_mode: str
    mitigation_percent_after: Decimal


class MTFMitigationAlignment(BaseModel):
    """Higher-timeframe mitigation block alignment."""

    model_config = ConfigDict(frozen=True)

    aligned_timeframes: list[str] = Field(default_factory=list)
    alignment_direction: MitigationBlockDirection
    alignment_score: Decimal
    parent_timeframe: str
    parent_block_id: str


class MitigationBlock(BaseModel):
    """Institutional mitigation block zone."""

    model_config = ConfigDict(frozen=True)

    block_id: str
    direction: MitigationBlockDirection
    status: MitigationBlockStatus
    high: Decimal
    low: Decimal
    origin_bar_index: int
    origin_time_utc: datetime
    displacement_bar_index: int
    displacement_time_utc: datetime
    formation_bar_index: int
    formation_time_utc: datetime
    mitigation_percent: Decimal = Decimal("0")
    touch_count: int = 0
    first_touch_bar_index: int | None = None
    last_touch_bar_index: int | None = None
    confirmation_bar_index: int | None = None
    confirmation_time_utc: datetime | None = None
    used_bar_index: int | None = None
    invalidation_bar_index: int | None = None
    expiration_bar_index: int | None = None
    quality: MitigationBlockQuality
    strength: Decimal
    is_confirmed: bool
    confirmation_reason: str
    structure_scope: StructureScope = StructureScope.UNDETERMINED
    structure_alignment: bool = False
    liquidity_confluence: bool = False
    order_block_confluence: bool = False
    fvg_confluence: bool = False
    breaker_confluence: bool = False
    is_nested: bool = False
    parent_zone_id: str | None = None
    parent_zone_type: MitigationSourceType | None = None
    child_block_ids: list[str] = Field(default_factory=list)
    htf_aligned: bool = False
    htf_block_ids: list[str] = Field(default_factory=list)
    ltf_nested: bool = False
    ltf_block_ids: list[str] = Field(default_factory=list)
    confluence_ids: list[str] = Field(default_factory=list)
    premium_discount: PremiumDiscountZone = PremiumDiscountZone.EQUILIBRIUM
    dealing_range_high: Decimal | None = None
    dealing_range_low: Decimal | None = None
    source_type: MitigationSourceType = MitigationSourceType.DISPLACEMENT
    evidence: list[str] = Field(default_factory=list)


class MitigationBlockState(BaseModel):
    """Serializable mitigation block engine state."""

    active_blocks: list[MitigationBlock] = Field(default_factory=list)
    last_analysis_utc: datetime | None = None
    bar_count: int = 0


class MitigationBlockEvent(BaseModel):
    """Timeline mitigation block event."""

    model_config = ConfigDict(frozen=True)

    kind: MitigationBlockEventKind
    timestamp_utc: datetime
    timeframe: str
    description: str
    block_id: str | None = None
    direction: MitigationBlockDirection | None = None
    status: MitigationBlockStatus | None = None
    price: Decimal | None = None
    touch_count: int | None = None
    mitigation_percent: Decimal | None = None
    parent_zone_id: str | None = None


class MitigationBlockAnalysis(BaseModel):
    """Complete mitigation block analysis output."""

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    mitigation_blocks: list[MitigationBlock] = Field(default_factory=list)
    fresh_blocks: list[MitigationBlock] = Field(default_factory=list)
    partial_blocks: list[MitigationBlock] = Field(default_factory=list)
    confirmed_blocks: list[MitigationBlock] = Field(default_factory=list)
    used_blocks: list[MitigationBlock] = Field(default_factory=list)
    invalidated_blocks: list[MitigationBlock] = Field(default_factory=list)
    expired_blocks: list[MitigationBlock] = Field(default_factory=list)
    bullish_blocks: list[MitigationBlock] = Field(default_factory=list)
    bearish_blocks: list[MitigationBlock] = Field(default_factory=list)
    nested_blocks: list[MitigationBlock] = Field(default_factory=list)
    internal_blocks: list[MitigationBlock] = Field(default_factory=list)
    external_blocks: list[MitigationBlock] = Field(default_factory=list)
    htf_aligned_blocks: list[MitigationBlock] = Field(default_factory=list)
    bias: MitigationBlockBias = MitigationBlockBias.UNDETERMINED
    confidence: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)
    state: MitigationBlockState = Field(default_factory=MitigationBlockState)
    events: list[MitigationBlockEvent] = Field(default_factory=list)
