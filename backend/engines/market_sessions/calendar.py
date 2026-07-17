"""Weekend, holiday, and market availability resolution."""

from datetime import date, datetime, timedelta

from backend.engines.market_sessions.config import MarketSessionsConfig
from backend.engines.market_sessions.schemas import CalendarContext, MarketAvailability
from backend.engines.market_sessions.timezone import TimezoneNormalizer


WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class CalendarResolver:
    """Resolve calendar context from broker-local time."""

    def __init__(
        self,
        config: MarketSessionsConfig,
        normalizer: TimezoneNormalizer | None = None,
    ) -> None:
        self._config = config
        self._tz = normalizer or TimezoneNormalizer()

    def is_weekend(self, broker_local: datetime) -> bool:
        """Return whether broker-local time falls on a configured weekend day."""
        weekday_name = WEEKDAY_NAMES[broker_local.weekday()]
        return weekday_name in {
            day.lower() for day in self._config.calendar.weekend_days
        }

    def is_holiday(self, broker_local: datetime) -> tuple[bool, str | None]:
        """Return holiday flag and optional name for broker-local date."""
        if not self._config.calendar.holidays.enabled:
            return False, None
        local_date = broker_local.date().isoformat()
        for holiday_date in self._config.calendar.holidays.dates:
            if holiday_date == local_date:
                return True, f"Holiday {local_date}"
        return False, None

    def resolve_calendar_context(
        self,
        timestamp_utc: datetime,
        broker_timezone: str,
    ) -> CalendarContext:
        """Build full calendar context for reference time."""
        broker_local = self._tz.to_broker_local(timestamp_utc, broker_timezone)
        is_weekend = self.is_weekend(broker_local)
        is_holiday, holiday_name = self.is_holiday(broker_local)

        dst_enabled = self._config.calendar.dst.enabled
        is_dst = False
        dst_offset = self._tz.get_dst_offset_minutes(timestamp_utc, broker_timezone)
        if dst_enabled:
            for session_cfg in self._config.sessions.values():
                if session_cfg.enabled and self._tz.is_dst_transition(
                    timestamp_utc,
                    session_cfg.timezone,
                    self._config.calendar.dst.transition_window_hours,
                ):
                    is_dst = True
                    break

        trading_day_id = self._tz.trading_day_id(
            timestamp_utc,
            broker_timezone,
            self._config.broker_day_start_hour,
        )
        week_id = self._tz.week_id(timestamp_utc, broker_timezone)
        month_id = self._tz.month_id(timestamp_utc, broker_timezone)

        return CalendarContext(
            is_weekend=is_weekend,
            is_holiday=is_holiday,
            holiday_name=holiday_name,
            is_dst_transition=is_dst,
            dst_offset_minutes=dst_offset,
            trading_day_id=trading_day_id,
            week_id=week_id,
            month_id=month_id,
        )

    def market_availability(
        self,
        calendar_context: CalendarContext,
        *,
        has_active_session: bool,
    ) -> MarketAvailability:
        """Derive market availability from calendar and session state."""
        if calendar_context.is_holiday:
            partial = self._config.calendar.partial_holiday_sessions
            if not partial:
                return MarketAvailability.CLOSED
        if calendar_context.is_weekend and not self._config.weekend_trading_enabled:
            return MarketAvailability.CLOSED
        if calendar_context.is_holiday and not self._config.calendar.partial_holiday_sessions:
            return MarketAvailability.CLOSED
        if has_active_session:
            return MarketAvailability.OPEN
        if calendar_context.is_weekend or calendar_context.is_holiday:
            return MarketAvailability.OPEN if self._config.weekend_trading_enabled else MarketAvailability.CLOSED
        return MarketAvailability.PRE_OPEN if not has_active_session else MarketAvailability.OPEN

    def sessions_allowed(
        self,
        calendar_context: CalendarContext,
    ) -> bool:
        """Return whether session/kill zone resolution should proceed."""
        if calendar_context.is_weekend and not self._config.weekend_trading_enabled:
            return False
        if calendar_context.is_holiday:
            if not self._config.calendar.partial_holiday_sessions:
                return False
        return True

    def partial_holiday_active_sessions(self) -> set[str]:
        """Sessions permitted on partial holidays."""
        return set(self._config.calendar.partial_holiday_sessions)

    def week_start_weekday(self) -> int:
        """Return weekday index for configured week start."""
        day = self._config.opens.weekly_week_start_day.lower()
        try:
            return WEEKDAY_NAMES.index(day)
        except ValueError:
            return 0

    def month_start_date(
        self,
        broker_local: datetime,
    ) -> date:
        """First day of current month in broker-local calendar."""
        return date(broker_local.year, broker_local.month, 1)

    def week_start_date(
        self,
        broker_local: datetime,
    ) -> date:
        """Configured week start date containing broker_local."""
        target_weekday = self.week_start_weekday()
        delta_days = (broker_local.weekday() - target_weekday) % 7
        return broker_local.date() - timedelta(days=delta_days)
