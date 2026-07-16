"""Liquidity sweep and grab detection."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.config import MarketLiquidityConfig
from backend.engines.market_liquidity.schemas import (
    LiquidityGrab,
    LiquidityKind,
    LiquidityLevel,
    LiquiditySweep,
    SweepDirection,
    SweepQuality,
)


class SweepDetector:
    """Detect liquidity sweeps and aggressive grabs."""

    def __init__(self, config: MarketLiquidityConfig) -> None:
        self._config = config

    def detect_sweeps(
        self,
        candles: list[NormalizedCandle],
        liquidity_levels: list[LiquidityLevel],
        timeframe: str,
    ) -> list[LiquiditySweep]:
        """Detect price trading beyond liquidity then returning inside."""
        if not candles or not liquidity_levels:
            return []

        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda c: c.open_time_utc,
        )
        events: list[LiquiditySweep] = []

        for level in liquidity_levels:
            if level.kind in {LiquidityKind.SELL_SIDE, LiquidityKind.EQUAL_LOW,
                              LiquidityKind.DAILY_LOW, LiquidityKind.WEEKLY_LOW,
                              LiquidityKind.PREVIOUS_LOW, LiquidityKind.SESSION_LOW,
                              LiquidityKind.INTERNAL_SWING_LOW}:
                event = self._detect_low_sweep(closed, level, timeframe)
            else:
                event = self._detect_high_sweep(closed, level, timeframe)
            if event is not None:
                events.append(event)

        return events

    def detect_grabs(
        self,
        candles: list[NormalizedCandle],
        sweeps: list[LiquiditySweep],
        timeframe: str,
    ) -> list[LiquidityGrab]:
        """Detect aggressive rejection after liquidity sweeps."""
        if not candles or not sweeps:
            return []

        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda c: c.open_time_utc,
        )
        grabs: list[LiquidityGrab] = []

        for sweep in sweeps:
            if sweep.bar_index >= len(closed):
                continue
            candle = closed[sweep.bar_index]
            grab = self._classify_grab(candle, sweep, timeframe)
            if grab is not None:
                grabs.append(grab)

        return grabs

    def _detect_high_sweep(
        self,
        candles: list[NormalizedCandle],
        level: LiquidityLevel,
        timeframe: str,
    ) -> LiquiditySweep | None:
        start_index = (level.bar_index or 0) + 1
        for index in range(start_index, len(candles)):
            candle = candles[index]
            if candle.high <= level.price:
                continue
            if candle.close < level.price:
                quality = self._sweep_quality(candle, level.price, is_high=True)
                return LiquiditySweep(
                    direction=SweepDirection.BEARISH,
                    swept_level=level.price,
                    sweep_price=candle.high,
                    reclaim_price=candle.close,
                    timestamp_utc=candle.open_time_utc,
                    bar_index=index,
                    timeframe=timeframe,
                    quality=quality,
                    liquidity_kind=level.kind,
                )
        return None

    def _detect_low_sweep(
        self,
        candles: list[NormalizedCandle],
        level: LiquidityLevel,
        timeframe: str,
    ) -> LiquiditySweep | None:
        start_index = (level.bar_index or 0) + 1
        for index in range(start_index, len(candles)):
            candle = candles[index]
            if candle.low >= level.price:
                continue
            if candle.close > level.price:
                quality = self._sweep_quality(candle, level.price, is_high=False)
                return LiquiditySweep(
                    direction=SweepDirection.BULLISH,
                    swept_level=level.price,
                    sweep_price=candle.low,
                    reclaim_price=candle.close,
                    timestamp_utc=candle.open_time_utc,
                    bar_index=index,
                    timeframe=timeframe,
                    quality=quality,
                    liquidity_kind=level.kind,
                )
        return None

    def _classify_grab(
        self,
        candle: NormalizedCandle,
        sweep: LiquiditySweep,
        timeframe: str,
    ) -> LiquidityGrab | None:
        total_range = candle.high - candle.low
        if total_range <= Decimal("0"):
            return None

        body = abs(candle.close - candle.open)
        rejection_ratio = body / total_range
        if rejection_ratio < Decimal(str(self._config.sweep_rejection_ratio)):
            return None

        return LiquidityGrab(
            direction=sweep.direction,
            swept_level=sweep.swept_level,
            sweep_price=sweep.sweep_price,
            rejection_price=candle.close,
            timestamp_utc=candle.open_time_utc,
            bar_index=sweep.bar_index,
            timeframe=timeframe,
            rejection_ratio=rejection_ratio,
        )

    @staticmethod
    def _sweep_quality(
        candle: NormalizedCandle,
        level: Decimal,
        *,
        is_high: bool,
    ) -> SweepQuality:
        wick = candle.high - level if is_high else level - candle.low
        body = abs(candle.close - candle.open)
        if wick <= Decimal("0"):
            return SweepQuality.WEAK
        if body / wick >= Decimal("0.5"):
            return SweepQuality.STRONG
        return SweepQuality.INDETERMINATE
