"""External liquidity detection — previous, weekly, daily, session levels."""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.config import MarketLiquidityConfig
from backend.engines.market_liquidity.schemas import LiquidityKind, LiquidityLevel

SESSION_RANGES: dict[str, tuple[int, int]] = {
    "asian": (0, 8),
    "london": (8, 16),
    "new_york": (13, 21),
}


class ExternalLiquidityDetector:
    """Detect external institutional liquidity levels."""

    def __init__(self, config: MarketLiquidityConfig) -> None:
        self._config = config

    def detect(self, candles: list[NormalizedCandle]) -> list[LiquidityLevel]:
        """Detect all external liquidity levels from candle history."""
        if not candles:
            return []

        sorted_candles = sorted(
            [c for c in candles if c.is_closed],
            key=lambda c: c.open_time_utc,
        )
        if not sorted_candles:
            sorted_candles = sorted(candles, key=lambda c: c.open_time_utc)

        lookback = sorted_candles[-self._config.lookback :]
        levels: list[LiquidityLevel] = []
        levels.extend(self._detect_daily_levels(lookback))
        levels.extend(self._detect_weekly_levels(lookback))
        levels.extend(self._detect_previous_levels(lookback))
        levels.extend(self._detect_session_levels(lookback))
        return levels

    def _detect_daily_levels(self, candles: list[NormalizedCandle]) -> list[LiquidityLevel]:
        by_day: dict[datetime, list[NormalizedCandle]] = defaultdict(list)
        for candle in candles:
            day = candle.open_time_utc.astimezone(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            by_day[day].append(candle)

        levels: list[LiquidityLevel] = []
        for _day, day_candles in sorted(by_day.items()):
            high_candle = max(day_candles, key=lambda c: c.high)
            low_candle = min(day_candles, key=lambda c: c.low)
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.DAILY_HIGH,
                    price=high_candle.high,
                    timestamp_utc=high_candle.open_time_utc,
                    bar_index=self._bar_index(candles, high_candle),
                    strength=Decimal("0.7"),
                )
            )
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.DAILY_LOW,
                    price=low_candle.low,
                    timestamp_utc=low_candle.open_time_utc,
                    bar_index=self._bar_index(candles, low_candle),
                    strength=Decimal("0.7"),
                )
            )
        return levels

    def _detect_weekly_levels(self, candles: list[NormalizedCandle]) -> list[LiquidityLevel]:
        by_week: dict[tuple[int, int], list[NormalizedCandle]] = defaultdict(list)
        for candle in candles:
            dt = candle.open_time_utc.astimezone(UTC)
            key = (dt.isocalendar().year, dt.isocalendar().week)
            by_week[key].append(candle)

        levels: list[LiquidityLevel] = []
        for _, week_candles in sorted(by_week.items()):
            high_candle = max(week_candles, key=lambda c: c.high)
            low_candle = min(week_candles, key=lambda c: c.low)
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.WEEKLY_HIGH,
                    price=high_candle.high,
                    timestamp_utc=high_candle.open_time_utc,
                    bar_index=self._bar_index(candles, high_candle),
                    strength=Decimal("0.85"),
                )
            )
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.WEEKLY_LOW,
                    price=low_candle.low,
                    timestamp_utc=low_candle.open_time_utc,
                    bar_index=self._bar_index(candles, low_candle),
                    strength=Decimal("0.85"),
                )
            )
        return levels

    def _detect_previous_levels(self, candles: list[NormalizedCandle]) -> list[LiquidityLevel]:
        by_day: dict[datetime, list[NormalizedCandle]] = defaultdict(list)
        for candle in candles:
            day = candle.open_time_utc.astimezone(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            by_day[day].append(candle)

        days = sorted(by_day.keys())
        if len(days) < 2:
            return []

        previous_day = days[-2]
        previous_candles = by_day[previous_day]
        high_candle = max(previous_candles, key=lambda c: c.high)
        low_candle = min(previous_candles, key=lambda c: c.low)
        return [
            LiquidityLevel(
                kind=LiquidityKind.PREVIOUS_HIGH,
                price=high_candle.high,
                timestamp_utc=high_candle.open_time_utc,
                bar_index=self._bar_index(candles, high_candle),
                strength=Decimal("0.9"),
            ),
            LiquidityLevel(
                kind=LiquidityKind.PREVIOUS_LOW,
                price=low_candle.low,
                timestamp_utc=low_candle.open_time_utc,
                bar_index=self._bar_index(candles, low_candle),
                strength=Decimal("0.9"),
            ),
        ]

    def _detect_session_levels(self, candles: list[NormalizedCandle]) -> list[LiquidityLevel]:
        levels: list[LiquidityLevel] = []
        for session in self._config.session_filter:
            session_key = session.lower()
            if session_key not in SESSION_RANGES:
                continue
            start_hour, end_hour = SESSION_RANGES[session_key]
            session_candles = [
                c
                for c in candles
                if self._in_session(c.open_time_utc, start_hour, end_hour)
            ]
            if not session_candles:
                continue

            high_candle = max(session_candles, key=lambda c: c.high)
            low_candle = min(session_candles, key=lambda c: c.low)
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.SESSION_HIGH,
                    price=high_candle.high,
                    timestamp_utc=high_candle.open_time_utc,
                    bar_index=self._bar_index(candles, high_candle),
                    session=session_key,
                    strength=Decimal("0.65"),
                )
            )
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.SESSION_LOW,
                    price=low_candle.low,
                    timestamp_utc=low_candle.open_time_utc,
                    bar_index=self._bar_index(candles, low_candle),
                    session=session_key,
                    strength=Decimal("0.65"),
                )
            )
        return levels

    @staticmethod
    def _in_session(timestamp: datetime, start_hour: int, end_hour: int) -> bool:
        hour = timestamp.astimezone(UTC).hour
        if start_hour <= end_hour:
            return start_hour <= hour < end_hour
        return hour >= start_hour or hour < end_hour

    @staticmethod
    def _bar_index(candles: list[NormalizedCandle], target: NormalizedCandle) -> int:
        for index, candle in enumerate(candles):
            if candle.open_time_utc == target.open_time_utc:
                return index
        return len(candles) - 1
