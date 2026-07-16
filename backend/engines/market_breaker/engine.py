"""Breaker Block Engine orchestrator."""

import logging

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_breaker.config import BreakerBlockConfig, load_market_breaker_config
from backend.engines.market_breaker.detector import BreakerBlockDetector
from backend.engines.market_breaker.exceptions import (
    BreakerBlockError,
    DuplicateBreakerError,
    InsufficientDataError,
    UnsupportedTimeframeError,
)
from backend.engines.market_breaker.lifecycle import LifecycleManager
from backend.engines.market_breaker.publisher import BreakerBlockEventPublisher
from backend.engines.market_breaker.quality import QualityScorer
from backend.engines.market_breaker.schemas import (
    BreakerBlock,
    BreakerBlockAnalysis,
    BreakerBlockEventKind,
    BreakerBlockState,
)
from backend.engines.market_breaker.validator import BreakerBlockInputValidator
from backend.engines.market_fvg.schemas import FairValueGap, FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_structure import MarketStructure

logger = logging.getLogger(__name__)


class BreakerBlockEngine:
    """Institutional breaker block detection and lifecycle engine."""

    def __init__(
        self,
        config: BreakerBlockConfig | None = None,
        detector: BreakerBlockDetector | None = None,
        validator: BreakerBlockInputValidator | None = None,
        publisher: BreakerBlockEventPublisher | None = None,
    ) -> None:
        self._config = config or load_market_breaker_config()
        self._detector = detector or BreakerBlockDetector(self._config)
        self._validator = validator or BreakerBlockInputValidator()
        self._publisher = publisher or BreakerBlockEventPublisher()
        self._lifecycle = LifecycleManager(self._config)
        self._quality = QualityScorer(self._config)
        self._prior_state: BreakerBlockState | None = None

    @property
    def config(self) -> BreakerBlockConfig:
        return self._config

    @property
    def publisher(self) -> BreakerBlockEventPublisher:
        return self._publisher

    @property
    def prior_state(self) -> BreakerBlockState | None:
        return self._prior_state

    def analyze(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        invalidated_order_blocks: list[OrderBlock] | None = None,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        *,
        timeframe: str | None = None,
        prior_state: BreakerBlockState | None = None,
        invalidated_fvgs: list[FairValueGap] | None = None,
    ) -> BreakerBlockAnalysis:
        """Analyze breaker blocks from candles and upstream context."""
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
                fair_value_gap_state,
                invalidated_order_blocks,
                state,
            )
        except BreakerBlockError as exc:
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
            "Analyzing breaker blocks",
            extra={
                "symbol": candles[0].symbol,
                "timeframe": target_timeframe,
                "candles": len(closed),
                "structure": structure is not None,
                "liquidity_state": liquidity_state is not None,
                "invalidated_blocks": len(invalidated_order_blocks or []),
                "fvg_state": fair_value_gap_state is not None,
            },
        )

        analysis = self._detector.detect(
            closed,
            structure,
            invalidated_order_blocks,
            liquidity_state,
            fair_value_gap_state,
            state,
            invalidated_fvgs,
        )
        self._validate_unique_breakers(analysis.breaker_blocks)
        self.publish_events(analysis, prior_breakers=state.active_breakers if state else [])
        self._prior_state = analysis.state

        logger.info(
            "Breaker block analysis complete",
            extra={
                "symbol": analysis.symbol,
                "timeframe": analysis.timeframe,
                "candidate": len(analysis.candidate_breakers),
                "confirmed": len(analysis.confirmed_breakers),
                "mitigated": len(analysis.mitigated_breakers),
                "bias": analysis.bias.value,
            },
        )
        return analysis

    def detect_bullish_breakers(
        self,
        candles: list[NormalizedCandle],
        invalidated_order_blocks: list[OrderBlock],
        structure: MarketStructure | None = None,
    ) -> list[BreakerBlock]:
        """Detect bullish breaker blocks only."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.detect_bullish_breakers(
            closed,
            invalidated_order_blocks,
            structure,
        )

    def detect_bearish_breakers(
        self,
        candles: list[NormalizedCandle],
        invalidated_order_blocks: list[OrderBlock],
        structure: MarketStructure | None = None,
    ) -> list[BreakerBlock]:
        """Detect bearish breaker blocks only."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.detect_bearish_breakers(
            closed,
            invalidated_order_blocks,
            structure,
        )

    def classify_lifecycle(
        self,
        breakers: list[BreakerBlock],
        candles: list[NormalizedCandle],
    ) -> list[BreakerBlock]:
        """Update candidate, confirmed, mitigated, invalidated, and expired status."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.classify_lifecycle(breakers, closed)

    def validate_confirmation(
        self,
        breaker: BreakerBlock,
        candles: list[NormalizedCandle],
    ) -> bool:
        """Check confirmation rules for a breaker."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._lifecycle.validate_confirmation(breaker, closed)

    def score_confluence(
        self,
        breaker: BreakerBlock,
        liquidity_state: LiquidityState | None,
        fvg_state: FairValueGapState | None,
    ) -> BreakerBlock:
        """Enrich breaker with liquidity and FVG confluence fields."""
        return self._quality.score_confluence(breaker, liquidity_state, fvg_state)

    def publish_events(
        self,
        analysis: BreakerBlockAnalysis,
        *,
        prior_breakers: list[BreakerBlock] | None = None,
    ) -> None:
        """Emit all breaker block lifecycle events."""
        prior_by_id = {breaker.breaker_id: breaker for breaker in (prior_breakers or [])}
        breakers_by_id = {breaker.breaker_id: breaker for breaker in analysis.breaker_blocks}

        for breaker in analysis.breaker_blocks:
            if breaker.breaker_id not in prior_by_id:
                self._publisher.publish_breaker_detected(breaker, analysis.symbol)
                if breaker.direction.value == "bullish":
                    self._publisher.publish_bullish_breaker(breaker, analysis.symbol)
                else:
                    self._publisher.publish_bearish_breaker(breaker, analysis.symbol)
                self._publisher.publish_candidate_breaker(breaker, analysis.symbol)

        for event in analysis.events:
            breaker = breakers_by_id.get(event.breaker_id or "")
            if breaker is None:
                continue
            if event.kind is BreakerBlockEventKind.CONFIRMED_BREAKER_BLOCK:
                self._publisher.publish_confirmed_breaker(breaker, analysis.symbol)
            elif event.kind is BreakerBlockEventKind.MITIGATED_BREAKER_BLOCK:
                self._publisher.publish_mitigated_breaker(breaker, analysis.symbol)
            elif event.kind is BreakerBlockEventKind.INVALIDATED_BREAKER_BLOCK:
                self._publisher.publish_invalidated_breaker(breaker, analysis.symbol)
            elif event.kind is BreakerBlockEventKind.EXPIRED_BREAKER_BLOCK:
                self._publisher.publish_expired_breaker(breaker, analysis.symbol)
            elif event.kind is BreakerBlockEventKind.LIQUIDITY_CONFLUENCE_BREAKER:
                self._publisher.publish_liquidity_confluence(
                    breaker,
                    analysis.symbol,
                    timeframe=analysis.timeframe,
                )
            elif event.kind is BreakerBlockEventKind.FVG_CONFLUENCE_BREAKER:
                self._publisher.publish_fvg_confluence(
                    breaker,
                    analysis.symbol,
                    timeframe=analysis.timeframe,
                )

        self._publisher.publish_analysis_completed(analysis)

    def reset_state(self) -> None:
        self._prior_state = None
        logger.info("Breaker block engine state reset")

    def handle_config_updated(self, config: BreakerBlockConfig) -> None:
        self._config = config
        self._detector = BreakerBlockDetector(config)
        self._lifecycle = LifecycleManager(config)
        self._quality = QualityScorer(config)
        logger.info("Breaker block configuration updated")

    @staticmethod
    def _validate_unique_breakers(breakers: list[BreakerBlock]) -> None:
        seen: set[str] = set()
        for breaker in breakers:
            if breaker.breaker_id in seen:
                raise DuplicateBreakerError(
                    "Duplicate breaker identifiers in analysis output",
                    details={"breaker_id": breaker.breaker_id},
                )
            seen.add(breaker.breaker_id)
