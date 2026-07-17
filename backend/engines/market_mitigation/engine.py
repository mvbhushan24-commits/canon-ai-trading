"""Mitigation Block Engine orchestrator."""

import logging

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_mitigation.config import MitigationBlockConfig, load_market_mitigation_config
from backend.engines.market_mitigation.detector import MitigationBlockDetector
from backend.engines.market_mitigation.exceptions import (
    DuplicateBlockError,
    InsufficientDataError,
    MitigationBlockError,
    UnsupportedTimeframeError,
)
from backend.engines.market_mitigation.lifecycle import LifecycleManager
from backend.engines.market_mitigation.publisher import MitigationBlockEventPublisher
from backend.engines.market_mitigation.quality import QualityScorer
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockAnalysis,
    MitigationBlockEventKind,
    MitigationBlockState,
)
from backend.engines.market_mitigation.validator import MitigationBlockInputValidator
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_structure import MarketStructure

logger = logging.getLogger(__name__)


class MitigationBlockEngine:
    """Institutional mitigation block detection and lifecycle engine."""

    def __init__(
        self,
        config: MitigationBlockConfig | None = None,
        detector: MitigationBlockDetector | None = None,
        validator: MitigationBlockInputValidator | None = None,
        publisher: MitigationBlockEventPublisher | None = None,
    ) -> None:
        self._config = config or load_market_mitigation_config()
        self._detector = detector or MitigationBlockDetector(self._config)
        self._validator = validator or MitigationBlockInputValidator()
        self._publisher = publisher or MitigationBlockEventPublisher()
        self._lifecycle = LifecycleManager(self._config)
        self._quality = QualityScorer(self._config)
        self._prior_state: MitigationBlockState | None = None

    @property
    def config(self) -> MitigationBlockConfig:
        return self._config

    @property
    def publisher(self) -> MitigationBlockEventPublisher:
        return self._publisher

    @property
    def prior_state(self) -> MitigationBlockState | None:
        return self._prior_state

    def analyze(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        order_blocks: list[OrderBlock] | None = None,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        *,
        timeframe: str | None = None,
        prior_state: MitigationBlockState | None = None,
        htf_mitigation_blocks: list[MitigationBlock] | None = None,
        ltf_mitigation_blocks: list[MitigationBlock] | None = None,
    ) -> MitigationBlockAnalysis:
        """Analyze mitigation blocks from candles and upstream context."""
        if not candles:
            raise InsufficientDataError(
                "No candles provided",
                details={"min_candles": self._config.min_candles},
            )

        state = prior_state or self._prior_state
        target_timeframe = (timeframe or candles[0].timeframe).upper()

        try:
            self._validator.validate_or_raise(
                candles,
                structure,
                liquidity_state,
                order_blocks,
                fair_value_gap_state,
                breaker_blocks,
                state,
                htf_mitigation_blocks,
            )
        except MitigationBlockError as exc:
            self._publisher.publish_error(
                symbol=candles[0].symbol if candles else None,
                code=exc.code,
                message=str(exc),
                details=exc.details,
                timeframe=target_timeframe,
            )
            raise

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
            "Analyzing mitigation blocks",
            extra={
                "symbol": candles[0].symbol,
                "timeframe": target_timeframe,
                "candles": len(closed),
                "structure": structure is not None,
                "liquidity_state": liquidity_state is not None,
                "order_blocks": len(order_blocks or []),
                "fvg_state": fair_value_gap_state is not None,
                "breaker_blocks": len(breaker_blocks or []),
            },
        )

        analysis = self._detector.detect(
            closed,
            structure,
            order_blocks,
            liquidity_state,
            fair_value_gap_state,
            breaker_blocks,
            state,
            htf_mitigation_blocks,
            ltf_mitigation_blocks,
        )
        self._validate_unique_blocks(analysis.mitigation_blocks)
        self.publish_events(analysis, prior_blocks=state.active_blocks if state else [])
        self._prior_state = analysis.state

        logger.info(
            "Mitigation block analysis complete",
            extra={
                "symbol": analysis.symbol,
                "timeframe": analysis.timeframe,
                "fresh": len(analysis.fresh_blocks),
                "partial": len(analysis.partial_blocks),
                "confirmed": len(analysis.confirmed_blocks),
                "bias": analysis.bias.value,
            },
        )
        return analysis

    def detect_bullish_blocks(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
    ) -> list[MitigationBlock]:
        """Detect bullish mitigation blocks only."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.detect_bullish_blocks(closed, structure)

    def detect_bearish_blocks(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
    ) -> list[MitigationBlock]:
        """Detect bearish mitigation blocks only."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.detect_bearish_blocks(closed, structure)

    def classify_lifecycle(
        self,
        blocks: list[MitigationBlock],
        candles: list[NormalizedCandle],
    ) -> list[MitigationBlock]:
        """Update fresh, partial, confirmed, used, invalidated, and expired status."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.classify_lifecycle(blocks, closed)

    def track_touches(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
    ) -> MitigationBlock:
        """Update touch count and mitigation percent."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._lifecycle.track_touches(block, closed)

    def validate_confirmation(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
    ) -> bool:
        """Check confirmation rules for a block."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._lifecycle.validate_confirmation(block, closed)

    def score_confluence(
        self,
        block: MitigationBlock,
        liquidity_state: LiquidityState | None,
        order_blocks: list[OrderBlock] | None,
        fair_value_gap_state: FairValueGapState | None,
        breaker_blocks: list[BreakerBlock] | None,
    ) -> MitigationBlock:
        """Enrich block with upstream confluence fields."""
        return self._quality.score_confluence(
            block,
            liquidity_state,
            order_blocks,
            fair_value_gap_state,
            breaker_blocks,
        )

    def classify_nesting(
        self,
        block: MitigationBlock,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
    ) -> MitigationBlock:
        """Classify nested relationship fields."""
        nested, _ = self._quality.classify_nesting(
            block,
            order_blocks=order_blocks,
            fair_value_gaps=(
                fair_value_gap_state.active_gaps if fair_value_gap_state else None
            ),
            breaker_blocks=breaker_blocks,
        )
        return nested

    def publish_events(
        self,
        analysis: MitigationBlockAnalysis,
        *,
        prior_blocks: list[MitigationBlock] | None = None,
    ) -> None:
        """Emit all mitigation block lifecycle events."""
        prior_by_id = {block.block_id: block for block in (prior_blocks or [])}
        blocks_by_id = {block.block_id: block for block in analysis.mitigation_blocks}

        for block in analysis.mitigation_blocks:
            if block.block_id not in prior_by_id:
                self._publisher.publish_block_detected(block, analysis.symbol)
                if block.direction.value == "bullish":
                    self._publisher.publish_bullish_block(block, analysis.symbol)
                else:
                    self._publisher.publish_bearish_block(block, analysis.symbol)
                self._publisher.publish_fresh_block(block, analysis.symbol)

        for event in analysis.events:
            block = blocks_by_id.get(event.block_id or "")
            if block is None:
                continue

            if event.kind is MitigationBlockEventKind.NESTED_MITIGATION_BLOCK:
                self._publisher.publish_nested(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.INTERNAL_MITIGATION_BLOCK:
                self._publisher.publish_internal_scope(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.EXTERNAL_MITIGATION_BLOCK:
                self._publisher.publish_external_scope(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.LIQUIDITY_CONFLUENCE_MITIGATION:
                self._publisher.publish_liquidity_confluence(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.ORDER_BLOCK_CONFLUENCE_MITIGATION:
                self._publisher.publish_ob_confluence(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.FVG_CONFLUENCE_MITIGATION:
                self._publisher.publish_fvg_confluence(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.BREAKER_CONFLUENCE_MITIGATION:
                self._publisher.publish_breaker_confluence(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.HTF_MITIGATION_ALIGNED:
                self._publisher.publish_htf_aligned(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.LTF_MITIGATION_NESTED:
                self._publisher.publish_ltf_nested(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.PARTIAL_MITIGATION_BLOCK:
                self._publisher.publish_partial_mitigation(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.FULL_MITIGATION_BLOCK:
                self._publisher.publish_full_mitigation(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.MULTI_TOUCH_MITIGATION_BLOCK:
                self._publisher.publish_multi_touch(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.CONFIRMED_MITIGATION_BLOCK:
                self._publisher.publish_confirmed(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.USED_MITIGATION_BLOCK:
                self._publisher.publish_used(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.INVALIDATED_MITIGATION_BLOCK:
                self._publisher.publish_invalidated(block, analysis.symbol)
            elif event.kind is MitigationBlockEventKind.EXPIRED_MITIGATION_BLOCK:
                self._publisher.publish_expired(block, analysis.symbol)

        self._publisher.publish_analysis_completed(analysis)

    def reset_state(self) -> None:
        self._prior_state = None
        logger.info("Mitigation block engine state reset")

    def handle_config_updated(self, config: MitigationBlockConfig) -> None:
        self._config = config
        self._detector = MitigationBlockDetector(config)
        self._lifecycle = LifecycleManager(config)
        self._quality = QualityScorer(config)
        logger.info("Mitigation block configuration updated")

    @staticmethod
    def _validate_unique_blocks(blocks: list[MitigationBlock]) -> None:
        seen: set[str] = set()
        for block in blocks:
            if block.block_id in seen:
                raise DuplicateBlockError(
                    "Duplicate block identifiers in analysis output",
                    details={"block_id": block.block_id},
                )
            seen.add(block.block_id)
