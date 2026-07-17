"""Broker timezone normalization and UTC window resolution."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.engines.market_sessions.exceptions import InvalidTimezoneError


def validate_timezone(tz_name: str) -> ZoneInfo:
    """Return ZoneInfo for a valid IANA timezone or raise."""
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise InvalidTimezoneError(
            f"Unrecognized IANA timezone: {tz_name}",
            details={"timezone": tz_name},
        ) from exc


def ensure_utc(timestamp: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC."""
    if timestamp.tzinfo is None:
        raise InvalidTimezoneError("Timestamp must be timezone-aware")
    return timestamp.astimezone(UTC)


class TimezoneNormalizer:
    """Broker and session timezone normalization utilities."""

    def to_broker_local(self, timestamp_utc: datetime, broker_timezone: str) -> datetime:
        """Convert UTC timestamp to broker-local time."""
        utc_time = ensure_utc(timestamp_utc)
        tz = validate_timezone(broker_timezone)
        return utc_time.astimezone(tz)

    def parse_hhmm(self, value: str) -> time:
        """Parse HH:MM string to time."""
        hour, minute = value.split(":")
        return time(hour=int(hour), minute=int(minute))

    def combine_local(
        self,
        local_date: date,
        local_time: time,
        tz_name: str,
    ) -> datetime:
        """Combine local date/time in timezone, returning UTC."""
        tz = validate_timezone(tz_name)
        local_dt = datetime(
            local_date.year,
            local_date.month,
            local_date.day,
            local_time.hour,
            local_time.minute,
            tzinfo=tz,
        )
        return local_dt.astimezone(UTC)

    def resolve_local_window_utc(
        self,
        reference_utc: datetime,
        tz_name: str,
        local_start: str,
        local_end: str,
    ) -> tuple[datetime, datetime]:
        """Resolve a local-time session window containing reference_utc."""
        utc_ref = ensure_utc(reference_utc)
        tz = validate_timezone(tz_name)
        local_ref = utc_ref.astimezone(tz)
        start_t = self.parse_hhmm(local_start)
        end_t = self.parse_hhmm(local_end)
        wraps = end_t <= start_t

        candidates: list[tuple[datetime, datetime]] = []
        for day_offset in (-1, 0, 1):
            base_date = local_ref.date() + timedelta(days=day_offset)
            start_utc = self.combine_local(base_date, start_t, tz_name)
            end_date = base_date if not wraps else base_date + timedelta(days=1)
            end_utc = self.combine_local(end_date, end_t, tz_name)
            if end_utc <= start_utc:
                end_utc += timedelta(days=1)
            candidates.append((start_utc, end_utc))

        for start_utc, end_utc in candidates:
            if start_utc <= utc_ref < end_utc:
                return start_utc, end_utc

        future = [
            (start, end)
            for start, end in candidates
            if start > utc_ref
        ]
        if future:
            return min(future, key=lambda item: item[0])
        return max(candidates, key=lambda item: item[0])

    def resolve_utc_window(
        self,
        reference_utc: datetime,
        utc_start: str,
        utc_end: str,
    ) -> tuple[datetime, datetime]:
        """Resolve fixed UTC time-of-day window for reference date."""
        utc_ref = ensure_utc(reference_utc)
        start_t = self.parse_hhmm(utc_start)
        end_t = self.parse_hhmm(utc_end)
        wraps = end_t <= start_t

        ref_date = utc_ref.date()
        start_utc = datetime.combine(ref_date, start_t, tzinfo=UTC)
        end_date = ref_date if not wraps else ref_date + timedelta(days=1)
        end_utc = datetime.combine(end_date, end_t, tzinfo=UTC)
        if end_utc <= start_utc:
            end_utc += timedelta(days=1)

        if wraps:
            if utc_ref.time() < end_t:
                start_utc -= timedelta(days=1)
                end_utc = datetime.combine(ref_date, end_t, tzinfo=UTC)
            elif utc_ref.time() >= start_t:
                end_utc = datetime.combine(ref_date + timedelta(days=1), end_t, tzinfo=UTC)
        elif utc_ref < start_utc:
            start_utc -= timedelta(days=1)
            end_utc -= timedelta(days=1)
        elif utc_ref >= end_utc:
            start_utc += timedelta(days=1)
            end_utc += timedelta(days=1)

        return start_utc, end_utc

    def is_time_in_window(
        self,
        reference_utc: datetime,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> bool:
        """Return whether reference time falls within [start, end)."""
        utc_ref = ensure_utc(reference_utc)
        return window_start_utc <= utc_ref < window_end_utc

    def minutes_between(self, start_utc: datetime, end_utc: datetime) -> int:
        """Whole minutes between two UTC datetimes."""
        delta = ensure_utc(end_utc) - ensure_utc(start_utc)
        return max(0, int(delta.total_seconds() // 60))

    def get_dst_offset_minutes(self, timestamp_utc: datetime, tz_name: str) -> int:
        """Current UTC offset in minutes for timezone at reference time."""
        tz = validate_timezone(tz_name)
        local_dt = ensure_utc(timestamp_utc).astimezone(tz)
        offset = local_dt.utcoffset()
        if offset is None:
            return 0
        return int(offset.total_seconds() // 60)

    def is_dst_transition(
        self,
        timestamp_utc: datetime,
        tz_name: str,
        window_hours: int,
    ) -> bool:
        """Detect DST offset change within window around reference time."""
        utc_ref = ensure_utc(timestamp_utc)
        current_offset = self.get_dst_offset_minutes(utc_ref, tz_name)
        for hours in range(1, window_hours + 1):
            for sign in (-1, 1):
                probe = utc_ref + timedelta(hours=sign * hours)
                if self.get_dst_offset_minutes(probe, tz_name) != current_offset:
                    return True
        return False

    def find_dst_transition_time(
        self,
        timestamp_utc: datetime,
        tz_name: str,
        window_hours: int,
    ) -> datetime | None:
        """Find approximate DST transition time within window."""
        utc_ref = ensure_utc(timestamp_utc)
        current_offset = self.get_dst_offset_minutes(utc_ref, tz_name)
        for minute in range(1, window_hours * 60 + 1):
            for sign in (-1, 1):
                probe = utc_ref + timedelta(minutes=sign * minute)
                if self.get_dst_offset_minutes(probe, tz_name) != current_offset:
                    return probe
        return None

    def broker_day_boundary_utc(
        self,
        reference_utc: datetime,
        broker_timezone: str,
        day_start_hour: int,
    ) -> datetime:
        """Return UTC timestamp of current broker trading day start."""
        local_ref = self.to_broker_local(reference_utc, broker_timezone)
        boundary_date = local_ref.date()
        if local_ref.hour < day_start_hour:
            boundary_date -= timedelta(days=1)
        boundary_local = datetime(
            boundary_date.year,
            boundary_date.month,
            boundary_date.day,
            day_start_hour,
            0,
            tzinfo=validate_timezone(broker_timezone),
        )
        return boundary_local.astimezone(UTC)

    def trading_day_id(
        self,
        reference_utc: datetime,
        broker_timezone: str,
        day_start_hour: int,
    ) -> str:
        """Broker-normalized trading day identifier (YYYY-MM-DD)."""
        boundary = self.broker_day_boundary_utc(
            reference_utc,
            broker_timezone,
            day_start_hour,
        )
        local_boundary = self.to_broker_local(boundary, broker_timezone)
        return local_boundary.date().isoformat()

    def week_id(self, reference_utc: datetime, broker_timezone: str) -> str:
        """ISO week identifier from broker-local calendar."""
        local_ref = self.to_broker_local(reference_utc, broker_timezone)
        iso = local_ref.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def month_id(self, reference_utc: datetime, broker_timezone: str) -> str:
        """Year-month identifier from broker-local calendar."""
        local_ref = self.to_broker_local(reference_utc, broker_timezone)
        return f"{local_ref.year:02d}-{local_ref.month:02d}"
