"""Market Liquidity Engine orchestrator."""

import logging

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.config import (
    MarketLiquidityConfig,
    load_market_liquidity_config,
)
from backend.engines.market_liquidity.detector import LiquidityDetector
from backend.engines.market_liquidity.exceptions import (
    DuplicateZoneError,
    InsufficientDataError,
    UnsupportedTimeframeError,
)
from backend.engines.market_liquidity.publisher import LiquidityEventPublisher
from backend.engines.market_liquidity.schemas import (
    EqualLevelCluster,
    LiquidityAnalysis,
    LiquidityGrab,
    LiquidityLevel,
    LiquidityState,
    LiquiditySweep,
)
from backend.engines.market_liquidity.validator import LiquidityInputValidator
from backend.engines.market_structure.schemas import MarketStructure, SwingPoint

logger = logging.getLogger(__name__)


class LiquidityEngine:
    """Institutional liquidity analysis engine."""

    def __init__(
        self,
        config: MarketLiquidityConfig | None = None,
        detector: LiquidityDetector | None = None,
        validator: LiquidityInputValidator | None = None,
        publisher: LiquidityEventPublisher | None = None,
    ) -> None:
        self._config = config or load_market_liquidity_config()
        self._detector = detector or LiquidityDetector(self._config)
        self._validator = validator or LiquidityInputValidator()
        self._publisher = publisher or LiquidityEventPublisher()
        self._prior_state: LiquidityState | None = None

    @property
    def config(self) -> MarketLiquidityConfig:
        return self._config

    @property
    def publisher(self) -> LiquidityEventPublisher:
        return self._publisher

    @property
    def prior_state(self) -> LiquidityState | None:
        return self._prior_state

    def analyze(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        *,
        timeframe: str | None = None,
    ) -> LiquidityAnalysis:
        """Analyze liquidity from candles and optional market structure."""
        if not candles:
            raise InsufficientDataError(
                "No candles provided",
                details={"min_candles": self._config.min_candles},
            )

        self._validator.validate_or_raise(candles, structure)
        target_timeframe = (timeframe or candles[0].timeframe).upper()

        if target_timeframe not in self._config.timeframes:
            raise UnsupportedTimeframeError(
                f"Timeframe '{target_timeframe}' is not configured",
                details={"configured": self._config.timeframes},
            )

        closed = [c for c in candles if c.is_closed]
        if len(closed) < self._config.min_candles:
            raise InsufficientDataError(
                f"Need at least {self._config.min_candles} closed candles",
                details={"received": len(closed)},
            )

        logger.info(
            "Analyzing liquidity",
            extra={
                "symbol": candles[0].symbol,
                "timeframe": target_timeframe,
                "candles": len(closed),
                "structure": structure is not None,
            },
        )

        analysis = self._detector.detect(closed, structure)
        zone_result = self._validator.validate_zones([z.zone_id for z in analysis.zones])
        if not zone_result.is_valid:
            raise DuplicateZoneError(
                "Duplicate liquidity zones detected",
                details={"errors": zone_result.errors},
            )

        self.publish_events(analysis)
        self._prior_state = analysis.state

        logger.info(
            "Liquidity analysis complete",
            extra={
                "bias": analysis.bias.value,
                "external": len(analysis.external_liquidity),
                "equal_highs": len(analysis.equal_highs),
                "sweeps": len(analysis.sweeps),
                "grabs": len(analysis.grabs),
            },
        )
        return analysis

    def detect_equal_highs(
        self,
        structure: MarketStructure | None,
        swing_highs: list[SwingPoint] | None = None,
    ) -> list[EqualLevelCluster]:
        return self._detector.detect_equal_highs(structure, swing_highs)

    def detect_equal_lows(
        self,
        structure: MarketStructure | None,
        swing_lows: list[SwingPoint] | None = None,
    ) -> list[EqualLevelCluster]:
        return self._detector.detect_equal_lows(structure, swing_lows)

    def detect_buy_side(self, equal_highs: list[EqualLevelCluster]) -> list[LiquidityLevel]:
        return self._detector.detect_buy_side(equal_highs)

    def detect_sell_side(self, equal_lows: list[EqualLevelCluster]) -> list[LiquidityLevel]:
        return self._detector.detect_sell_side(equal_lows)

    def detect_sweeps(
        self,
        candles: list[NormalizedCandle],
        liquidity_levels: list[LiquidityLevel],
        timeframe: str,
    ) -> list[LiquiditySweep]:
        return self._detector.detect_sweeps(candles, liquidity_levels, timeframe)

    def detect_grabs(
        self,
        candles: list[NormalizedCandle],
        sweeps: list[LiquiditySweep],
        timeframe: str,
    ) -> list[LiquidityGrab]:
        return self._detector.detect_grabs(candles, sweeps, timeframe)

    def publish_events(self, analysis: LiquidityAnalysis) -> None:
        """Publish all liquidity events for an analysis result."""
        for level in (
            analysis.external_liquidity
            + analysis.internal_liquidity
            + analysis.buy_side_liquidity
            + analysis.sell_side_liquidity
        ):
            self._publisher.publish_liquidity_detected(level, analysis.symbol)

        for sweep in analysis.sweeps:
            self._publisher.publish_sweep(sweep, analysis.symbol)

        for grab in analysis.grabs:
            self._publisher.publish_grab(grab, analysis.symbol)

        for zone in analysis.zones:
            self._publisher.publish_zone(zone, analysis.symbol)

        self._publisher.publish_analysis_completed(analysis)

    def reset_state(self) -> None:
        self._prior_state = None
        logger.info("Liquidity engine state reset")

    def handle_config_updated(self, config: MarketLiquidityConfig) -> None:
        self._config = config
        self._detector = LiquidityDetector(config)
        logger.info("Liquidity configuration updated")
