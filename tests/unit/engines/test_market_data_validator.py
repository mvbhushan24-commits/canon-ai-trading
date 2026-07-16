"""Unit tests for market data validator."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_data.schemas import NormalizedCandle
from backend.engines.market_data.validator import DataValidator


def _make_candle(
    symbol: str,
    open_time: datetime,
    *,
    timeframe: str = "H1",
    open_price: Decimal = Decimal("2300"),
    high: Decimal | None = None,
    low: Decimal | None = None,
    close: Decimal | None = None,
) -> NormalizedCandle:
    high = high or open_price + Decimal("2")
    low = low or open_price - Decimal("1")
    close = close or open_price + Decimal("1")
    duration = timedelta(hours=1) if timeframe == "H1" else timedelta(minutes=1)
    return NormalizedCandle(
        symbol=symbol,
        timeframe=timeframe,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100,
        open_time_utc=open_time,
        close_time_utc=open_time + duration,
        is_closed=True,
    )


def test_validate_candles_detects_gaps(sample_symbol: str) -> None:
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    candles = [
        _make_candle(sample_symbol, start),
        _make_candle(sample_symbol, start + timedelta(hours=3)),
    ]
    result = DataValidator().validate_candles(candles)

    assert result.is_valid is False
    assert len(result.gaps) == 1
    assert result.gaps[0].missing_bars == 2


def test_validate_candles_detects_duplicates(sample_symbol: str) -> None:
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    candle = _make_candle(sample_symbol, start)
    result = DataValidator().validate_candles([candle, candle])

    assert result.is_valid is False
    assert result.duplicate_count == 1


def test_validate_candles_detects_invalid_ohlc(sample_symbol: str) -> None:
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    candle = _make_candle(
        sample_symbol,
        start,
        high=Decimal("2290"),
        low=Decimal("2310"),
    )
    result = DataValidator().validate_candles([candle])

    assert result.is_valid is False
    assert result.invalid_ohlc_count == 1


def test_validate_candles_detects_future_timestamp(sample_symbol: str) -> None:
    future = datetime.now(tz=UTC) + timedelta(days=1)
    candle = _make_candle(sample_symbol, future)
    result = DataValidator().validate_candles(
        [candle],
        reference_time=datetime.now(tz=UTC),
    )

    assert result.is_valid is False
    assert result.invalid_timestamp_count >= 1
    assert any("Future timestamp" in error for error in result.errors)


def test_detect_duplicates(sample_candles: list[NormalizedCandle]) -> None:
    duplicated = sample_candles + [sample_candles[0]]
    assert DataValidator().detect_duplicates(duplicated) == 1
