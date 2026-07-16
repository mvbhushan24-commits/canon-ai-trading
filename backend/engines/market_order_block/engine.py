"""Order Block Engine orchestrator."""

import logging

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.schemas import LiquidityAnalysis
from backend.engines.market_order_block.config import OrderBlockConfig, load_order_block_config
from backend.engines.market_order_block.detector import OrderBlockDetector
from backend.engines.market_order_block.exceptions import (
    DuplicateBlockError,
    InsufficientDataError,
    OrderBlockError,
    UnsupportedTimeframeError,
)
from backend.engines.market_order_block.publisher import OrderBlockEventPublisher
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockAnalysis,
    OrderBlockEventKind,
    OrderBlockState,
)
from backend.engines.market_order_block.validator import OrderBlockInputValidator
from backend.engines.market_structure.schemas import MarketStructure

logger = logging.getLogger(__name__)


class OrderBlockEngine:
    """Institutional order block detection and lifecycle engine."""

    def __init__(
        self,
        config: OrderBlockConfig | None = None,
        detector: OrderBlockDetector | None = None,
        validator: OrderBlockInputValidator | None = None,
        publisher: OrderBlockEventPublisher | None = None,
    ) -> None:
        self._config = config or load_order_block_config()
        self._detector = detector or OrderBlockDetector(self._config)
        self._validator = validator or OrderBlockInputValidator()
        self._publisher = publisher or OrderBlockEventPublisher()
        self._prior_state: OrderBlockState | None = None

    @property
    def config(self) -> OrderBlockConfig:
        return self._config

    @property
    def publisher(self) -> OrderBlockEventPublisher:
        return self._publisher

    @property
    def prior_state(self) -> OrderBlockState | None:
        return self._prior_state

    def analyze(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
        *,
        timeframe: str | None = None,
        prior_state: OrderBlockState | None = None,
    ) -> OrderBlockAnalysis:
        """Analyze order blocks from candles and upstream context."""
        if not candles:
            raise InsufficientDataError(
                "No candles provided",
                details={"min_candles": self._config.min_candles},
            )

        state = prior_state or self._prior_state

        try:
            self._validator.validate_or_raise(candles, structure, liquidity, state)
        except OrderBlockError as exc:
            self._publisher.publish_error(
                symbol=candles[0].symbol if candles else None,
                code=exc.code,
                message=str(exc),
                details=exc.details,
            )
            raise

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
            "Analyzing order blocks",
            extra={
                "symbol": candles[0].symbol,
                "timeframe": target_timeframe,
                "candles": len(closed),
                "structure": structure is not None,
                "liquidity": liquidity is not None,
            },
        )

        analysis = self._detector.detect(closed, structure, liquidity, state)
        self._validate_unique_blocks(analysis.order_blocks)
        self.publish_events(analysis, prior_blocks=state.active_blocks if state else [])
        self._prior_state = analysis.state

        logger.info(
            "Order block analysis complete",
            extra={
                "symbol": analysis.symbol,
                "timeframe": analysis.timeframe,
                "fresh": len(analysis.fresh_blocks),
                "mitigated": len(analysis.mitigated_blocks),
                "invalidated": len(analysis.invalidated_blocks),
                "bias": analysis.bias.value,
            },
        )
        return analysis

    def detect_bullish_blocks(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
    ) -> list[OrderBlock]:
        """Detect bullish order blocks only."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.detect_bullish_blocks(closed, structure, liquidity)

    def detect_bearish_blocks(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
    ) -> list[OrderBlock]:
        """Detect bearish order blocks only."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.detect_bearish_blocks(closed, structure, liquidity)

    def classify_lifecycle(
        self,
        blocks: list[OrderBlock],
        candles: list[NormalizedCandle],
    ) -> list[OrderBlock]:
        """Update fresh, mitigated, and invalidated status."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.classify_lifecycle(blocks, closed)

    def publish_events(
        self,
        analysis: OrderBlockAnalysis,
        *,
        prior_blocks: list[OrderBlock] | None = None,
    ) -> None:
        """Emit all order block lifecycle events."""
        prior_by_id = {block.block_id: block for block in (prior_blocks or [])}
        blocks_by_id = {block.block_id: block for block in analysis.order_blocks}

        for block in analysis.order_blocks:
            if block.block_id not in prior_by_id:
                self._publisher.publish_block_detected(block, analysis.symbol)
                if block.direction.value == "bullish":
                    self._publisher.publish_bullish_block(block, analysis.symbol)
                else:
                    self._publisher.publish_bearish_block(block, analysis.symbol)

        for event in analysis.events:
            block = blocks_by_id.get(event.block_id or "")
            if block is None:
                continue
            if event.kind is OrderBlockEventKind.FRESH_ORDER_BLOCK:
                self._publisher.publish_fresh_block(block, analysis.symbol)
            elif event.kind is OrderBlockEventKind.MITIGATED_ORDER_BLOCK:
                self._publisher.publish_mitigated_block(block, analysis.symbol)
            elif event.kind is OrderBlockEventKind.INVALIDATED_ORDER_BLOCK:
                self._publisher.publish_invalidated_block(block, analysis.symbol)

        self._publisher.publish_analysis_completed(analysis)

    def reset_state(self) -> None:
        self._prior_state = None
        logger.info("Order block engine state reset")

    def handle_config_updated(self, config: OrderBlockConfig) -> None:
        self._config = config
        self._detector = OrderBlockDetector(config)
        logger.info("Order block configuration updated")

    @staticmethod
    def _validate_unique_blocks(blocks: list[OrderBlock]) -> None:
        seen: set[str] = set()
        for block in blocks:
            if block.block_id in seen:
                raise DuplicateBlockError(
                    "Duplicate order block identifiers in analysis output",
                    details={"block_id": block.block_id},
                )
            seen.add(block.block_id)
