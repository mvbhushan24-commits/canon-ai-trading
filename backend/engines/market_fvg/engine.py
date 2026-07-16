"""Fair Value Gap Engine orchestrator."""

import logging
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.config import FairValueGapConfig, load_fair_value_gap_config
from backend.engines.market_fvg.detector import FairValueGapDetector
from backend.engines.market_fvg.exceptions import (
    DuplicateGapError,
    FairValueGapError,
    InsufficientDataError,
    UnsupportedTimeframeError,
)
from backend.engines.market_fvg.mitigation import MitigationManager
from backend.engines.market_fvg.publisher import FairValueGapEventPublisher
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapAnalysis,
    FairValueGapEventKind,
    FairValueGapState,
    MTFGapAlignment,
    PremiumDiscountZone,
)
from backend.engines.market_fvg.validator import FairValueGapInputValidator
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_order_block import OrderBlockState
from backend.engines.market_structure import MarketStructure

logger = logging.getLogger(__name__)


class FairValueGapEngine:
    """Institutional fair value gap detection and lifecycle engine."""

    def __init__(
        self,
        config: FairValueGapConfig | None = None,
        detector: FairValueGapDetector | None = None,
        validator: FairValueGapInputValidator | None = None,
        publisher: FairValueGapEventPublisher | None = None,
    ) -> None:
        self._config = config or load_fair_value_gap_config()
        self._detector = detector or FairValueGapDetector(self._config)
        self._validator = validator or FairValueGapInputValidator()
        self._publisher = publisher or FairValueGapEventPublisher()
        self._mitigation = MitigationManager(self._config)
        self._prior_state: FairValueGapState | None = None

    @property
    def config(self) -> FairValueGapConfig:
        return self._config

    @property
    def publisher(self) -> FairValueGapEventPublisher:
        return self._publisher

    @property
    def prior_state(self) -> FairValueGapState | None:
        return self._prior_state

    def analyze(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_block_state: OrderBlockState | None = None,
        *,
        timeframe: str | None = None,
        prior_state: FairValueGapState | None = None,
        higher_timeframe_gaps: list[FairValueGap] | None = None,
    ) -> FairValueGapAnalysis:
        """Analyze fair value gaps from candles and upstream context."""
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
                order_block_state,
                state,
            )
        except FairValueGapError as exc:
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
            "Analyzing fair value gaps",
            extra={
                "symbol": candles[0].symbol,
                "timeframe": target_timeframe,
                "candles": len(closed),
                "structure": structure is not None,
                "liquidity_state": liquidity_state is not None,
                "order_block_state": order_block_state is not None,
            },
        )

        analysis = self._detector.detect(
            closed,
            structure,
            liquidity_state,
            order_block_state,
            state,
            higher_timeframe_gaps,
        )
        self._validate_unique_gaps(analysis.fair_value_gaps)
        self.publish_events(analysis, prior_gaps=state.active_gaps if state else [])
        self._prior_state = analysis.state

        logger.info(
            "Fair value gap analysis complete",
            extra={
                "symbol": analysis.symbol,
                "timeframe": analysis.timeframe,
                "open": len(analysis.open_gaps),
                "partial": len(analysis.partial_gaps),
                "filled": len(analysis.filled_gaps),
                "mitigated": len(analysis.mitigated_gaps),
                "bias": analysis.bias.value,
            },
        )
        return analysis

    def detect_bullish_gaps(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_block_state: OrderBlockState | None = None,
    ) -> list[FairValueGap]:
        """Detect bullish fair value gaps only."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.detect_bullish_gaps(
            closed,
            structure,
            liquidity_state,
            order_block_state,
        )

    def detect_bearish_gaps(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_block_state: OrderBlockState | None = None,
    ) -> list[FairValueGap]:
        """Detect bearish fair value gaps only."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._detector.detect_bearish_gaps(
            closed,
            structure,
            liquidity_state,
            order_block_state,
        )

    def classify_lifecycle(
        self,
        gaps: list[FairValueGap],
        candles: list[NormalizedCandle],
    ) -> list[FairValueGap]:
        """Update lifecycle status for existing gaps."""
        return self._detector.classify_lifecycle(gaps, candles)

    def compute_fill_percent(
        self,
        gap: FairValueGap,
        candles: list[NormalizedCandle],
    ) -> Decimal:
        """Compute current fill percentage for a gap."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        return self._mitigation.compute_fill_percent(gap, closed)

    def classify_premium_discount(
        self,
        gap: FairValueGap,
        structure: MarketStructure | None,
    ) -> PremiumDiscountZone:
        """Classify gap premium/discount placement."""
        zone, _, _, _ = self._mitigation.classify_premium_discount(gap, structure)
        return zone

    def resolve_nesting(self, gaps: list[FairValueGap]) -> list[FairValueGap]:
        """Resolve nested parent-child gap relationships."""
        return self._detector.resolve_nesting(gaps)

    def score_mtf_alignment(
        self,
        gap: FairValueGap,
        higher_timeframe_gaps: list[FairValueGap] | None,
        *,
        timeframe: str,
    ) -> MTFGapAlignment | None:
        """Score multi-timeframe alignment for a gap."""
        return self._detector.score_mtf_alignment(
            gap,
            higher_timeframe_gaps,
            timeframe=timeframe,
        )

    def publish_events(
        self,
        analysis: FairValueGapAnalysis,
        *,
        prior_gaps: list[FairValueGap] | None = None,
    ) -> None:
        """Emit all fair value gap lifecycle events."""
        prior_by_id = {gap.gap_id: gap for gap in (prior_gaps or [])}
        gaps_by_id = {gap.gap_id: gap for gap in analysis.fair_value_gaps}

        for gap in analysis.fair_value_gaps:
            if gap.gap_id not in prior_by_id:
                self._publisher.publish_gap_detected(gap, analysis.symbol)
                if gap.direction.value == "bullish":
                    self._publisher.publish_bullish_gap(gap, analysis.symbol)
                else:
                    self._publisher.publish_bearish_gap(gap, analysis.symbol)

        for event in analysis.events:
            gap = gaps_by_id.get(event.gap_id or "")
            if gap is None:
                continue

            if event.kind is FairValueGapEventKind.OPEN_FAIR_VALUE_GAP:
                self._publisher.publish_open_gap(gap, analysis.symbol)
            elif event.kind is FairValueGapEventKind.PARTIAL_FILL_FAIR_VALUE_GAP:
                self._publisher.publish_partial_fill(gap, analysis.symbol)
            elif event.kind is FairValueGapEventKind.CE_ENCROACHED:
                self._publisher.publish_ce_encroached(gap, analysis.symbol)
            elif event.kind is FairValueGapEventKind.FILLED_FAIR_VALUE_GAP:
                self._publisher.publish_filled(gap, analysis.symbol)
            elif event.kind is FairValueGapEventKind.MITIGATED_FAIR_VALUE_GAP:
                self._publisher.publish_mitigated(gap, analysis.symbol)
            elif event.kind is FairValueGapEventKind.INVALIDATED_FAIR_VALUE_GAP:
                self._publisher.publish_invalidated(gap, analysis.symbol)
            elif event.kind is FairValueGapEventKind.EXPIRED_FAIR_VALUE_GAP:
                self._publisher.publish_expired(gap, analysis.symbol)
            elif event.kind is FairValueGapEventKind.NESTED_FAIR_VALUE_GAP:
                parent = gaps_by_id.get(gap.nested_parent_gap_id or "")
                if parent is not None:
                    self._publisher.publish_nested(
                        child=gap,
                        parent=parent,
                        symbol=analysis.symbol,
                        timeframe=analysis.timeframe,
                    )
            elif event.kind is FairValueGapEventKind.MTF_ALIGNED_FAIR_VALUE_GAP:
                if gap.mtf_alignment is not None:
                    self._publisher.publish_mtf_aligned(
                        gap,
                        gap.mtf_alignment,
                        analysis.symbol,
                    )

        self._publisher.publish_analysis_completed(analysis)

    def reset_state(self) -> None:
        self._prior_state = None
        logger.info("Fair value gap engine state reset")

    def handle_config_updated(self, config: FairValueGapConfig) -> None:
        self._config = config
        self._detector = FairValueGapDetector(config)
        self._mitigation = MitigationManager(config)
        logger.info("Fair value gap configuration updated")

    @staticmethod
    def _validate_unique_gaps(gaps: list[FairValueGap]) -> None:
        seen: set[str] = set()
        for gap in gaps:
            if gap.gap_id in seen:
                raise DuplicateGapError(
                    "Duplicate fair value gap identifiers in analysis output",
                    details={"gap_id": gap.gap_id},
                )
            seen.add(gap.gap_id)
