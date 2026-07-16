"""Data validation for normalized market data."""

from datetime import UTC, datetime

from backend.engines.market_data.schemas import GapInfo, NormalizedCandle, ValidationResult
from backend.engines.market_data.timeframes import timeframe_duration, validate_timeframe


class DataValidator:
    """Validate candle sequences for gaps, duplicates, timestamps, and OHLC integrity."""

    def validate_candles(
        self,
        candles: list[NormalizedCandle],
        *,
        reference_time: datetime | None = None,
    ) -> ValidationResult:
        if not candles:
            return ValidationResult(is_valid=True)

        sorted_candles = sorted(candles, key=lambda candle: candle.open_time_utc)
        reference = reference_time or datetime.now(tz=UTC)
        if reference_time is None:
            latest_close = max(candle.close_time_utc for candle in sorted_candles)
            if latest_close > reference:
                reference = latest_close

        errors: list[str] = []
        duplicate_count = 0
        invalid_timestamp_count = 0
        invalid_ohlc_count = 0
        seen_times: set[datetime] = set()
        gaps: list[GapInfo] = []

        for candle in sorted_candles:
            if candle.open_time_utc in seen_times:
                duplicate_count += 1
                errors.append(
                    f"Duplicate candle at {candle.open_time_utc.isoformat()} "
                    f"for {candle.symbol}/{candle.timeframe}"
                )
            seen_times.add(candle.open_time_utc)

            if not self._is_valid_timestamp(candle):
                invalid_timestamp_count += 1
                errors.append(
                    f"Invalid timestamp alignment for {candle.open_time_utc.isoformat()}"
                )

            if candle.is_closed and candle.open_time_utc > reference:
                invalid_timestamp_count += 1
                errors.append(f"Future timestamp detected: {candle.open_time_utc.isoformat()}")

            if not self._is_valid_ohlc(candle):
                invalid_ohlc_count += 1
                errors.append(f"Invalid OHLC values at {candle.open_time_utc.isoformat()}")

        gaps = self.detect_gaps(sorted_candles)
        if gaps:
            for gap in gaps:
                errors.append(
                    f"Gap detected: {gap.missing_bars} bars between "
                    f"{gap.gap_start_utc.isoformat()} and {gap.gap_end_utc.isoformat()}"
                )

        is_valid = not errors
        return ValidationResult(
            is_valid=is_valid,
            gaps=gaps,
            duplicate_count=duplicate_count,
            invalid_timestamp_count=invalid_timestamp_count,
            invalid_ohlc_count=invalid_ohlc_count,
            errors=errors,
        )

    def detect_gaps(self, candles: list[NormalizedCandle]) -> list[GapInfo]:
        if len(candles) < 2:
            return []

        sorted_candles = sorted(candles, key=lambda candle: candle.open_time_utc)
        timeframe = sorted_candles[0].timeframe
        symbol = sorted_candles[0].symbol
        step = timeframe_duration(timeframe)
        gaps: list[GapInfo] = []

        for previous, current in zip(sorted_candles, sorted_candles[1:], strict=False):
            expected_next = previous.open_time_utc + step
            if current.open_time_utc <= expected_next:
                continue

            missing = int((current.open_time_utc - expected_next) / step)
            if missing > 0:
                gaps.append(
                    GapInfo(
                        symbol=symbol,
                        timeframe=timeframe,
                        gap_start_utc=expected_next,
                        gap_end_utc=current.open_time_utc - step,
                        missing_bars=missing,
                    )
                )

        return gaps

    def detect_duplicates(self, candles: list[NormalizedCandle]) -> int:
        seen: set[datetime] = set()
        duplicates = 0
        for candle in candles:
            if candle.open_time_utc in seen:
                duplicates += 1
            seen.add(candle.open_time_utc)
        return duplicates

    @staticmethod
    def _is_valid_ohlc(candle: NormalizedCandle) -> bool:
        prices = [candle.open, candle.high, candle.low, candle.close]
        return max(prices) == candle.high and min(prices) == candle.low

    @staticmethod
    def _is_valid_timestamp(candle: NormalizedCandle) -> bool:
        validate_timeframe(candle.timeframe)
        duration = timeframe_duration(candle.timeframe)
        total_seconds = int(duration.total_seconds())
        if total_seconds <= 0:
            return False

        epoch_seconds = int(candle.open_time_utc.timestamp())
        return epoch_seconds % total_seconds == 0
