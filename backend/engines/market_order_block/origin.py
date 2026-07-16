"""Origin candle identification for order blocks."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_order_block.config import OrderBlockConfig
from backend.engines.market_order_block.schemas import OrderBlockDirection, OriginCandidate


class OriginDetector:
    """Identify opposing candles before displacement moves."""

    def __init__(self, config: OrderBlockConfig) -> None:
        self._config = config

    def find_bullish_origins(self, candles: list[NormalizedCandle]) -> list[OriginCandidate]:
        """Find bearish origin candles before bullish displacement."""
        return self._find_origins(candles, OrderBlockDirection.BULLISH)

    def find_bearish_origins(self, candles: list[NormalizedCandle]) -> list[OriginCandidate]:
        """Find bullish origin candles before bearish displacement."""
        return self._find_origins(candles, OrderBlockDirection.BEARISH)

    def _find_origins(
        self,
        candles: list[NormalizedCandle],
        direction: OrderBlockDirection,
    ) -> list[OriginCandidate]:
        candidates: list[OriginCandidate] = []
        scan_end = len(candles) - self._config.min_impulse_candles
        if scan_end < 1:
            return candidates

        for index in range(1, scan_end):
            candle = candles[index]
            if not self._is_opposing_candle(candle, direction):
                continue

            if not self._has_impulse_start(candles, index, direction):
                continue

            zone_high, zone_low = self._zone_bounds(candle)
            candidates.append(
                OriginCandidate(
                    direction=direction,
                    origin_bar_index=index,
                    origin_time_utc=candle.open_time_utc,
                    zone_high=zone_high,
                    zone_low=zone_low,
                    displacement_start_index=index + 1,
                ),
            )

        return candidates

    def _is_opposing_candle(
        self,
        candle: NormalizedCandle,
        direction: OrderBlockDirection,
    ) -> bool:
        if direction is OrderBlockDirection.BULLISH:
            return candle.close < candle.open
        return candle.close > candle.open

    def _has_impulse_start(
        self,
        candles: list[NormalizedCandle],
        origin_index: int,
        direction: OrderBlockDirection,
    ) -> bool:
        start = origin_index + 1
        end = start + self._config.min_impulse_candles
        if end > len(candles):
            return False

        for index in range(start, end):
            candle = candles[index]
            if direction is OrderBlockDirection.BULLISH and candle.close <= candle.open:
                return False
            if direction is OrderBlockDirection.BEARISH and candle.close >= candle.open:
                return False
        return True

    def _zone_bounds(self, candle: NormalizedCandle) -> tuple[Decimal, Decimal]:
        mode = self._config.zone_mode
        if mode == "body":
            return max(candle.open, candle.close), min(candle.open, candle.close)
        if mode == "wick":
            return candle.high, candle.low

        buffer_price = Decimal(str(self._config.full_zone_buffer_price))
        return candle.high + buffer_price, candle.low - buffer_price
