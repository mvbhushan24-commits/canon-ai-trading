"""Market Structure Engine orchestrator."""

import logging

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure.config import (
    MarketStructureConfig,
    load_market_structure_config,
)
from backend.engines.market_structure.detector import StructureDetector
from backend.engines.market_structure.exceptions import (
    InsufficientDataError,
    UnsupportedTimeframeError,
)
from backend.engines.market_structure.publisher import StructureEventPublisher
from backend.engines.market_structure.schemas import MarketStructure, StructureState
from backend.engines.market_structure.validator import StructureInputValidator

logger = logging.getLogger(__name__)


class MarketStructureEngine:
    """Smart Money Concepts market structure analysis engine."""

    def __init__(
        self,
        config: MarketStructureConfig | None = None,
        detector: StructureDetector | None = None,
        validator: StructureInputValidator | None = None,
        publisher: StructureEventPublisher | None = None,
    ) -> None:
        self._config = config or load_market_structure_config()
        self._detector = detector or StructureDetector(self._config)
        self._validator = validator or StructureInputValidator()
        self._publisher = publisher or StructureEventPublisher()
        self._prior_state: StructureState | None = None

    @property
    def config(self) -> MarketStructureConfig:
        return self._config

    @property
    def publisher(self) -> StructureEventPublisher:
        return self._publisher

    @property
    def prior_state(self) -> StructureState | None:
        return self._prior_state

    def analyze(
        self,
        candles: list[NormalizedCandle],
        *,
        timeframe: str | None = None,
        prior_state: StructureState | None = None,
    ) -> MarketStructure:
        """Analyze a batch of normalized candles and return market structure."""
        if not candles:
            raise InsufficientDataError(
                "No candles provided",
                details={"min_candles": self._config.min_candles},
            )

        self._validator.validate_or_raise(candles)
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

        state = prior_state or self._prior_state
        logger.info(
            "Analyzing market structure",
            extra={
                "symbol": candles[0].symbol,
                "timeframe": target_timeframe,
                "candles": len(closed),
            },
        )

        structure = self._detector.detect(closed, prior_state=state)
        self._emit_events(structure, state)
        self._prior_state = structure.current_structure_state

        logger.info(
            "Market structure analysis complete",
            extra={
                "trend": structure.current_trend.value,
                "swing_highs": len(structure.swing_highs),
                "swing_lows": len(structure.swing_lows),
                "bos": len(structure.bos_events),
                "choch": len(structure.choch_events),
            },
        )
        return structure

    def analyze_candle(
        self,
        candle: NormalizedCandle,
        history: list[NormalizedCandle],
        *,
        prior_state: StructureState | None = None,
    ) -> MarketStructure:
        """Analyze structure using candle history plus the latest candle."""
        if not candle.is_closed:
            logger.debug("Skipping unclosed candle for structure analysis")
        combined = sorted(history + [candle], key=lambda c: c.open_time_utc)
        return self.analyze(combined, prior_state=prior_state)

    def reset_state(self) -> None:
        """Reset persisted structure state."""
        self._prior_state = None
        logger.info("Market structure state reset")

    def handle_config_updated(self, config: MarketStructureConfig) -> None:
        """Apply updated configuration."""
        self._config = config
        self._detector = StructureDetector(config)
        logger.info("Market structure configuration updated")

    def _emit_events(
        self,
        structure: MarketStructure,
        prior_state: StructureState | None,
    ) -> None:
        for swing in structure.swing_highs + structure.swing_lows:
            self._publisher.publish_swing_detected(
                swing,
                structure.symbol,
                structure.timeframe,
            )

        for bos in structure.bos_events:
            self._publisher.publish_bos_detected(bos, structure.symbol)

        for choch in structure.choch_events:
            self._publisher.publish_choch_detected(choch, structure.symbol)

        if prior_state and prior_state.trend != structure.current_trend:
            self._publisher.publish_trend_changed(
                symbol=structure.symbol,
                timeframe=structure.timeframe,
                previous=prior_state.trend,
                current=structure.current_trend,
                timestamp_utc=structure.timestamp_utc,
            )

        self._publisher.publish_structure_updated(structure)
