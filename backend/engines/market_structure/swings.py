"""Swing high and swing low detection."""

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure.schemas import SwingKind, SwingLabel, SwingPoint


class SwingDetector:
    """Detect swing highs and swing lows using fractal lookback."""

    def detect(
        self,
        candles: list[NormalizedCandle],
        lookback: int,
    ) -> tuple[list[SwingPoint], list[SwingPoint]]:
        """Return confirmed swing highs and swing lows."""
        if lookback < 1 or len(candles) < 2 * lookback + 1:
            return [], []

        swing_highs: list[SwingPoint] = []
        swing_lows: list[SwingPoint] = []

        for index in range(lookback, len(candles) - lookback):
            candle = candles[index]
            if not self._is_swing_high(candles, index, lookback):
                continue
            swing_highs.append(
                SwingPoint(
                    price=candle.high,
                    timestamp_utc=candle.open_time_utc,
                    bar_index=index,
                    kind=SwingKind.SWING_HIGH,
                )
            )

        for index in range(lookback, len(candles) - lookback):
            candle = candles[index]
            if not self._is_swing_low(candles, index, lookback):
                continue
            swing_lows.append(
                SwingPoint(
                    price=candle.low,
                    timestamp_utc=candle.open_time_utc,
                    bar_index=index,
                    kind=SwingKind.SWING_LOW,
                )
            )

        return swing_highs, swing_lows

    def label_swings(
        self,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
    ) -> tuple[list[SwingPoint], list[SwingPoint], list[SwingPoint], list[SwingPoint],
               list[SwingPoint], list[SwingPoint]]:
        """Classify swings as HH, HL, LH, LL."""
        labeled_highs = self._label_highs(swing_highs)
        labeled_lows = self._label_lows(swing_lows)

        hh = [s for s in labeled_highs if s.label == SwingLabel.HH]
        lh = [s for s in labeled_highs if s.label == SwingLabel.LH]
        hl = [s for s in labeled_lows if s.label == SwingLabel.HL]
        ll = [s for s in labeled_lows if s.label == SwingLabel.LL]

        return labeled_highs, labeled_lows, hh, hl, lh, ll

    @staticmethod
    def _is_swing_high(candles: list[NormalizedCandle], index: int, lookback: int) -> bool:
        pivot_high = candles[index].high
        for offset in range(1, lookback + 1):
            if pivot_high <= candles[index - offset].high:
                return False
            if pivot_high <= candles[index + offset].high:
                return False
        return True

    @staticmethod
    def _is_swing_low(candles: list[NormalizedCandle], index: int, lookback: int) -> bool:
        pivot_low = candles[index].low
        for offset in range(1, lookback + 1):
            if pivot_low >= candles[index - offset].low:
                return False
            if pivot_low >= candles[index + offset].low:
                return False
        return True

    def _label_highs(self, swings: list[SwingPoint]) -> list[SwingPoint]:
        if not swings:
            return []
        ordered = sorted(swings, key=lambda s: s.bar_index)
        labeled: list[SwingPoint] = []
        for index, swing in enumerate(ordered):
            if index == 0:
                labeled.append(swing.model_copy(update={"label": SwingLabel.NONE}))
                continue
            prior = ordered[index - 1]
            label = SwingLabel.HH if swing.price > prior.price else SwingLabel.LH
            labeled.append(swing.model_copy(update={"label": label}))
        return labeled

    def _label_lows(self, swings: list[SwingPoint]) -> list[SwingPoint]:
        if not swings:
            return []
        ordered = sorted(swings, key=lambda s: s.bar_index)
        labeled: list[SwingPoint] = []
        for index, swing in enumerate(ordered):
            if index == 0:
                labeled.append(swing.model_copy(update={"label": SwingLabel.NONE}))
                continue
            prior = ordered[index - 1]
            label = SwingLabel.HL if swing.price > prior.price else SwingLabel.LL
            labeled.append(swing.model_copy(update={"label": label}))
        return labeled

    def deduplicate_swings(self, swings: list[SwingPoint]) -> list[SwingPoint]:
        """Remove duplicate swings at the same bar index."""
        seen: set[int] = set()
        unique: list[SwingPoint] = []
        for swing in sorted(swings, key=lambda s: s.bar_index):
            if swing.bar_index in seen:
                continue
            seen.add(swing.bar_index)
            unique.append(swing)
        return unique
