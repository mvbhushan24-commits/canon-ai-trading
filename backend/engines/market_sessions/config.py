"""Kill Zones & Trading Sessions Engine configuration."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.yaml_loader import load_yaml_config
from backend.engines.market_sessions.exceptions import ConfigInvalidError
from backend.engines.market_sessions.schemas import (
    FilterMode,
    KillZoneId,
    TradingSessionId,
)


class SessionWindowConfig(BaseModel):
    """Single trading session window configuration."""

    enabled: bool = True
    timezone: str = "Europe/London"
    local_start: str = "08:00"
    local_end: str = "17:00"

    @field_validator("local_start", "local_end")
    @classmethod
    def _validate_time_format(cls, value: str) -> str:
        parts = value.strip().split(":")
        if len(parts) != 2:
            msg = f"Invalid time format '{value}', expected HH:MM"
            raise ValueError(msg)
        hour, minute = int(parts[0]), int(parts[1])
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            msg = f"Invalid time value '{value}'"
            raise ValueError(msg)
        return f"{hour:02d}:{minute:02d}"

    @model_validator(mode="after")
    def _validate_window(self) -> "SessionWindowConfig":
        if self.local_start == self.local_end:
            msg = "Session local_start must differ from local_end"
            raise ValueError(msg)
        return self


class KillZoneWindowConfig(BaseModel):
    """Single kill zone window configuration."""

    enabled: bool = True
    parent_session: str = "london"
    utc_start: str = "07:00"
    utc_end: str = "10:00"
    use_dst_adjustment: bool = False

    @field_validator("utc_start", "utc_end")
    @classmethod
    def _validate_time_format(cls, value: str) -> str:
        parts = value.strip().split(":")
        if len(parts) != 2:
            msg = f"Invalid time format '{value}', expected HH:MM"
            raise ValueError(msg)
        hour, minute = int(parts[0]), int(parts[1])
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            msg = f"Invalid time value '{value}'"
            raise ValueError(msg)
        return f"{hour:02d}:{minute:02d}"

    @model_validator(mode="after")
    def _validate_window(self) -> "KillZoneWindowConfig":
        if self.utc_start == self.utc_end:
            msg = "Kill zone utc_start must differ from utc_end"
            raise ValueError(msg)
        return self


class OverlapConfig(BaseModel):
    """Session overlap pair configuration."""

    enabled: bool = True
    sessions: list[str] = Field(default_factory=list)


class SessionPhasesConfig(BaseModel):
    """Session phase duration rules."""

    pre_open_minutes: int = 30
    opening_phase_minutes: int = 60
    closing_phase_minutes: int = 30


class OpensConfig(BaseModel):
    """Period open resolution settings."""

    daily_enabled: bool = True
    daily_require_closed_candle: bool = True
    weekly_enabled: bool = True
    weekly_week_start_day: str = "monday"
    weekly_require_closed_candle: bool = True
    monthly_enabled: bool = True
    monthly_require_closed_candle: bool = True


class SessionExtremesConfig(BaseModel):
    """Session high/low tracking settings."""

    enabled: bool = True
    reset_at_daily_open: bool = True
    cross_validate_liquidity: bool = True


class OpeningRangeConfig(BaseModel):
    """Opening range computation settings."""

    enabled: bool = True
    duration_minutes: int = 30
    min_candles: int = 2
    breakout_buffer_pips: float = 2.0
    sessions: list[str] = Field(default_factory=lambda: ["london", "new_york"])


class InitialBalanceConfig(BaseModel):
    """Initial balance computation settings."""

    enabled: bool = True
    duration_minutes: int = 60
    min_candles: int = 4
    extension_threshold_pips: float = 5.0
    sessions: list[str] = Field(default_factory=lambda: ["london", "new_york"])


class TimeOfDayFilterConfig(BaseModel):
    """Time-of-day filter settings."""

    mode: str = "kill_zone_only"
    allow_list: list[str] = Field(default_factory=list)
    block_list: list[str] = Field(default_factory=lambda: ["sydney"])
    block_weekends: bool = False
    block_holidays: bool = True
    block_outside_sessions: bool = False


class HolidaysConfig(BaseModel):
    """Holiday calendar configuration."""

    enabled: bool = True
    dates: list[str] = Field(default_factory=list)
    file: str | None = None


class DstConfig(BaseModel):
    """DST detection configuration."""

    enabled: bool = True
    transition_window_hours: int = 24


class CalendarConfig(BaseModel):
    """Weekend, holiday, and DST settings."""

    weekend_days: list[str] = Field(default_factory=lambda: ["saturday", "sunday"])
    holidays: HolidaysConfig = Field(default_factory=HolidaysConfig)
    partial_holiday_sessions: list[str] = Field(default_factory=list)
    dst: DstConfig = Field(default_factory=DstConfig)


class TransitionsConfig(BaseModel):
    """Transition detection and forecast settings."""

    forecast_hours: int = 24
    imminent_minutes: int = 15
    recent_lookback_hours: int = 4


class VolatilityConfig(BaseModel):
    """Volatility profiling settings."""

    enabled: bool = True
    baseline_lookback_sessions: int = 20
    low_percentile: int = 33
    high_percentile: int = 67
    min_candles_for_profile: int = 10


class LiquidityScoringConfig(BaseModel):
    """Liquidity scoring settings."""

    use_volume: bool = True
    use_spread: bool = True
    use_liquidity_engine: bool = True
    low_volume_percentile: int = 25
    high_volume_percentile: int = 75


class HistoricalPerformanceConfig(BaseModel):
    """Historical performance scoring settings."""

    enabled: bool = False
    lookback_days: int = 30
    min_samples: int = 10
    metrics: list[str] = Field(
        default_factory=lambda: [
            "or_breakout_rate",
            "ib_extension_rate",
            "session_range_expansion",
        ],
    )


class QualityWeights(BaseModel):
    """Composite quality scoring weights."""

    session_quality: float = 0.20
    kill_zone_quality: float = 0.20
    overlap_quality: float = 0.15
    volatility: float = 0.15
    liquidity_availability: float = 0.15
    historical_performance: float = 0.15

    @model_validator(mode="after")
    def _validate_sum(self) -> "QualityWeights":
        total = (
            self.session_quality
            + self.kill_zone_quality
            + self.overlap_quality
            + self.volatility
            + self.liquidity_availability
            + self.historical_performance
        )
        if abs(total - 1.0) > 0.001:
            msg = f"quality_weights must sum to 1.0 (±0.001), got {total}"
            raise ValueError(msg)
        return self


class MarketSessionsConfig(BaseModel):
    """Configuration for kill zones and trading session analysis."""

    enabled: bool = True
    timeframes: list[str] = Field(default_factory=lambda: ["M5", "M15", "H1"])
    min_candles: int = 20
    lookback: int = 500
    pip_size: float = 0.1
    broker_timezone: str = "Europe/Nicosia"
    broker_day_start_hour: int = 0
    weekend_trading_enabled: bool = True
    allow_partial_analysis: bool = True
    kill_zones_require_active_session: bool = False
    session_priority: list[str] = Field(
        default_factory=lambda: ["london", "new_york", "tokyo", "sydney"],
    )
    sessions: dict[str, SessionWindowConfig] = Field(default_factory=dict)
    kill_zones: dict[str, KillZoneWindowConfig] = Field(default_factory=dict)
    overlaps: dict[str, OverlapConfig] = Field(default_factory=dict)
    session_phases: SessionPhasesConfig = Field(default_factory=SessionPhasesConfig)
    opens: OpensConfig = Field(default_factory=OpensConfig)
    session_extremes: SessionExtremesConfig = Field(default_factory=SessionExtremesConfig)
    opening_range: OpeningRangeConfig = Field(default_factory=OpeningRangeConfig)
    initial_balance: InitialBalanceConfig = Field(default_factory=InitialBalanceConfig)
    time_of_day_filter: TimeOfDayFilterConfig = Field(
        default_factory=TimeOfDayFilterConfig,
    )
    calendar: CalendarConfig = Field(default_factory=CalendarConfig)
    transitions: TransitionsConfig = Field(default_factory=TransitionsConfig)
    volatility: VolatilityConfig = Field(default_factory=VolatilityConfig)
    liquidity: LiquidityScoringConfig = Field(default_factory=LiquidityScoringConfig)
    historical_performance: HistoricalPerformanceConfig = Field(
        default_factory=HistoricalPerformanceConfig,
    )
    min_quality_score: float = 0.4
    high_quality_threshold: float = 0.7
    quality_weights: QualityWeights = Field(default_factory=QualityWeights)
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("min_candles", "lookback")
    @classmethod
    def _validate_positive(cls, value: int) -> int:
        if value < 1:
            msg = "min_candles and lookback must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("broker_day_start_hour")
    @classmethod
    def _validate_hour(cls, value: int) -> int:
        if not 0 <= value <= 23:
            msg = "broker_day_start_hour must be between 0 and 23"
            raise ValueError(msg)
        return value

    @field_validator("timeframes")
    @classmethod
    def _validate_timeframes(cls, value: list[str]) -> list[str]:
        if not value:
            msg = "timeframes must be a non-empty list"
            raise ValueError(msg)
        return [item.strip().upper() for item in value if str(item).strip()]

    @field_validator("time_of_day_filter", mode="before")
    @classmethod
    def _normalize_filter_mode(cls, value: object) -> object:
        if isinstance(value, dict) and "mode" in value:
            value = dict(value)
            value["mode"] = str(value["mode"]).strip().lower()
        return value

    @model_validator(mode="after")
    def _validate_defaults(self) -> "MarketSessionsConfig":
        if not self.sessions:
            self.sessions = _default_sessions()
        if not self.kill_zones:
            self.kill_zones = _default_kill_zones()
        if not self.overlaps:
            self.overlaps = _default_overlaps()
        return self


def _default_sessions() -> dict[str, SessionWindowConfig]:
    return {
        "sydney": SessionWindowConfig(
            timezone="Australia/Sydney",
            local_start="07:00",
            local_end="16:00",
        ),
        "tokyo": SessionWindowConfig(
            timezone="Asia/Tokyo",
            local_start="09:00",
            local_end="18:00",
        ),
        "london": SessionWindowConfig(
            timezone="Europe/London",
            local_start="08:00",
            local_end="17:00",
        ),
        "new_york": SessionWindowConfig(
            timezone="America/New_York",
            local_start="08:00",
            local_end="17:00",
        ),
    }


def _default_kill_zones() -> dict[str, KillZoneWindowConfig]:
    return {
        "asian": KillZoneWindowConfig(
            parent_session="tokyo",
            utc_start="00:00",
            utc_end="03:00",
        ),
        "london_open": KillZoneWindowConfig(
            parent_session="london",
            utc_start="07:00",
            utc_end="10:00",
        ),
        "new_york": KillZoneWindowConfig(
            parent_session="new_york",
            utc_start="12:00",
            utc_end="15:00",
        ),
        "london_close": KillZoneWindowConfig(
            parent_session="london",
            utc_start="15:00",
            utc_end="17:00",
        ),
    }


def _default_overlaps() -> dict[str, OverlapConfig]:
    return {
        "sydney_tokyo": OverlapConfig(sessions=["sydney", "tokyo"]),
        "london_new_york": OverlapConfig(sessions=["london", "new_york"]),
    }


def _parse_timeframes(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [item.strip().upper() for item in raw if str(item).strip()]
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_session_config(raw: object) -> SessionWindowConfig | None:
    if not isinstance(raw, dict):
        return None
    return SessionWindowConfig(
        enabled=bool(raw.get("enabled", True)),
        timezone=str(raw.get("timezone", "Europe/London")),
        local_start=str(raw.get("local_start", "08:00")),
        local_end=str(raw.get("local_end", "17:00")),
    )


def _parse_kill_zone_config(raw: object) -> KillZoneWindowConfig | None:
    if not isinstance(raw, dict):
        return None
    return KillZoneWindowConfig(
        enabled=bool(raw.get("enabled", True)),
        parent_session=str(raw.get("parent_session", "london")),
        utc_start=str(raw.get("utc_start", "07:00")),
        utc_end=str(raw.get("utc_end", "10:00")),
        use_dst_adjustment=bool(raw.get("use_dst_adjustment", False)),
    )


def _parse_overlap_config(raw: object) -> OverlapConfig | None:
    if not isinstance(raw, dict):
        return None
    return OverlapConfig(
        enabled=bool(raw.get("enabled", True)),
        sessions=[str(item) for item in raw.get("sessions", [])],
    )


def _parse_quality_weights(raw: object) -> QualityWeights | None:
    if not isinstance(raw, dict):
        return None
    return QualityWeights(
        session_quality=float(raw.get("session_quality", 0.20)),
        kill_zone_quality=float(raw.get("kill_zone_quality", 0.20)),
        overlap_quality=float(raw.get("overlap_quality", 0.15)),
        volatility=float(raw.get("volatility", 0.15)),
        liquidity_availability=float(raw.get("liquidity_availability", 0.15)),
        historical_performance=float(raw.get("historical_performance", 0.15)),
    )


def _load_holiday_dates(calendar_yaml: dict) -> list[str]:
    holidays_yaml = calendar_yaml.get("holidays", {})
    if not isinstance(holidays_yaml, dict):
        return []
    dates = list(holidays_yaml.get("dates", []))
    holiday_file = holidays_yaml.get("file")
    if holiday_file:
        file_path = Path(str(holiday_file))
        if file_path.exists():
            file_data = load_yaml_config(file_path)
            if isinstance(file_data, list):
                dates.extend(str(item) for item in file_data)
            elif isinstance(file_data, dict):
                file_dates = file_data.get("dates", [])
                if isinstance(file_dates, list):
                    dates.extend(str(item) for item in file_dates)
    return [str(item) for item in dates]


def load_market_sessions_config(
    yaml_path: Path | None = None,
) -> MarketSessionsConfig:
    """Load market sessions configuration from YAML."""
    config_path = yaml_path or Path("config/settings.yaml")
    yaml_data = load_yaml_config(config_path)
    ms_yaml = yaml_data.get("market_sessions", {})
    if not isinstance(ms_yaml, dict):
        ms_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("market_sessions", True))
    if "enabled" in ms_yaml:
        enabled = bool(ms_yaml["enabled"])

    sessions: dict[str, SessionWindowConfig] = {}
    sessions_yaml = ms_yaml.get("sessions", {})
    if isinstance(sessions_yaml, dict):
        for key, value in sessions_yaml.items():
            parsed = _parse_session_config(value)
            if parsed is not None:
                sessions[key] = parsed

    kill_zones: dict[str, KillZoneWindowConfig] = {}
    kill_zones_yaml = ms_yaml.get("kill_zones", {})
    if isinstance(kill_zones_yaml, dict):
        require_active = bool(kill_zones_yaml.get("require_active_session", False))
        for key, value in kill_zones_yaml.items():
            if key == "require_active_session":
                continue
            parsed = _parse_kill_zone_config(value)
            if parsed is not None:
                kill_zones[key] = parsed
    else:
        require_active = False

    overlaps: dict[str, OverlapConfig] = {}
    overlaps_yaml = ms_yaml.get("overlaps", {})
    if isinstance(overlaps_yaml, dict):
        for key, value in overlaps_yaml.items():
            parsed = _parse_overlap_config(value)
            if parsed is not None:
                overlaps[key] = parsed

    session_phases_yaml = ms_yaml.get("session_phases", {})
    if not isinstance(session_phases_yaml, dict):
        session_phases_yaml = {}
    session_phases = SessionPhasesConfig(
        pre_open_minutes=int(session_phases_yaml.get("pre_open_minutes", 30)),
        opening_phase_minutes=int(session_phases_yaml.get("opening_phase_minutes", 60)),
        closing_phase_minutes=int(session_phases_yaml.get("closing_phase_minutes", 30)),
    )

    priority_yaml = ms_yaml.get("session_priority", {})
    if isinstance(priority_yaml, dict):
        session_priority = [str(item) for item in priority_yaml.get("order", [])]
    elif isinstance(priority_yaml, list):
        session_priority = [str(item) for item in priority_yaml]
    else:
        session_priority = ["london", "new_york", "tokyo", "sydney"]

    opens_yaml = ms_yaml.get("opens", {})
    if not isinstance(opens_yaml, dict):
        opens_yaml = {}
    daily_yaml = opens_yaml.get("daily", {})
    weekly_yaml = opens_yaml.get("weekly", {})
    monthly_yaml = opens_yaml.get("monthly", {})
    if not isinstance(daily_yaml, dict):
        daily_yaml = {}
    if not isinstance(weekly_yaml, dict):
        weekly_yaml = {}
    if not isinstance(monthly_yaml, dict):
        monthly_yaml = {}
    opens = OpensConfig(
        daily_enabled=bool(daily_yaml.get("enabled", True)),
        daily_require_closed_candle=bool(daily_yaml.get("require_closed_candle", True)),
        weekly_enabled=bool(weekly_yaml.get("enabled", True)),
        weekly_week_start_day=str(weekly_yaml.get("week_start_day", "monday")),
        weekly_require_closed_candle=bool(weekly_yaml.get("require_closed_candle", True)),
        monthly_enabled=bool(monthly_yaml.get("enabled", True)),
        monthly_require_closed_candle=bool(
            monthly_yaml.get("require_closed_candle", True),
        ),
    )

    extremes_yaml = ms_yaml.get("session_extremes", {})
    if not isinstance(extremes_yaml, dict):
        extremes_yaml = {}
    session_extremes = SessionExtremesConfig(
        enabled=bool(extremes_yaml.get("enabled", True)),
        reset_at_daily_open=bool(extremes_yaml.get("reset_at_daily_open", True)),
        cross_validate_liquidity=bool(
            extremes_yaml.get("cross_validate_liquidity", True),
        ),
    )

    or_yaml = ms_yaml.get("opening_range", {})
    if not isinstance(or_yaml, dict):
        or_yaml = {}
    opening_range = OpeningRangeConfig(
        enabled=bool(or_yaml.get("enabled", True)),
        duration_minutes=int(or_yaml.get("duration_minutes", 30)),
        min_candles=int(or_yaml.get("min_candles", 2)),
        breakout_buffer_pips=float(or_yaml.get("breakout_buffer_pips", 2.0)),
        sessions=[str(item) for item in or_yaml.get("sessions", ["london", "new_york"])],
    )

    ib_yaml = ms_yaml.get("initial_balance", {})
    if not isinstance(ib_yaml, dict):
        ib_yaml = {}
    initial_balance = InitialBalanceConfig(
        enabled=bool(ib_yaml.get("enabled", True)),
        duration_minutes=int(ib_yaml.get("duration_minutes", 60)),
        min_candles=int(ib_yaml.get("min_candles", 4)),
        extension_threshold_pips=float(ib_yaml.get("extension_threshold_pips", 5.0)),
        sessions=[str(item) for item in ib_yaml.get("sessions", ["london", "new_york"])],
    )

    filter_yaml = ms_yaml.get("time_of_day_filter", {})
    if not isinstance(filter_yaml, dict):
        filter_yaml = {}
    time_of_day_filter = TimeOfDayFilterConfig(
        mode=str(filter_yaml.get("mode", "kill_zone_only")),
        allow_list=[str(item) for item in filter_yaml.get("allow_list", [])],
        block_list=[str(item) for item in filter_yaml.get("block_list", ["sydney"])],
        block_weekends=bool(filter_yaml.get("block_weekends", False)),
        block_holidays=bool(filter_yaml.get("block_holidays", True)),
        block_outside_sessions=bool(filter_yaml.get("block_outside_sessions", False)),
    )

    calendar_yaml = ms_yaml.get("calendar", {})
    if not isinstance(calendar_yaml, dict):
        calendar_yaml = {}
    holidays_yaml = calendar_yaml.get("holidays", {})
    if not isinstance(holidays_yaml, dict):
        holidays_yaml = {}
    dst_yaml = calendar_yaml.get("dst", {})
    if not isinstance(dst_yaml, dict):
        dst_yaml = {}
    calendar = CalendarConfig(
        weekend_days=[
            str(item).lower()
            for item in calendar_yaml.get("weekend_days", ["saturday", "sunday"])
        ],
        holidays=HolidaysConfig(
            enabled=bool(holidays_yaml.get("enabled", True)),
            dates=_load_holiday_dates(calendar_yaml),
            file=holidays_yaml.get("file"),
        ),
        partial_holiday_sessions=[
            str(item) for item in calendar_yaml.get("partial_holiday_sessions", [])
        ],
        dst=DstConfig(
            enabled=bool(dst_yaml.get("enabled", True)),
            transition_window_hours=int(dst_yaml.get("transition_window_hours", 24)),
        ),
    )

    transitions_yaml = ms_yaml.get("transitions", {})
    if not isinstance(transitions_yaml, dict):
        transitions_yaml = {}
    transitions = TransitionsConfig(
        forecast_hours=int(transitions_yaml.get("forecast_hours", 24)),
        imminent_minutes=int(transitions_yaml.get("imminent_minutes", 15)),
        recent_lookback_hours=int(transitions_yaml.get("recent_lookback_hours", 4)),
    )

    volatility_yaml = ms_yaml.get("volatility", {})
    if not isinstance(volatility_yaml, dict):
        volatility_yaml = {}
    volatility = VolatilityConfig(
        enabled=bool(volatility_yaml.get("enabled", True)),
        baseline_lookback_sessions=int(
            volatility_yaml.get("baseline_lookback_sessions", 20),
        ),
        low_percentile=int(volatility_yaml.get("low_percentile", 33)),
        high_percentile=int(volatility_yaml.get("high_percentile", 67)),
        min_candles_for_profile=int(volatility_yaml.get("min_candles_for_profile", 10)),
    )

    liquidity_yaml = ms_yaml.get("liquidity", {})
    if not isinstance(liquidity_yaml, dict):
        liquidity_yaml = {}
    liquidity = LiquidityScoringConfig(
        use_volume=bool(liquidity_yaml.get("use_volume", True)),
        use_spread=bool(liquidity_yaml.get("use_spread", True)),
        use_liquidity_engine=bool(liquidity_yaml.get("use_liquidity_engine", True)),
        low_volume_percentile=int(liquidity_yaml.get("low_volume_percentile", 25)),
        high_volume_percentile=int(liquidity_yaml.get("high_volume_percentile", 75)),
    )

    hist_yaml = ms_yaml.get("historical_performance", {})
    if not isinstance(hist_yaml, dict):
        hist_yaml = {}
    historical_performance = HistoricalPerformanceConfig(
        enabled=bool(hist_yaml.get("enabled", False)),
        lookback_days=int(hist_yaml.get("lookback_days", 30)),
        min_samples=int(hist_yaml.get("min_samples", 10)),
        metrics=[str(item) for item in hist_yaml.get("metrics", [])]
        or [
            "or_breakout_rate",
            "ib_extension_rate",
            "session_range_expansion",
        ],
    )

    quality_weights = _parse_quality_weights(ms_yaml.get("quality_weights"))

    try:
        return MarketSessionsConfig(
            enabled=enabled,
            timeframes=_parse_timeframes(ms_yaml.get("timeframes")) or ["M5", "M15", "H1"],
            min_candles=int(ms_yaml.get("min_candles", 20)),
            lookback=int(ms_yaml.get("lookback", 500)),
            pip_size=float(ms_yaml.get("pip_size", 0.1)),
            broker_timezone=str(ms_yaml.get("broker_timezone", "Europe/Nicosia")),
            broker_day_start_hour=int(ms_yaml.get("broker_day_start_hour", 0)),
            weekend_trading_enabled=bool(ms_yaml.get("weekend_trading_enabled", True)),
            allow_partial_analysis=bool(ms_yaml.get("allow_partial_analysis", True)),
            kill_zones_require_active_session=require_active,
            session_priority=session_priority or ["london", "new_york", "tokyo", "sydney"],
            sessions=sessions or _default_sessions(),
            kill_zones=kill_zones or _default_kill_zones(),
            overlaps=overlaps or _default_overlaps(),
            session_phases=session_phases,
            opens=opens,
            session_extremes=session_extremes,
            opening_range=opening_range,
            initial_balance=initial_balance,
            time_of_day_filter=time_of_day_filter,
            calendar=calendar,
            transitions=transitions,
            volatility=volatility,
            liquidity=liquidity,
            historical_performance=historical_performance,
            min_quality_score=float(ms_yaml.get("min_quality_score", 0.4)),
            high_quality_threshold=float(ms_yaml.get("high_quality_threshold", 0.7)),
            quality_weights=quality_weights or QualityWeights(),
            yaml_config_path=str(config_path),
        )
    except ValueError as exc:
        raise ConfigInvalidError(str(exc)) from exc


def validate_config_timezones(config: MarketSessionsConfig) -> None:
    """Validate IANA timezones in session and broker configuration."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(config.broker_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigInvalidError(
            f"Invalid broker timezone: {config.broker_timezone}",
        ) from exc

    for session_id, session_cfg in config.sessions.items():
        if not session_cfg.enabled:
            continue
        try:
            ZoneInfo(session_cfg.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ConfigInvalidError(
                f"Invalid session timezone for {session_id}: {session_cfg.timezone}",
            ) from exc

    allowed_sessions = {item.value for item in TradingSessionId}
    allowed_kill_zones = {item.value for item in KillZoneId}
    allowed_filters = {item.value for item in FilterMode}

    if config.time_of_day_filter.mode not in allowed_filters:
        raise ConfigInvalidError(
            f"Invalid filter mode: {config.time_of_day_filter.mode}",
        )

    for overlap_id, overlap_cfg in config.overlaps.items():
        if not overlap_cfg.enabled:
            continue
        for session_name in overlap_cfg.sessions:
            if session_name not in allowed_sessions:
                raise ConfigInvalidError(
                    f"Unknown session '{session_name}' in overlap '{overlap_id}'",
                )

    for kz_id, kz_cfg in config.kill_zones.items():
        if kz_cfg.parent_session not in allowed_sessions:
            raise ConfigInvalidError(
                f"Unknown parent session '{kz_cfg.parent_session}' for kill zone '{kz_id}'",
            )
        if kz_id not in allowed_kill_zones:
            raise ConfigInvalidError(f"Unknown kill zone id: {kz_id}")
