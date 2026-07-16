"""Canonical schemas for the Market Structure Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TrendDirection(StrEnum):
    """Current market trend classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    RANGE = "range"
    UNDETERMINED = "undetermined"


class SwingKind(StrEnum):
    """Swing point type."""

    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"


class SwingLabel(StrEnum):
    """Swing classification relative to prior swing of same kind."""

    HH = "HH"
    HL = "HL"
    LH = "LH"
    LL = "LL"
    NONE = "none"


class StructureEventKind(StrEnum):
    """Structure event types emitted by analysis."""

    SWING_DETECTED = "SwingDetected"
    BOS_DETECTED = "BOSDetected"
    CHOCH_DETECTED = "CHoCHDetected"
    TREND_CHANGED = "TrendChanged"
    STRUCTURE_UPDATED = "StructureUpdated"


class BOSDirection(StrEnum):
    """Break of structure direction."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class CHoCHDirection(StrEnum):
    """Change of character direction."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class SwingPoint(BaseModel):
    """Confirmed swing high or swing low."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    timestamp_utc: datetime
    bar_index: int
    kind: SwingKind
    label: SwingLabel = SwingLabel.NONE


class BOSEvent(BaseModel):
    """Break of structure event."""

    model_config = ConfigDict(frozen=True)

    direction: BOSDirection
    broken_level: Decimal
    break_price: Decimal
    timestamp_utc: datetime
    bar_index: int
    timeframe: str


class CHoCHEvent(BaseModel):
    """Change of character event."""

    model_config = ConfigDict(frozen=True)

    direction: CHoCHDirection
    broken_level: Decimal
    break_price: Decimal
    timestamp_utc: datetime
    bar_index: int
    timeframe: str


class StructureEvent(BaseModel):
    """Timeline structure event."""

    model_config = ConfigDict(frozen=True)

    kind: StructureEventKind
    timestamp_utc: datetime
    timeframe: str
    description: str
    price: Decimal | None = None
    trend: TrendDirection | None = None


class StructureState(BaseModel):
    """Serializable structure state for continuity."""

    trend: TrendDirection = TrendDirection.UNDETERMINED
    last_swing_high: SwingPoint | None = None
    last_swing_low: SwingPoint | None = None
    last_bos: BOSEvent | None = None
    last_choch: CHoCHEvent | None = None
    bar_count: int = 0


class MarketStructure(BaseModel):
    """Complete market structure analysis output."""

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    current_trend: TrendDirection
    swing_highs: list[SwingPoint] = Field(default_factory=list)
    swing_lows: list[SwingPoint] = Field(default_factory=list)
    higher_highs: list[SwingPoint] = Field(default_factory=list)
    higher_lows: list[SwingPoint] = Field(default_factory=list)
    lower_highs: list[SwingPoint] = Field(default_factory=list)
    lower_lows: list[SwingPoint] = Field(default_factory=list)
    bos_events: list[BOSEvent] = Field(default_factory=list)
    choch_events: list[CHoCHEvent] = Field(default_factory=list)
    internal_structure: StructureState
    external_structure: StructureState
    current_structure_state: StructureState
    structure_events: list[StructureEvent] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: Decimal = Decimal("0")
