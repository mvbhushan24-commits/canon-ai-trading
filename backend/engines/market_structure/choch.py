"""Change of Character (CHoCH) detection."""

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure.schemas import (
    CHoCHDirection,
    CHoCHEvent,
    SwingPoint,
    TrendDirection,
)


class CHoCHDetector:
    """Detect change of character against the prevailing trend."""

    def detect(
        self,
        candles: list[NormalizedCandle],
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
        trend: TrendDirection,
        timeframe: str,
    ) -> list[CHoCHEvent]:
        """Detect CHoCH events when price breaks counter to trend."""
        if not candles or trend not in {TrendDirection.BULLISH, TrendDirection.BEARISH}:
            return []

        events: list[CHoCHEvent] = []
        closed = [c for c in candles if c.is_closed] or candles

        if trend == TrendDirection.BULLISH and swing_lows:
            for level in sorted(swing_lows, key=lambda swing: swing.bar_index):
                event = self._find_break_below(
                    closed,
                    level,
                    timeframe,
                    CHoCHDirection.BEARISH,
                )
                if event is not None:
                    events.append(event)

        if trend == TrendDirection.BEARISH and swing_highs:
            for level in sorted(swing_highs, key=lambda swing: swing.bar_index):
                event = self._find_break_above(
                    closed,
                    level,
                    timeframe,
                    CHoCHDirection.BULLISH,
                )
                if event is not None:
                    events.append(event)

        return events

    @staticmethod
    def _find_break_above(
        candles: list[NormalizedCandle],
        level: SwingPoint,
        timeframe: str,
        direction: CHoCHDirection,
    ) -> CHoCHEvent | None:
        for index, candle in enumerate(candles):
            if index <= level.bar_index:
                continue
            if candle.close > level.price:
                return CHoCHEvent(
                    direction=direction,
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
        direction: CHoCHDirection,
    ) -> CHoCHEvent | None:
        for index, candle in enumerate(candles):
            if index <= level.bar_index:
                continue
            if candle.close < level.price:
                return CHoCHEvent(
                    direction=direction,
                    broken_level=level.price,
                    break_price=candle.close,
                    timestamp_utc=candle.open_time_utc,
                    bar_index=index,
                    timeframe=timeframe,
                )
        return None
