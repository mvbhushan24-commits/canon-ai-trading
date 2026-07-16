"""Canonical schemas for the Fair Value Gap Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FairValueGapDirection(StrEnum):
    """Fair value gap directional classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class FairValueGapStatus(StrEnum):
    """Fair value gap lifecycle status."""

    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    MITIGATED = "mitigated"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class FairValueGapQuality(StrEnum):
    """Fair value gap quality classification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FairValueGapBias(StrEnum):
    """Dominant fair value gap bias."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNDETERMINED = "undetermined"


class PremiumDiscountZone(StrEnum):
    """Premium / discount placement relative to dealing range."""

    PREMIUM = "premium"
    DISCOUNT = "discount"
    EQUILIBRIUM = "equilibrium"


class FairValueGapEventKind(StrEnum):
    """Fair value gap timeline event types."""

    FAIR_VALUE_GAP_DETECTED = "FairValueGapDetected"
    BULLISH_FAIR_VALUE_GAP_DETECTED = "BullishFairValueGapDetected"
    BEARISH_FAIR_VALUE_GAP_DETECTED = "BearishFairValueGapDetected"
    OPEN_FAIR_VALUE_GAP = "OpenFairValueGap"
    PARTIAL_FILL_FAIR_VALUE_GAP = "PartialFillFairValueGap"
    FILLED_FAIR_VALUE_GAP = "FilledFairValueGap"
    MITIGATED_FAIR_VALUE_GAP = "MitigatedFairValueGap"
    INVALIDATED_FAIR_VALUE_GAP = "InvalidatedFairValueGap"
    EXPIRED_FAIR_VALUE_GAP = "ExpiredFairValueGap"
    CE_ENCROACHED = "CEEncroached"
    NESTED_FAIR_VALUE_GAP = "NestedFairValueGap"
    MTF_ALIGNED_FAIR_VALUE_GAP = "MTFAlignedFairValueGap"
    FAIR_VALUE_GAP_UPDATED = "FairValueGapUpdated"


class FVGFormationCandidate(BaseModel):
    """Internal three-candle formation candidate before validation."""

    model_config = ConfigDict(frozen=True)

    direction: FairValueGapDirection
    candle_a_index: int
    candle_b_index: int
    candle_c_index: int
    origin_bar_index: int
    origin_time_utc: datetime
    high: Decimal
    low: Decimal


class MTFGapAlignment(BaseModel):
    """Multi-timeframe gap alignment metadata."""

    model_config = ConfigDict(frozen=True)

    aligned_timeframes: list[str] = Field(default_factory=list)
    alignment_direction: FairValueGapDirection
    alignment_score: Decimal
    parent_timeframe: str
    parent_gap_id: str


class FairValueGap(BaseModel):
    """Institutional fair value gap zone."""

    model_config = ConfigDict(frozen=True)

    gap_id: str
    direction: FairValueGapDirection
    status: FairValueGapStatus
    high: Decimal
    low: Decimal
    ce_price: Decimal
    gap_size: Decimal
    gap_size_pips: Decimal
    fill_percent: Decimal = Decimal("0")
    is_valid: bool = True
    validity_reason: str = ""
    origin_bar_index: int
    origin_time_utc: datetime
    candle_a_index: int
    candle_b_index: int
    candle_c_index: int
    fill_bar_index: int | None = None
    mitigation_bar_index: int | None = None
    invalidation_bar_index: int | None = None
    expiration_bar_index: int | None = None
    quality: FairValueGapQuality
    strength: Decimal
    structure_alignment: bool = False
    liquidity_confluence: bool = False
    order_block_confluence: bool = False
    premium_discount: PremiumDiscountZone = PremiumDiscountZone.EQUILIBRIUM
    dealing_range_high: Decimal | None = None
    dealing_range_low: Decimal | None = None
    nested_parent_gap_id: str | None = None
    nested_child_gap_ids: list[str] = Field(default_factory=list)
    mtf_alignment: MTFGapAlignment | None = None
    evidence: list[str] = Field(default_factory=list)


class FairValueGapState(BaseModel):
    """Serializable fair value gap engine state."""

    active_gaps: list[FairValueGap] = Field(default_factory=list)
    last_analysis_utc: datetime | None = None
    bar_count: int = 0


class FairValueGapEvent(BaseModel):
    """Timeline fair value gap event."""

    model_config = ConfigDict(frozen=True)

    kind: FairValueGapEventKind
    timestamp_utc: datetime
    timeframe: str
    description: str
    gap_id: str | None = None
    direction: FairValueGapDirection | None = None
    status: FairValueGapStatus | None = None
    price: Decimal | None = None
    fill_percent: Decimal | None = None


class FairValueGapAnalysis(BaseModel):
    """Complete fair value gap analysis output."""

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    fair_value_gaps: list[FairValueGap] = Field(default_factory=list)
    open_gaps: list[FairValueGap] = Field(default_factory=list)
    partial_gaps: list[FairValueGap] = Field(default_factory=list)
    filled_gaps: list[FairValueGap] = Field(default_factory=list)
    mitigated_gaps: list[FairValueGap] = Field(default_factory=list)
    invalidated_gaps: list[FairValueGap] = Field(default_factory=list)
    expired_gaps: list[FairValueGap] = Field(default_factory=list)
    bullish_gaps: list[FairValueGap] = Field(default_factory=list)
    bearish_gaps: list[FairValueGap] = Field(default_factory=list)
    bias: FairValueGapBias = FairValueGapBias.UNDETERMINED
    confidence: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)
    state: FairValueGapState = Field(default_factory=FairValueGapState)
    events: list[FairValueGapEvent] = Field(default_factory=list)
