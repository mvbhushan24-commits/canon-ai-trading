"""Bearish fair value gap formation detection."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FVGFormationCandidate, FairValueGapDirection


class BearishFVGDetector:
    """Identify bearish three-candle fair value gap formations."""

    def find_formations(self, candles: list[NormalizedCandle]) -> list[FVGFormationCandidate]:
        """Return bearish FVG candidates where candle A low is above candle C high."""
        formations: list[FVGFormationCandidate] = []

        for index in range(2, len(candles)):
            candle_a = candles[index - 2]
            candle_b = candles[index - 1]
            candle_c = candles[index]

            if candle_a.low <= candle_c.high:
                continue

            low = candle_c.high
            high = candle_a.low
            if high <= low:
                continue

            formations.append(
                FVGFormationCandidate(
                    direction=FairValueGapDirection.BEARISH,
                    candle_a_index=index - 2,
                    candle_b_index=index - 1,
                    candle_c_index=index,
                    origin_bar_index=index - 1,
                    origin_time_utc=candle_b.open_time_utc,
                    high=Decimal(str(high)),
                    low=Decimal(str(low)),
                ),
            )

        return formations
