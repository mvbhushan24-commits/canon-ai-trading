"""Liquidity detection orchestrator."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.config import MarketLiquidityConfig
from backend.engines.market_liquidity.equal import EqualLiquidityDetector
from backend.engines.market_liquidity.external import ExternalLiquidityDetector
from backend.engines.market_liquidity.schemas import (
    EqualLevelCluster,
    LiquidityAnalysis,
    LiquidityGrab,
    LiquidityLevel,
    LiquiditySide,
    LiquidityState,
    LiquiditySweep,
)
from backend.engines.market_liquidity.sweep import SweepDetector
from backend.engines.market_liquidity.zones import ZoneBuilder
from backend.engines.market_structure.schemas import MarketStructure, SwingPoint


class LiquidityDetector:
    """Orchestrate external, equal, sweep, and zone liquidity detection."""

    def __init__(
        self,
        config: MarketLiquidityConfig,
        external_detector: ExternalLiquidityDetector | None = None,
        equal_detector: EqualLiquidityDetector | None = None,
        sweep_detector: SweepDetector | None = None,
        zone_builder: ZoneBuilder | None = None,
    ) -> None:
        self._config = config
        self._external = external_detector or ExternalLiquidityDetector(config)
        self._equal = equal_detector or EqualLiquidityDetector(config)
        self._sweep = sweep_detector or SweepDetector(config)
        self._zones = zone_builder or ZoneBuilder(config)

    def detect(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
    ) -> LiquidityAnalysis:
        """Run full liquidity analysis pipeline."""
        sorted_candles = sorted(
            [c for c in candles if c.is_closed],
            key=lambda c: c.open_time_utc,
        )
        if not sorted_candles:
            sorted_candles = sorted(candles, key=lambda c: c.open_time_utc)

        symbol = sorted_candles[0].symbol
        timeframe = sorted_candles[0].timeframe
        analysis_time = sorted_candles[-1].close_time_utc

        external = self._external.detect(sorted_candles)
        internal = self._equal.internal_liquidity(structure)
        equal_highs = self.detect_equal_highs(structure)
        equal_lows = self.detect_equal_lows(structure)
        buy_side = self.detect_buy_side(equal_highs)
        sell_side = self.detect_sell_side(equal_lows)

        sweep_targets = buy_side + sell_side + external + internal
        sweeps = self.detect_sweeps(sorted_candles, sweep_targets, timeframe)
        grabs = self.detect_grabs(sorted_candles, sweeps, timeframe)
        zones = self._zones.build_zones(equal_highs, equal_lows)

        bias, confidence, evidence = self._determine_bias(
            buy_side,
            sell_side,
            sweeps,
            grabs,
            structure,
        )

        state = LiquidityState(
            active_zones=zones,
            recent_sweeps=sweeps[-5:],
            bar_count=len(sorted_candles),
        )

        return LiquidityAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_utc=analysis_time,
            external_liquidity=external,
            internal_liquidity=internal,
            equal_highs=equal_highs,
            equal_lows=equal_lows,
            buy_side_liquidity=buy_side,
            sell_side_liquidity=sell_side,
            sweeps=sweeps,
            grabs=grabs,
            zones=zones,
            bias=bias,
            confidence=confidence,
            evidence=evidence,
            state=state,
        )

    def detect_equal_highs(
        self,
        structure: MarketStructure | None,
        swing_highs: list[SwingPoint] | None = None,
    ) -> list[EqualLevelCluster]:
        return self._equal.detect_equal_highs(structure, swing_highs)

    def detect_equal_lows(
        self,
        structure: MarketStructure | None,
        swing_lows: list[SwingPoint] | None = None,
    ) -> list[EqualLevelCluster]:
        return self._equal.detect_equal_lows(structure, swing_lows)

    def detect_buy_side(self, equal_highs: list[EqualLevelCluster]) -> list[LiquidityLevel]:
        return self._equal.detect_buy_side(equal_highs)

    def detect_sell_side(self, equal_lows: list[EqualLevelCluster]) -> list[LiquidityLevel]:
        return self._equal.detect_sell_side(equal_lows)

    def detect_sweeps(
        self,
        candles: list[NormalizedCandle],
        liquidity_levels: list[LiquidityLevel],
        timeframe: str,
    ) -> list[LiquiditySweep]:
        return self._sweep.detect_sweeps(candles, liquidity_levels, timeframe)

    def detect_grabs(
        self,
        candles: list[NormalizedCandle],
        sweeps: list[LiquiditySweep],
        timeframe: str,
    ) -> list[LiquidityGrab]:
        return self._sweep.detect_grabs(candles, sweeps, timeframe)

    @staticmethod
    def _determine_bias(
        buy_side: list[LiquidityLevel],
        sell_side: list[LiquidityLevel],
        sweeps: list[LiquiditySweep],
        grabs: list[LiquidityGrab],
        structure: MarketStructure | None,
    ) -> tuple[LiquiditySide, Decimal, list[str]]:
        evidence: list[str] = []
        buy_score = len(buy_side)
        sell_score = len(sell_side)

        if structure is not None:
            evidence.append(f"Structure trend: {structure.current_trend.value}")
            if structure.current_trend.value == "bullish":
                buy_score += 1
            elif structure.current_trend.value == "bearish":
                sell_score += 1

        if sweeps:
            evidence.append(f"{len(sweeps)} liquidity sweep(s) detected")
        if grabs:
            evidence.append(f"{len(grabs)} liquidity grab(s) detected")

        total = buy_score + sell_score
        if total == 0:
            return LiquiditySide.UNDETERMINED, Decimal("0"), evidence

        if buy_score > sell_score:
            bias = LiquiditySide.BUY_SIDE
        elif sell_score > buy_score:
            bias = LiquiditySide.SELL_SIDE
        else:
            bias = LiquiditySide.BALANCED

        confidence = Decimal(str(round(max(buy_score, sell_score) / total, 2)))
        evidence.append(f"Liquidity bias: {bias.value}")
        return bias, confidence, evidence
