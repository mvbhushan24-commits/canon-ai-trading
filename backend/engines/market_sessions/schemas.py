"""Canonical schemas for the Kill Zones & Trading Sessions Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TradingSessionId(StrEnum):
    """Institutional trading session identifiers."""

    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"


class KillZoneId(StrEnum):
    """ICT-style kill zone identifiers."""

    ASIAN = "asian"
    LONDON_OPEN = "london_open"
    NEW_YORK = "new_york"
    LONDON_CLOSE = "london_close"


class SessionPhase(StrEnum):
    """Session lifecycle phase."""

    PRE_OPEN = "pre_open"
    OPENING = "opening"
    MID = "mid"
    CLOSING = "closing"
    INACTIVE = "inactive"


class TransitionType(StrEnum):
    """Session or kill zone boundary transition types."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    KILL_ZONE_START = "kill_zone_start"
    KILL_ZONE_END = "kill_zone_end"
    OVERLAP_START = "overlap_start"
    OVERLAP_END = "overlap_end"


class MarketAvailability(StrEnum):
    """Broker calendar market availability."""

    OPEN = "open"
    CLOSED = "closed"
    PRE_OPEN = "pre_open"
    POST_CLOSE = "post_close"


class VolatilityProfile(StrEnum):
    """Relative volatility classification."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNDETERMINED = "undetermined"


class LiquidityAvailability(StrEnum):
    """Relative liquidity availability."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNDETERMINED = "undetermined"


class SessionQualityTier(StrEnum):
    """Session / kill zone quality tier."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FilterMode(StrEnum):
    """Time-of-day filter mode."""

    ALLOW_LIST = "allow_list"
    BLOCK_LIST = "block_list"
    KILL_ZONE_ONLY = "kill_zone_only"
    DISABLED = "disabled"


class PeriodType(StrEnum):
    """Period open type."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BreakoutDirection(StrEnum):
    """Opening range breakout direction."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NONE = "none"
    UNDETERMINED = "undetermined"


class MarketSessionsEventKind(StrEnum):
    """Session timeline event types."""

    SESSION_STARTED = "SessionStarted"
    SESSION_ENDED = "SessionEnded"
    KILL_ZONE_STARTED = "KillZoneStarted"
    KILL_ZONE_ENDED = "KillZoneEnded"
    KILL_ZONE_ENTERED = "KillZoneEntered"
    KILL_ZONE_EXITED = "KillZoneExited"
    OVERLAP_STARTED = "OverlapStarted"
    OVERLAP_ENDED = "OverlapEnded"
    DAILY_OPEN_RESOLVED = "DailyOpenResolved"
    WEEKLY_OPEN_RESOLVED = "WeeklyOpenResolved"
    MONTHLY_OPEN_RESOLVED = "MonthlyOpenResolved"
    SESSION_HIGH_UPDATED = "SessionHighUpdated"
    SESSION_LOW_UPDATED = "SessionLowUpdated"
    OPENING_RANGE_COMPLETE = "OpeningRangeComplete"
    OPENING_RANGE_BREAKOUT = "OpeningRangeBreakout"
    INITIAL_BALANCE_COMPLETE = "InitialBalanceComplete"
    INITIAL_BALANCE_EXTENSION = "InitialBalanceExtension"
    TIME_FILTER_BLOCKED = "TimeFilterBlocked"
    WEEKEND_DETECTED = "WeekendDetected"
    HOLIDAY_DETECTED = "HolidayDetected"
    DST_TRANSITION = "DSTTransition"
    SESSION_QUALITY_UPDATED = "SessionQualityUpdated"
    SESSION_TRANSITION_DETECTED = "SessionTransitionDetected"
    SESSION_ANALYSIS_UPDATED = "SessionAnalysisUpdated"


SESSION_DISPLAY_NAMES: dict[TradingSessionId, str] = {
    TradingSessionId.SYDNEY: "Sydney Session",
    TradingSessionId.TOKYO: "Tokyo Session",
    TradingSessionId.LONDON: "London Session",
    TradingSessionId.NEW_YORK: "New York Session",
}

KILL_ZONE_DISPLAY_NAMES: dict[KillZoneId, str] = {
    KillZoneId.ASIAN: "Asian Kill Zone",
    KillZoneId.LONDON_OPEN: "London Open Kill Zone",
    KillZoneId.NEW_YORK: "New York Kill Zone",
    KillZoneId.LONDON_CLOSE: "London Close Kill Zone",
}


class TradingSessionState(BaseModel):
    """Per-session state at reference time."""

    model_config = ConfigDict(frozen=True)

    session_id: TradingSessionId
    display_name: str
    is_active: bool
    phase: SessionPhase
    window_start_utc: datetime
    window_end_utc: datetime
    elapsed_minutes: int
    remaining_minutes: int
    quality: SessionQualityTier
    quality_score: Decimal
    volatility_profile: VolatilityProfile
    evidence: list[str] = Field(default_factory=list)


class KillZoneState(BaseModel):
    """Per-kill-zone state at reference time."""

    model_config = ConfigDict(frozen=True)

    kill_zone_id: KillZoneId
    display_name: str
    parent_session: TradingSessionId
    is_active: bool
    window_start_utc: datetime
    window_end_utc: datetime
    elapsed_minutes: int
    remaining_minutes: int
    quality: SessionQualityTier
    quality_score: Decimal
    volatility_profile: VolatilityProfile
    liquidity_score: Decimal
    historical_score: Decimal
    evidence: list[str] = Field(default_factory=list)


class SessionOverlap(BaseModel):
    """Concurrent session overlap window."""

    model_config = ConfigDict(frozen=True)

    overlap_id: str
    sessions: list[TradingSessionId]
    window_start_utc: datetime
    window_end_utc: datetime
    is_active: bool
    quality: SessionQualityTier
    quality_score: Decimal
    volatility_profile: VolatilityProfile
    evidence: list[str] = Field(default_factory=list)


class SessionTransition(BaseModel):
    """Session or kill zone boundary crossing."""

    model_config = ConfigDict(frozen=True)

    transition_id: str
    session_id: TradingSessionId | None = None
    kill_zone_id: KillZoneId | None = None
    overlap_id: str | None = None
    transition_type: TransitionType
    transition_time_utc: datetime
    from_phase: SessionPhase
    to_phase: SessionPhase
    is_imminent: bool = False


class PeriodOpen(BaseModel):
    """Daily, weekly, or monthly open resolution."""

    model_config = ConfigDict(frozen=True)

    period_type: PeriodType
    open_price: Decimal
    open_time_utc: datetime
    bar_index: int | None = None
    broker_midnight_utc: datetime | None = None
    is_confirmed: bool
    evidence: list[str] = Field(default_factory=list)


class SessionExtreme(BaseModel):
    """Session high/low for current trading day."""

    model_config = ConfigDict(frozen=True)

    session_id: TradingSessionId
    session_high: Decimal
    session_low: Decimal
    high_time_utc: datetime
    low_time_utc: datetime
    range_size_pips: Decimal
    is_complete: bool


class OpeningRange(BaseModel):
    """Post-open price range for a session."""

    model_config = ConfigDict(frozen=True)

    range_id: str
    session_id: TradingSessionId
    high: Decimal
    low: Decimal
    midpoint: Decimal
    range_size_pips: Decimal
    formation_start_utc: datetime
    formation_end_utc: datetime
    duration_minutes: int
    is_complete: bool
    breakout_direction: BreakoutDirection | None = None
    quality: SessionQualityTier
    strength: Decimal
    evidence: list[str] = Field(default_factory=list)


class InitialBalance(BaseModel):
    """Initial balance range for a session."""

    model_config = ConfigDict(frozen=True)

    balance_id: str
    session_id: TradingSessionId
    high: Decimal
    low: Decimal
    midpoint: Decimal
    range_size_pips: Decimal
    formation_start_utc: datetime
    formation_end_utc: datetime
    duration_minutes: int
    is_complete: bool
    extension_high: Decimal | None = None
    extension_low: Decimal | None = None
    quality: SessionQualityTier
    strength: Decimal
    evidence: list[str] = Field(default_factory=list)


class TimeOfDayFilter(BaseModel):
    """Allow/block evaluation for downstream gating."""

    model_config = ConfigDict(frozen=True)

    filter_mode: FilterMode
    is_allowed: bool
    active_windows: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    next_allowed_utc: datetime | None = None


class CalendarContext(BaseModel):
    """Weekend, holiday, DST, and trading period identifiers."""

    model_config = ConfigDict(frozen=True)

    is_weekend: bool
    is_holiday: bool
    holiday_name: str | None = None
    is_dst_transition: bool
    dst_offset_minutes: int
    trading_day_id: str
    week_id: str
    month_id: str


class MarketSessionsState(BaseModel):
    """Serializable continuity state between analysis cycles."""

    last_primary_session: TradingSessionId | None = None
    last_session_phase: SessionPhase = SessionPhase.INACTIVE
    session_extremes_cache: dict[str, SessionExtreme] = Field(default_factory=dict)
    active_opening_ranges: dict[str, OpeningRange] = Field(default_factory=dict)
    active_initial_balances: dict[str, InitialBalance] = Field(default_factory=dict)
    last_daily_open: PeriodOpen | None = None
    last_weekly_open: PeriodOpen | None = None
    last_monthly_open: PeriodOpen | None = None
    last_analysis_utc: datetime | None = None
    bar_count: int = 0
    active_session_ids: list[TradingSessionId] = Field(default_factory=list)
    active_kill_zone_ids: list[KillZoneId] = Field(default_factory=list)
    active_overlap_ids: list[str] = Field(default_factory=list)
    was_weekend: bool = False
    was_holiday: bool = False
    last_quality_tier: SessionQualityTier | None = None
    last_quality_score: Decimal | None = None


class MarketSessionsEvent(BaseModel):
    """Timeline event detected during analysis."""

    model_config = ConfigDict(frozen=True)

    kind: MarketSessionsEventKind
    timestamp_utc: datetime
    description: str
    session_id: TradingSessionId | None = None
    kill_zone_id: KillZoneId | None = None
    overlap_id: str | None = None


class SessionAnalysis(BaseModel):
    """Complete session and kill zone analysis output."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    broker_timezone: str
    market_availability: MarketAvailability
    active_sessions: list[TradingSessionState]
    primary_session: TradingSessionId | None
    session_phase: SessionPhase
    kill_zones: list[KillZoneState]
    active_kill_zones: list[KillZoneState]
    overlaps: list[SessionOverlap]
    next_transition: SessionTransition | None
    recent_transitions: list[SessionTransition]
    daily_open: PeriodOpen | None
    weekly_open: PeriodOpen | None
    monthly_open: PeriodOpen | None
    session_extremes: list[SessionExtreme]
    opening_range: OpeningRange | None
    initial_balance: InitialBalance | None
    time_of_day_filter: TimeOfDayFilter
    calendar_context: CalendarContext
    volatility_profile: VolatilityProfile
    liquidity_availability: LiquidityAvailability
    quality: SessionQualityTier
    confidence: Decimal
    strength: Decimal
    evidence: list[str] = Field(default_factory=list)
    state: MarketSessionsState
    events: list[MarketSessionsEvent] = Field(default_factory=list)
