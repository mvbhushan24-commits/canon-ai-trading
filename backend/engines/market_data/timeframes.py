"""Timeframe manager for supported MT5 candle periods."""

from datetime import timedelta
from enum import StrEnum

from backend.engines.market_data.exceptions import InvalidTimeframeError


class Timeframe(StrEnum):
    """Supported candle timeframes."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"


SUPPORTED_TIMEFRAMES: frozenset[str] = frozenset(tf.value for tf in Timeframe)

_TIMEFRAME_DURATIONS: dict[str, timedelta] = {
    Timeframe.M1.value: timedelta(minutes=1),
    Timeframe.M5.value: timedelta(minutes=5),
    Timeframe.M15.value: timedelta(minutes=15),
    Timeframe.M30.value: timedelta(minutes=30),
    Timeframe.H1.value: timedelta(hours=1),
    Timeframe.H4.value: timedelta(hours=4),
    Timeframe.D1.value: timedelta(days=1),
}


def validate_timeframe(timeframe: str) -> str:
    """Validate and normalize a timeframe string."""
    normalized = timeframe.strip().upper()
    if normalized not in SUPPORTED_TIMEFRAMES:
        supported = ", ".join(sorted(SUPPORTED_TIMEFRAMES))
        raise InvalidTimeframeError(
            f"Unsupported timeframe '{timeframe}'. Supported: {supported}",
            details={"timeframe": timeframe},
        )
    return normalized


def validate_timeframes(timeframes: list[str]) -> list[str]:
    """Validate and normalize a list of timeframes, preserving order."""
    return [validate_timeframe(tf) for tf in timeframes]


def timeframe_duration(timeframe: str) -> timedelta:
    """Return the candle duration for a validated timeframe."""
    normalized = validate_timeframe(timeframe)
    return _TIMEFRAME_DURATIONS[normalized]


def resolve_mt5_timeframe(timeframe: str, mt5_constants: dict[str, int]) -> int:
    """Map a canonical timeframe to the MT5 constant."""
    normalized = validate_timeframe(timeframe)
    constant_name = f"TIMEFRAME_{normalized}"
    if constant_name not in mt5_constants:
        raise InvalidTimeframeError(
            f"MT5 constant missing for timeframe '{normalized}'",
            details={"timeframe": normalized},
        )
    return mt5_constants[constant_name]
