"""Canonical schemas for the Order Block Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OrderBlockDirection(StrEnum):
    """Order block directional classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class OrderBlockStatus(StrEnum):
    """Order block lifecycle status."""

    FRESH = "fresh"
    MITIGATED = "mitigated"
    INVALIDATED = "invalidated"


class OrderBlockQuality(StrEnum):
    """Order block quality classification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OrderBlockBias(StrEnum):
    """Dominant order block bias."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNDETERMINED = "undetermined"


class OrderBlockEventKind(StrEnum):
    """Order block timeline event types."""

    ORDER_BLOCK_DETECTED = "OrderBlockDetected"
    BULLISH_ORDER_BLOCK_DETECTED = "BullishOrderBlockDetected"
    BEARISH_ORDER_BLOCK_DETECTED = "BearishOrderBlockDetected"
    FRESH_ORDER_BLOCK = "FreshOrderBlock"
    MITIGATED_ORDER_BLOCK = "MitigatedOrderBlock"
    INVALIDATED_ORDER_BLOCK = "InvalidatedOrderBlock"
    ORDER_BLOCK_UPDATED = "OrderBlockUpdated"


class OriginCandidate(BaseModel):
    """Internal origin candle candidate before displacement validation."""

    model_config = ConfigDict(frozen=True)

    direction: OrderBlockDirection
    origin_bar_index: int
    origin_time_utc: datetime
    zone_high: Decimal
    zone_low: Decimal
    displacement_start_index: int


class OrderBlock(BaseModel):
    """Institutional order block zone."""

    model_config = ConfigDict(frozen=True)

    block_id: str
    direction: OrderBlockDirection
    status: OrderBlockStatus
    high: Decimal
    low: Decimal
    origin_bar_index: int
    origin_time_utc: datetime
    displacement_bar_index: int
    mitigation_bar_index: int | None = None
    invalidation_bar_index: int | None = None
    quality: OrderBlockQuality
    strength: Decimal
    structure_alignment: bool
    liquidity_confluence: bool
    evidence: list[str] = Field(default_factory=list)


class OrderBlockState(BaseModel):
    """Serializable order block engine state."""

    active_blocks: list[OrderBlock] = Field(default_factory=list)
    last_analysis_utc: datetime | None = None
    bar_count: int = 0


class OrderBlockEvent(BaseModel):
    """Timeline order block event."""

    model_config = ConfigDict(frozen=True)

    kind: OrderBlockEventKind
    timestamp_utc: datetime
    timeframe: str
    description: str
    block_id: str | None = None
    direction: OrderBlockDirection | None = None
    status: OrderBlockStatus | None = None
    price: Decimal | None = None


class OrderBlockAnalysis(BaseModel):
    """Complete order block analysis output."""

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    order_blocks: list[OrderBlock] = Field(default_factory=list)
    fresh_blocks: list[OrderBlock] = Field(default_factory=list)
    mitigated_blocks: list[OrderBlock] = Field(default_factory=list)
    invalidated_blocks: list[OrderBlock] = Field(default_factory=list)
    bias: OrderBlockBias = OrderBlockBias.UNDETERMINED
    confidence: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)
    state: OrderBlockState = Field(default_factory=OrderBlockState)
    events: list[OrderBlockEvent] = Field(default_factory=list)
