"""Canonical schemas for the Market Liquidity Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class LiquidityKind(StrEnum):
    """Institutional liquidity level classification."""

    PREVIOUS_HIGH = "previous_high"
    PREVIOUS_LOW = "previous_low"
    WEEKLY_HIGH = "weekly_high"
    WEEKLY_LOW = "weekly_low"
    DAILY_HIGH = "daily_high"
    DAILY_LOW = "daily_low"
    SESSION_HIGH = "session_high"
    SESSION_LOW = "session_low"
    INTERNAL_SWING_HIGH = "internal_swing_high"
    INTERNAL_SWING_LOW = "internal_swing_low"
    EQUAL_HIGH = "equal_high"
    EQUAL_LOW = "equal_low"
    BUY_SIDE = "buy_side"
    SELL_SIDE = "sell_side"


class LiquiditySide(StrEnum):
    """Liquidity side bias."""

    BUY_SIDE = "buy_side"
    SELL_SIDE = "sell_side"
    BALANCED = "balanced"
    UNDETERMINED = "undetermined"


class SweepDirection(StrEnum):
    """Liquidity sweep direction."""

    BULLISH = "bullish_sweep"
    BEARISH = "bearish_sweep"


class SweepQuality(StrEnum):
    """Liquidity sweep quality classification."""

    STRONG = "strong"
    WEAK = "weak"
    INDETERMINATE = "indeterminate"


class LiquidityLevel(BaseModel):
    """Single institutional liquidity level."""

    model_config = ConfigDict(frozen=True)

    kind: LiquidityKind
    price: Decimal
    timestamp_utc: datetime
    bar_index: int | None = None
    session: str | None = None
    is_active: bool = True
    strength: Decimal = Decimal("0.5")
    touched_count: int = 1


class EqualLevelCluster(BaseModel):
    """Cluster of equal highs or equal lows."""

    model_config = ConfigDict(frozen=True)

    kind: LiquidityKind
    price: Decimal
    levels: list[LiquidityLevel] = Field(default_factory=list)
    touched_count: int = 0
    is_active: bool = True


class LiquiditySweep(BaseModel):
    """Liquidity sweep event."""

    model_config = ConfigDict(frozen=True)

    direction: SweepDirection
    swept_level: Decimal
    sweep_price: Decimal
    reclaim_price: Decimal
    timestamp_utc: datetime
    bar_index: int
    timeframe: str
    quality: SweepQuality = SweepQuality.INDETERMINATE
    liquidity_kind: LiquidityKind | None = None


class LiquidityGrab(BaseModel):
    """Aggressive rejection after a liquidity sweep."""

    model_config = ConfigDict(frozen=True)

    direction: SweepDirection
    swept_level: Decimal
    sweep_price: Decimal
    rejection_price: Decimal
    timestamp_utc: datetime
    bar_index: int
    timeframe: str
    rejection_ratio: Decimal


class LiquidityZone(BaseModel):
    """Liquidity zone around clustered equal levels."""

    model_config = ConfigDict(frozen=True)

    zone_id: str
    side: LiquiditySide
    upper_bound: Decimal
    lower_bound: Decimal
    anchor_price: Decimal
    cluster_size: int
    timestamp_utc: datetime
    is_active: bool = True


class LiquidityState(BaseModel):
    """Serializable liquidity engine state."""

    active_zones: list[LiquidityZone] = Field(default_factory=list)
    recent_sweeps: list[LiquiditySweep] = Field(default_factory=list)
    bar_count: int = 0


class LiquidityAnalysis(BaseModel):
    """Complete liquidity analysis output."""

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    external_liquidity: list[LiquidityLevel] = Field(default_factory=list)
    internal_liquidity: list[LiquidityLevel] = Field(default_factory=list)
    equal_highs: list[EqualLevelCluster] = Field(default_factory=list)
    equal_lows: list[EqualLevelCluster] = Field(default_factory=list)
    buy_side_liquidity: list[LiquidityLevel] = Field(default_factory=list)
    sell_side_liquidity: list[LiquidityLevel] = Field(default_factory=list)
    sweeps: list[LiquiditySweep] = Field(default_factory=list)
    grabs: list[LiquidityGrab] = Field(default_factory=list)
    zones: list[LiquidityZone] = Field(default_factory=list)
    bias: LiquiditySide = LiquiditySide.UNDETERMINED
    confidence: Decimal = Decimal("0")
    evidence: list[str] = Field(default_factory=list)
    state: LiquidityState = Field(default_factory=LiquidityState)
