"""Canonical schemas for the Premium / Discount Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.engines.market_structure.schemas import SwingKind, SwingLabel, TrendDirection


class PremiumDiscountZone(StrEnum):
    """Price territory relative to dealing range equilibrium."""

    PREMIUM = "premium"
    DISCOUNT = "discount"
    EQUILIBRIUM = "equilibrium"


class PremiumDiscountBias(StrEnum):
    """Dominant institutional pricing bias."""

    PREMIUM = "premium"
    DISCOUNT = "discount"
    EQUILIBRIUM = "equilibrium"
    NEUTRAL = "neutral"
    UNDETERMINED = "undetermined"


class PremiumDiscountQuality(StrEnum):
    """Quality tier for ranges and analysis."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DealingRangeScope(StrEnum):
    """Dealing range structural scope."""

    EXTERNAL = "external"
    INTERNAL = "internal"
    PRIMARY = "primary"


class InstitutionalZoneType(StrEnum):
    """Upstream institutional zone source type."""

    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fair_value_gap"
    BREAKER_BLOCK = "breaker_block"
    MITIGATION_BLOCK = "mitigation_block"
    LIQUIDITY = "liquidity"


class FibDirection(StrEnum):
    """Fibonacci projection direction within dealing range."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class PremiumDiscountEventKind(StrEnum):
    """Premium / discount timeline event types."""

    DEALING_RANGE_ESTABLISHED = "DealingRangeEstablished"
    DEALING_RANGE_UPDATED = "DealingRangeUpdated"
    DEALING_RANGE_INVALIDATED = "DealingRangeInvalidated"
    SWING_HIGH_ANCHORED = "SwingHighAnchored"
    SWING_LOW_ANCHORED = "SwingLowAnchored"
    PREMIUM_ZONE_ENTERED = "PremiumZoneEntered"
    DISCOUNT_ZONE_ENTERED = "DiscountZoneEntered"
    EQUILIBRIUM_REACHED = "EquilibriumReached"
    PREMIUM_ARRAY_FORMED = "PremiumArrayFormed"
    DISCOUNT_ARRAY_FORMED = "DiscountArrayFormed"
    INTERNAL_PREMIUM_CLASSIFIED = "InternalPremiumClassified"
    INTERNAL_DISCOUNT_CLASSIFIED = "InternalDiscountClassified"
    HTF_PREMIUM_CONTEXT = "HTFPremiumContext"
    HTF_DISCOUNT_CONTEXT = "HTFDiscountContext"
    MTF_PREMIUM_ALIGNED = "MTFPremiumAligned"
    MTF_DISCOUNT_ALIGNED = "MTFDiscountAligned"
    NESTED_PREMIUM_ZONE = "NestedPremiumZone"
    NESTED_DISCOUNT_ZONE = "NestedDiscountZone"
    FIBONACCI_RANGE_COMPUTED = "FibonacciRangeComputed"
    OTE_ZONE_DERIVED = "OTEZoneDerived"
    INSTITUTIONAL_CONTEXT_UPDATED = "InstitutionalContextUpdated"
    PREMIUM_DISCOUNT_UPDATED = "PremiumDiscountUpdated"
    PREMIUM_DETECTED = "PremiumDetected"
    DISCOUNT_DETECTED = "DiscountDetected"
    EQUILIBRIUM_CALCULATED = "EquilibriumCalculated"
    PREMIUM_EXPIRED = "PremiumExpired"
    DISCOUNT_EXPIRED = "DiscountExpired"
    PREMIUM_QUALITY_UPDATED = "PremiumQualityUpdated"


class SwingAnchor(BaseModel):
    """Swing high or swing low anchor for dealing range bounds."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    timestamp_utc: datetime
    bar_index: int
    kind: SwingKind
    label: SwingLabel = SwingLabel.NONE
    quality_score: Decimal = Decimal("0")


class DealingRange(BaseModel):
    """Institutional dealing range derived from swing anchors."""

    model_config = ConfigDict(frozen=True)

    range_id: str
    scope: DealingRangeScope
    high: Decimal
    low: Decimal
    equilibrium: Decimal
    range_size: Decimal
    swing_high: SwingAnchor
    swing_low: SwingAnchor
    formation_bar_index: int
    formation_time_utc: datetime
    is_valid: bool
    invalidation_reason: str | None = None
    quality: PremiumDiscountQuality = PremiumDiscountQuality.LOW
    strength: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)


class PriceZoneBand(BaseModel):
    """Premium or discount territory band."""

    model_config = ConfigDict(frozen=True)

    territory: PremiumDiscountZone
    high: Decimal
    low: Decimal
    scope: DealingRangeScope


class EquilibriumLevel(BaseModel):
    """50% equilibrium midpoint with tolerance band."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    tolerance_high: Decimal
    tolerance_low: Decimal
    scope: DealingRangeScope


class ArrayZoneEntry(BaseModel):
    """Normalized institutional zone entry for array assembly."""

    model_config = ConfigDict(frozen=True)

    zone_id: str
    zone_type: InstitutionalZoneType
    high: Decimal
    low: Decimal
    midpoint: Decimal
    direction: str | None = None
    status: str | None = None
    strength: Decimal = Decimal("0")
    distance_from_equilibrium_pips: Decimal = Decimal("0")
    placement_score: Decimal = Decimal("0")


class InstitutionalArray(BaseModel):
    """Clustered institutional zones in premium or discount territory."""

    model_config = ConfigDict(frozen=True)

    array_id: str
    territory: PremiumDiscountZone
    scope: DealingRangeScope
    zone_entries: list[ArrayZoneEntry] = Field(default_factory=list)
    cluster_high: Decimal
    cluster_low: Decimal
    entry_count: int
    dominant_direction: str | None = None
    confluence_score: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)


class FibonacciLevel(BaseModel):
    """Single Fibonacci price level within dealing range."""

    model_config = ConfigDict(frozen=True)

    ratio: Decimal
    price: Decimal
    label: str


class FibonacciDealingRange(BaseModel):
    """Fibonacci levels projected within dealing range."""

    model_config = ConfigDict(frozen=True)

    range_id: str
    direction: FibDirection
    levels: list[FibonacciLevel] = Field(default_factory=list)
    ote_low_level: Decimal
    ote_high_level: Decimal
    equilibrium_level: Decimal


class OptimalTradeEntryZone(BaseModel):
    """Optimal trade entry band within premium or discount."""

    model_config = ConfigDict(frozen=True)

    ote_id: str
    territory: PremiumDiscountZone
    direction: FibDirection
    high: Decimal
    low: Decimal
    fib_low_ratio: Decimal
    fib_high_ratio: Decimal
    overlapping_zone_ids: list[str] = Field(default_factory=list)
    quality: PremiumDiscountQuality
    strength: Decimal
    evidence: list[str] = Field(default_factory=list)


class InstitutionalPricingContext(BaseModel):
    """Composite institutional pricing narrative."""

    model_config = ConfigDict(frozen=True)

    narrative: list[str] = Field(default_factory=list)
    current_price_location: PremiumDiscountZone
    preferred_buy_territory: PremiumDiscountZone
    preferred_sell_territory: PremiumDiscountZone
    active_dealing_range_scope: DealingRangeScope
    structure_trend: TrendDirection | None = None
    liquidity_bias: str | None = None
    dominant_array_territory: PremiumDiscountZone | None = None
    mtf_aligned: bool = False
    ote_available: bool = False
    confidence: Decimal = Decimal("0")


class MTFPremiumDiscountAlignment(BaseModel):
    """Multi-timeframe premium or discount alignment."""

    model_config = ConfigDict(frozen=True)

    territory: PremiumDiscountZone
    aligned_timeframes: list[str] = Field(default_factory=list)
    alignment_score: Decimal
    ltf_timeframe: str
    htf_timeframe: str
    range_overlap_percent: Decimal
    array_overlap_count: int
    evidence: list[str] = Field(default_factory=list)


class HTFPricingContext(BaseModel):
    """Higher-timeframe premium or discount context."""

    model_config = ConfigDict(frozen=True)

    timeframe: str
    territory: PremiumDiscountZone
    dealing_range: DealingRange
    array_count: int
    equilibrium: Decimal
    evidence: list[str] = Field(default_factory=list)


class NestedZoneContext(BaseModel):
    """Nested zone relationship within same territory."""

    model_config = ConfigDict(frozen=True)

    child_zone_id: str
    child_zone_type: InstitutionalZoneType
    parent_zone_id: str
    parent_zone_type: InstitutionalZoneType
    territory: PremiumDiscountZone
    containment_percent: Decimal
    evidence: list[str] = Field(default_factory=list)


class PremiumDiscountContext(BaseModel):
    """Lightweight HTF summary for MTF alignment."""

    model_config = ConfigDict(frozen=True)

    timeframe: str
    dealing_range: DealingRange
    price_location: PremiumDiscountZone
    premium_arrays: list[InstitutionalArray] = Field(default_factory=list)
    discount_arrays: list[InstitutionalArray] = Field(default_factory=list)
    equilibrium: Decimal


class PremiumDiscountState(BaseModel):
    """Serializable premium / discount engine continuity state."""

    active_dealing_range: DealingRange | None = None
    active_external_range: DealingRange | None = None
    active_internal_range: DealingRange | None = None
    last_price_location: PremiumDiscountZone = PremiumDiscountZone.EQUILIBRIUM
    last_analysis_utc: datetime | None = None
    bar_count: int = 0


class PremiumDiscountEvent(BaseModel):
    """Timeline premium / discount event."""

    model_config = ConfigDict(frozen=True)

    kind: PremiumDiscountEventKind
    timestamp_utc: datetime
    timeframe: str
    description: str
    range_id: str | None = None
    price: Decimal | None = None
    territory: PremiumDiscountZone | None = None
    array_id: str | None = None
    ote_id: str | None = None


class PremiumDiscountAnalysis(BaseModel):
    """Complete premium / discount analysis output."""

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    current_price: Decimal
    dealing_range: DealingRange
    external_range: DealingRange
    internal_range: DealingRange
    swing_high: SwingAnchor
    swing_low: SwingAnchor
    premium_zone: PriceZoneBand
    discount_zone: PriceZoneBand
    equilibrium: EquilibriumLevel
    price_location: PremiumDiscountZone
    premium_arrays: list[InstitutionalArray] = Field(default_factory=list)
    discount_arrays: list[InstitutionalArray] = Field(default_factory=list)
    internal_premium: PriceZoneBand | None = None
    internal_discount: PriceZoneBand | None = None
    htf_premium: HTFPricingContext | None = None
    htf_discount: HTFPricingContext | None = None
    mtf_premium_alignment: MTFPremiumDiscountAlignment | None = None
    mtf_discount_alignment: MTFPremiumDiscountAlignment | None = None
    nested_premium_zones: list[NestedZoneContext] = Field(default_factory=list)
    nested_discount_zones: list[NestedZoneContext] = Field(default_factory=list)
    fibonacci_range: FibonacciDealingRange
    ote_zone: OptimalTradeEntryZone | None = None
    institutional_context: InstitutionalPricingContext
    bias: PremiumDiscountBias
    confidence: Decimal = Decimal("0")
    quality: PremiumDiscountQuality
    strength: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)
    state: PremiumDiscountState = Field(default_factory=PremiumDiscountState)
    events: list[PremiumDiscountEvent] = Field(default_factory=list)
