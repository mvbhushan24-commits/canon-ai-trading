"""Premium / Discount Engine orchestrator."""

import logging
from decimal import Decimal

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_mitigation.schemas import MitigationBlock
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_premium_discount.config import (
    PremiumDiscountConfig,
    load_market_premium_discount_config,
)
from backend.engines.market_premium_discount.detector import PremiumDiscountDetector
from backend.engines.market_premium_discount.exceptions import (
    InsufficientDataError,
    PremiumDiscountError,
    UnsupportedTimeframeError,
)
from backend.engines.market_premium_discount.lifecycle import LifecycleManager
from backend.engines.market_premium_discount.origin import DealingRangeBuilder
from backend.engines.market_premium_discount.publisher import PremiumDiscountEventPublisher
from backend.engines.market_premium_discount.quality import QualityScorer
from backend.engines.market_premium_discount.schemas import (
    DealingRange,
    DealingRangeScope,
    FibonacciDealingRange,
    InstitutionalArray,
    InstitutionalPricingContext,
    OptimalTradeEntryZone,
    PremiumDiscountAnalysis,
    PremiumDiscountContext,
    PremiumDiscountEventKind,
    PremiumDiscountState,
    PremiumDiscountZone,
    SwingAnchor,
)
from backend.engines.market_premium_discount.validator import PremiumDiscountInputValidator
from backend.engines.market_structure import MarketStructure

logger = logging.getLogger(__name__)


class PremiumDiscountEngine:
    """Institutional premium / discount detection and pricing context engine."""

    def __init__(
        self,
        config: PremiumDiscountConfig | None = None,
        detector: PremiumDiscountDetector | None = None,
        validator: PremiumDiscountInputValidator | None = None,
        publisher: PremiumDiscountEventPublisher | None = None,
    ) -> None:
        self._config = config or load_market_premium_discount_config()
        self._detector = detector or PremiumDiscountDetector(self._config)
        self._validator = validator or PremiumDiscountInputValidator()
        self._publisher = publisher or PremiumDiscountEventPublisher()
        self._range_builder = DealingRangeBuilder(self._config)
        self._lifecycle = LifecycleManager(self._config)
        self._quality = QualityScorer(self._config)
        self._prior_state: PremiumDiscountState | None = None

    @property
    def config(self) -> PremiumDiscountConfig:
        return self._config

    @property
    def publisher(self) -> PremiumDiscountEventPublisher:
        return self._publisher

    @property
    def prior_state(self) -> PremiumDiscountState | None:
        return self._prior_state

    def analyze(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
        *,
        timeframe: str | None = None,
        current_price: Decimal | None = None,
        prior_state: PremiumDiscountState | None = None,
        htf_premium_discount_context: PremiumDiscountContext | None = None,
    ) -> PremiumDiscountAnalysis:
        """Analyze premium / discount context from candles and upstream engines."""
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
                mitigation_blocks,
                state,
                htf_premium_discount_context,
            )
        except PremiumDiscountError as exc:
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
            "Analyzing premium / discount context",
            extra={
                "symbol": candles[0].symbol,
                "timeframe": target_timeframe,
                "candles": len(closed),
                "structure": structure is not None,
                "liquidity_state": liquidity_state is not None,
                "order_blocks": len(order_blocks or []),
                "fvg_state": fair_value_gap_state is not None,
                "breaker_blocks": len(breaker_blocks or []),
                "mitigation_blocks": len(mitigation_blocks or []),
                "htf_context": htf_premium_discount_context is not None,
            },
        )

        analysis = self._detector.detect(
            closed,
            structure,
            liquidity_state,
            order_blocks,
            fair_value_gap_state,
            breaker_blocks,
            mitigation_blocks,
            state,
            htf_premium_discount_context,
            current_price=current_price,
        )
        self.publish_events(analysis, prior_state=state)
        self._prior_state = analysis.state

        logger.info(
            "Premium / discount analysis complete",
            extra={
                "symbol": analysis.symbol,
                "timeframe": analysis.timeframe,
                "bias": analysis.bias.value,
                "quality": analysis.quality.value,
                "price_location": analysis.price_location.value,
            },
        )
        return analysis

    def build_dealing_range(
        self,
        structure: MarketStructure | None,
        scope: DealingRangeScope,
        candles: list[NormalizedCandle],
    ) -> DealingRange:
        """Construct dealing range for scope."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        timeframe = closed[0].timeframe if closed else "H1"
        dealing_range = self._range_builder.build(structure, scope, closed, timeframe=timeframe)
        return self._lifecycle.apply_invalidation(dealing_range, closed, structure)

    def select_swing_anchors(
        self,
        structure: MarketStructure,
        scope: DealingRangeScope,
        candles: list[NormalizedCandle],
    ) -> tuple[SwingAnchor | None, SwingAnchor | None]:
        """Select swing high and low anchors."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        from backend.engines.market_premium_discount.origin import SwingAnchorSelector

        selector = SwingAnchorSelector(self._config)
        return selector.select_anchors(structure, scope, closed)

    def classify_price(self, price: Decimal, dealing_range: DealingRange) -> PremiumDiscountZone:
        """Classify price location relative to dealing range."""
        return self._lifecycle.classify_price(price, dealing_range)

    def classify_zone(self, midpoint: Decimal, dealing_range: DealingRange) -> PremiumDiscountZone:
        """Classify zone territory by midpoint."""
        return self._lifecycle.classify_price(midpoint, dealing_range)

    def assemble_premium_arrays(
        self,
        candles: list[NormalizedCandle],
        dealing_range: DealingRange,
        *,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
        liquidity_state: LiquidityState | None = None,
    ) -> list[InstitutionalArray]:
        """Build premium institutional arrays."""
        entries = self._quality.collect_zone_entries(
            order_blocks=order_blocks,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            mitigation_blocks=mitigation_blocks,
            liquidity_state=liquidity_state,
            dealing_range=dealing_range,
        )
        return self._quality.assemble_arrays(entries, dealing_range, PremiumDiscountZone.PREMIUM)

    def assemble_discount_arrays(
        self,
        candles: list[NormalizedCandle],
        dealing_range: DealingRange,
        *,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
        liquidity_state: LiquidityState | None = None,
    ) -> list[InstitutionalArray]:
        """Build discount institutional arrays."""
        entries = self._quality.collect_zone_entries(
            order_blocks=order_blocks,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            mitigation_blocks=mitigation_blocks,
            liquidity_state=liquidity_state,
            dealing_range=dealing_range,
        )
        return self._quality.assemble_arrays(entries, dealing_range, PremiumDiscountZone.DISCOUNT)

    def project_fibonacci(
        self,
        dealing_range: DealingRange,
        direction,
        structure: MarketStructure | None = None,
    ) -> FibonacciDealingRange:
        """Project Fibonacci levels within dealing range."""
        from backend.engines.market_premium_discount.schemas import FibDirection

        if direction is FibDirection.BEARISH:
            from backend.engines.market_premium_discount.bearish import BearishPremiumDiscountAnalyzer

            return BearishPremiumDiscountAnalyzer(self._config).project_fibonacci(dealing_range)
        from backend.engines.market_premium_discount.bullish import BullishPremiumDiscountAnalyzer

        return BullishPremiumDiscountAnalyzer(self._config).project_fibonacci(dealing_range)

    def derive_ote(
        self,
        dealing_range: DealingRange,
        fibonacci: FibonacciDealingRange,
        zone_entries,
        structure: MarketStructure | None = None,
    ) -> OptimalTradeEntryZone | None:
        """Derive OTE zone from dealing range and Fibonacci projection."""
        return self._detector._derive_ote(dealing_range, fibonacci, zone_entries, structure)

    def score_mtf_alignment(
        self,
        ltf_analysis: PremiumDiscountAnalysis,
        htf_context: PremiumDiscountContext,
    ):
        """Score MTF alignment for the analysis territory."""
        return self._quality.score_mtf_premium_alignment(
            ltf_timeframe=ltf_analysis.timeframe,
            ltf_range=ltf_analysis.dealing_range,
            ltf_location=ltf_analysis.price_location,
            ltf_arrays=ltf_analysis.premium_arrays,
            htf_context=htf_context,
            structure=None,
        )

    def build_institutional_context(
        self,
        analysis: PremiumDiscountAnalysis,
    ) -> InstitutionalPricingContext:
        """Return institutional pricing context from analysis."""
        return analysis.institutional_context

    def publish_events(
        self,
        analysis: PremiumDiscountAnalysis,
        *,
        prior_state: PremiumDiscountState | None = None,
    ) -> None:
        """Emit all premium / discount lifecycle events."""
        symbol = analysis.symbol

        if analysis.dealing_range.is_valid:
            if prior_state is None or prior_state.active_dealing_range is None:
                self._publisher.publish_dealing_range_established(
                    analysis.dealing_range,
                    symbol,
                )
            elif prior_state.active_dealing_range.range_id != analysis.dealing_range.range_id:
                self._publisher.publish_dealing_range_updated(analysis.dealing_range, symbol)
        elif prior_state and prior_state.active_dealing_range and prior_state.active_dealing_range.is_valid:
            self._publisher.publish_dealing_range_invalidated(
                prior_state.active_dealing_range,
                symbol,
            )

        for event in analysis.events:
            if event.kind is PremiumDiscountEventKind.SWING_HIGH_ANCHORED:
                self._publisher.publish_swing_high_anchored(analysis.swing_high, symbol)
            elif event.kind is PremiumDiscountEventKind.SWING_LOW_ANCHORED:
                self._publisher.publish_swing_low_anchored(analysis.swing_low, symbol)
            elif event.kind is PremiumDiscountEventKind.PREMIUM_ZONE_ENTERED:
                self._publisher.publish_premium_entered(
                    analysis.current_price,
                    symbol,
                    range_id=analysis.dealing_range.range_id,
                )
            elif event.kind is PremiumDiscountEventKind.DISCOUNT_ZONE_ENTERED:
                self._publisher.publish_discount_entered(
                    analysis.current_price,
                    symbol,
                    range_id=analysis.dealing_range.range_id,
                )
            elif event.kind is PremiumDiscountEventKind.EQUILIBRIUM_REACHED:
                self._publisher.publish_equilibrium_reached(
                    analysis.current_price,
                    symbol,
                    range_id=analysis.dealing_range.range_id,
                )
            elif event.kind is PremiumDiscountEventKind.PREMIUM_EXPIRED:
                self._publisher.publish_premium_expired(analysis.current_price, symbol)
            elif event.kind is PremiumDiscountEventKind.DISCOUNT_EXPIRED:
                self._publisher.publish_discount_expired(analysis.current_price, symbol)
            elif event.kind is PremiumDiscountEventKind.PREMIUM_QUALITY_UPDATED:
                self._publisher.publish_quality_updated(
                    symbol=symbol,
                    quality=analysis.quality.value,
                    strength=str(analysis.strength),
                    timestamp=analysis.timestamp_utc,
                )

        for array in analysis.premium_arrays:
            self._publisher.publish_premium_array(array, symbol)
        for array in analysis.discount_arrays:
            self._publisher.publish_discount_array(array, symbol)

        if analysis.internal_premium:
            self._publisher.publish_internal_premium(analysis.internal_premium, symbol)
        if analysis.internal_discount:
            self._publisher.publish_internal_discount(analysis.internal_discount, symbol)

        if analysis.htf_premium:
            self._publisher.publish_htf_premium(analysis.htf_premium, symbol)
        if analysis.htf_discount:
            self._publisher.publish_htf_discount(analysis.htf_discount, symbol)

        if analysis.mtf_premium_alignment:
            self._publisher.publish_mtf_premium_aligned(analysis.mtf_premium_alignment, symbol)
        if analysis.mtf_discount_alignment:
            self._publisher.publish_mtf_discount_aligned(analysis.mtf_discount_alignment, symbol)

        for nested in analysis.nested_premium_zones:
            self._publisher.publish_nested_premium(nested, symbol)
        for nested in analysis.nested_discount_zones:
            self._publisher.publish_nested_discount(nested, symbol)

        if analysis.fibonacci_range.levels:
            self._publisher.publish_fibonacci_computed(analysis.fibonacci_range, symbol)
        if analysis.ote_zone:
            self._publisher.publish_ote_derived(analysis.ote_zone, symbol)

        self._publisher.publish_institutional_context(analysis.institutional_context, symbol)
        self._publisher.publish_analysis_completed(analysis)

    def reset_state(self) -> None:
        self._prior_state = None
        logger.info("Premium / discount engine state reset")

    def handle_config_updated(self, config: PremiumDiscountConfig) -> None:
        self._config = config
        self._detector = PremiumDiscountDetector(config)
        self._range_builder = DealingRangeBuilder(config)
        self._lifecycle = LifecycleManager(config)
        self._quality = QualityScorer(config)
        logger.info("Premium / discount configuration updated")
