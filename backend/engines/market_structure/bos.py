"""Break of Structure (BOS) detection."""

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure.schemas import (
    BOSDirection,
    BOSEvent,
    SwingPoint,
    TrendDirection,
)


class BOSDetector:
    """Detect breaks of structure in the direction of the prevailing trend."""

    def detect(
        self,
        candles: list[NormalizedCandle],
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
        trend: TrendDirection,
        timeframe: str,
    ) -> list[BOSEvent]:
        """Detect BOS events from candle closes against swing levels."""
        if not candles or trend not in {TrendDirection.BULLISH, TrendDirection.BEARISH}:
            return []

        events: list[BOSEvent] = []
        closed = [c for c in candles if c.is_closed] or candles

        if trend == TrendDirection.BULLISH and swing_highs:
            level = self._prior_swing(swing_highs)
            if level is not None:
                event = self._find_break_above(closed, level, timeframe)
                if event is not None:
                    events.append(event)

        if trend == TrendDirection.BEARISH and swing_lows:
            level = self._prior_swing(swing_lows)
            if level is not None:
                event = self._find_break_below(closed, level, timeframe)
                if event is not None:
                    events.append(event)

        return events

    @staticmethod
    def _prior_swing(swings: list[SwingPoint]) -> SwingPoint | None:
        if len(swings) < 2:
            return None
        ordered = sorted(swings, key=lambda s: s.bar_index)
        return ordered[-2]

    @staticmethod
    def _find_break_above(
        candles: list[NormalizedCandle],
        level: SwingPoint,
        timeframe: str,
    ) -> BOSEvent | None:
        for index, candle in enumerate(candles):
            if index <= level.bar_index:
                continue
            if candle.close > level.price:
                return BOSEvent(
                    direction=BOSDirection.BULLISH,
                    broken_level=level.price,
                    break_price=candle.close,
                    timestamp_utc=candle.open_time_utc,
                    bar_index=index,
                    timeframe=timeframe,
                )
        return None

    @staticmethod
    def _find_break_below(
        candles: list[NormalizedCandle],
        level: SwingPoint,
        timeframe: str,
    ) -> BOSEvent | None:
        for index, candle in enumerate(candles):
            if index <= level.bar_index:
                continue
            if candle.close < level.price:
                return BOSEvent(
                    direction=BOSDirection.BEARISH,
                    broken_level=level.price,
                    break_price=candle.close,
                    timestamp_utc=candle.open_time_utc,
                    bar_index=index,
                    timeframe=timeframe,
                )
        return None
