"""Unit tests for timeframe manager."""

import pytest

from backend.engines.market_data.exceptions import InvalidTimeframeError
from backend.engines.market_data.timeframes import (
    SUPPORTED_TIMEFRAMES,
    Timeframe,
    timeframe_duration,
    validate_timeframe,
    validate_timeframes,
)


def test_supported_timeframes_include_required_periods() -> None:
    required = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}
    assert required.issubset(SUPPORTED_TIMEFRAMES)


def test_validate_timeframe_normalizes_case() -> None:
    assert validate_timeframe("h1") == "H1"


def test_validate_timeframe_rejects_unknown() -> None:
    with pytest.raises(InvalidTimeframeError):
        validate_timeframe("W1")


def test_validate_timeframes_preserves_order() -> None:
    assert validate_timeframes(["m1", "H4", "d1"]) == ["M1", "H4", "D1"]


def test_timeframe_duration_values() -> None:
    assert timeframe_duration(Timeframe.M1.value).total_seconds() == 60
    assert timeframe_duration(Timeframe.H1.value).total_seconds() == 3600
    assert timeframe_duration(Timeframe.D1.value).total_seconds() == 86400
