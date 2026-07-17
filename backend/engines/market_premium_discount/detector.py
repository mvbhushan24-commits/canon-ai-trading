"""Premium / discount detection orchestrator."""

from decimal import Decimal

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_mitigation.schemas import MitigationBlock
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_premium_discount.bearish import BearishPremiumDiscountAnalyzer
from backend.engines.market_premium_discount.bullish import BullishPremiumDiscountAnalyzer
from backend.engines.market_premium_discount.config import (
    PremiumDiscountConfig,
    PriceReferenceMode,
)
from backend.engines.market_premium_discount.lifecycle import LifecycleManager
from backend.engines.market_premium_discount.origin import DealingRangeBuilder
from backend.engines.market_premium_discount.quality import QualityScorer
from backend.engines.market_premium_discount.schemas import (
    DealingRangeScope,
    FibDirection,
    FibonacciDealingRange,
    InstitutionalPricingContext,
    PremiumDiscountAnalysis,
    PremiumDiscountBias,
    PremiumDiscountContext,
    PremiumDiscountEvent,
    PremiumDiscountEventKind,
    PremiumDiscountQuality,
    PremiumDiscountState,
    PremiumDiscountZone,
    PriceZoneBand,
)
from backend.engines.market_structure import MarketStructure


class PremiumDiscountDetector:
    """Orchestrate premium / discount analysis pipeline."""

    def __init__(
        self,
        config: PremiumDiscountConfig,
        range_builder: DealingRangeBuilder | None = None,
        lifecycle: LifecycleManager | None = None,
        quality: QualityScorer | None = None,
        bullish: BullishPremiumDiscountAnalyzer | None = None,
        bearish: BearishPremiumDiscountAnalyzer | None = None,
    ) -> None:
        self._config = config
        self._range_builder = range_builder or DealingRangeBuilder(config)
        self._lifecycle = lifecycle or LifecycleManager(config)
        self._quality = quality or QualityScorer(config)
        self._bullish = bullish or BullishPremiumDiscountAnalyzer(config)
        self._bearish = bearish or BearishPremiumDiscountAnalyzer(config)

    def detect(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_blocks: list[OrderBlock] | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        mitigation_blocks: list[MitigationBlock] | None = None,
        prior_state: PremiumDiscountState | None = None,
        htf_premium_discount_context: PremiumDiscountContext | None = None,
        *,
        current_price: Decimal | None = None,
    ) -> PremiumDiscountAnalysis:
        """Run full premium / discount analysis pipeline."""
        sorted_candles = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        if not sorted_candles:
            sorted_candles = sorted(candles, key=lambda candle: candle.open_time_utc)

        symbol = sorted_candles[0].symbol
        timeframe = sorted_candles[0].timeframe.upper()
        analysis_time = sorted_candles[-1].close_time_utc
        bar_count = len(sorted_candles)
        reference_price = current_price or self._resolve_price(sorted_candles[-1])

        evidence: list[str] = []
        events: list[PremiumDiscountEvent] = []

        if structure is None:
            evidence.append("Structure context unavailable")

        external = self._range_builder.build(
            structure,
            DealingRangeScope.EXTERNAL,
            sorted_candles,
            timeframe=timeframe,
        )
        internal = self._range_builder.build(
            structure,
            DealingRangeScope.INTERNAL,
            sorted_candles,
            timeframe=timeframe,
        )

        external = self._lifecycle.apply_invalidation(external, sorted_candles, structure)
        internal = self._lifecycle.apply_invalidation(internal, sorted_candles, structure)
        external = self._quality.score_range(external, structure)
        internal = self._quality.score_range(internal, structure)

        primary = self._lifecycle.merge_primary_range(external, internal)
        if not primary.is_valid:
            evidence.append(primary.invalidation_reason or "Dealing range invalid")
            evidence.append("PD_DEALING_RANGE_INVALID")

        premium_zone, discount_zone, equilibrium = self._lifecycle.build_zones(primary)
        price_location = self._lifecycle.classify_price(reference_price, primary)

        prior_location = (
            prior_state.last_price_location
            if prior_state
            else PremiumDiscountZone.EQUILIBRIUM
        )
        events.extend(
            self._lifecycle.detect_territory_events(
                current_price=reference_price,
                current_location=price_location,
                prior_location=prior_location,
                dealing_range=primary,
                timeframe=timeframe,
                timestamp=analysis_time,
            ),
        )

        if external.is_valid and (
            prior_state is None
            or prior_state.active_external_range is None
            or prior_state.active_external_range.range_id != external.range_id
        ):
            events.append(self._range_event(
                PremiumDiscountEventKind.DEALING_RANGE_ESTABLISHED,
                external,
                timeframe,
                analysis_time,
                "External dealing range established",
            ))
            events.append(self._swing_event(
                PremiumDiscountEventKind.SWING_HIGH_ANCHORED,
                external.swing_high,
                timeframe,
                analysis_time,
            ))
            events.append(self._swing_event(
                PremiumDiscountEventKind.SWING_LOW_ANCHORED,
                external.swing_low,
                timeframe,
                analysis_time,
            ))

        zone_entries = self._quality.collect_zone_entries(
            order_blocks=order_blocks,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            mitigation_blocks=mitigation_blocks,
            liquidity_state=liquidity_state,
            dealing_range=primary,
        )
        premium_arrays = self._quality.assemble_arrays(
            zone_entries,
            primary,
            PremiumDiscountZone.PREMIUM,
        )
        discount_arrays = self._quality.assemble_arrays(
            zone_entries,
            primary,
            PremiumDiscountZone.DISCOUNT,
        )

        for array in premium_arrays:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.PREMIUM_ARRAY_FORMED,
                    timestamp_utc=analysis_time,
                    timeframe=timeframe,
                    description=f"Premium array formed with {array.entry_count} entries",
                    array_id=array.array_id,
                    territory=PremiumDiscountZone.PREMIUM,
                ),
            )
        for array in discount_arrays:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.DISCOUNT_ARRAY_FORMED,
                    timestamp_utc=analysis_time,
                    timeframe=timeframe,
                    description=f"Discount array formed with {array.entry_count} entries",
                    array_id=array.array_id,
                    territory=PremiumDiscountZone.DISCOUNT,
                ),
            )

        internal_premium: PriceZoneBand | None = None
        internal_discount: PriceZoneBand | None = None
        if self._config.compute_internal_bands and internal.is_valid:
            internal_premium, internal_discount, _ = self._lifecycle.build_zones(internal)
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.INTERNAL_PREMIUM_CLASSIFIED,
                    timestamp_utc=analysis_time,
                    timeframe=timeframe,
                    description="Internal premium band classified",
                    range_id=internal.range_id,
                    territory=PremiumDiscountZone.PREMIUM,
                ),
            )
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.INTERNAL_DISCOUNT_CLASSIFIED,
                    timestamp_utc=analysis_time,
                    timeframe=timeframe,
                    description="Internal discount band classified",
                    range_id=internal.range_id,
                    territory=PremiumDiscountZone.DISCOUNT,
                ),
            )

        htf_premium = None
        htf_discount = None
        mtf_premium = None
        mtf_discount = None
        if htf_premium_discount_context is not None:
            htf_premium, htf_discount = self._quality.build_htf_contexts(
                htf_premium_discount_context,
            )
            if htf_premium:
                events.append(
                    PremiumDiscountEvent(
                        kind=PremiumDiscountEventKind.HTF_PREMIUM_CONTEXT,
                        timestamp_utc=analysis_time,
                        timeframe=timeframe,
                        description="HTF premium context applied",
                    ),
                )
            if htf_discount:
                events.append(
                    PremiumDiscountEvent(
                        kind=PremiumDiscountEventKind.HTF_DISCOUNT_CONTEXT,
                        timestamp_utc=analysis_time,
                        timeframe=timeframe,
                        description="HTF discount context applied",
                    ),
                )
            mtf_premium = self._quality.score_mtf_premium_alignment(
                ltf_timeframe=timeframe,
                ltf_range=primary,
                ltf_location=price_location,
                ltf_arrays=premium_arrays,
                htf_context=htf_premium_discount_context,
                structure=structure,
            )
            mtf_discount = self._quality.score_mtf_discount_alignment(
                ltf_timeframe=timeframe,
                ltf_range=primary,
                ltf_location=price_location,
                ltf_arrays=discount_arrays,
                htf_context=htf_premium_discount_context,
                structure=structure,
            )
            if mtf_premium:
                events.append(
                    PremiumDiscountEvent(
                        kind=PremiumDiscountEventKind.MTF_PREMIUM_ALIGNED,
                        timestamp_utc=analysis_time,
                        timeframe=timeframe,
                        description="MTF premium alignment detected",
                        territory=PremiumDiscountZone.PREMIUM,
                    ),
                )
            if mtf_discount:
                events.append(
                    PremiumDiscountEvent(
                        kind=PremiumDiscountEventKind.MTF_DISCOUNT_ALIGNED,
                        timestamp_utc=analysis_time,
                        timeframe=timeframe,
                        description="MTF discount alignment detected",
                        territory=PremiumDiscountZone.DISCOUNT,
                    ),
                )
        else:
            evidence.append("HTF context unavailable")

        nested_premium, nested_discount = self._quality.detect_nested_zones(
            zone_entries,
            primary,
        )
        for nested in nested_premium:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.NESTED_PREMIUM_ZONE,
                    timestamp_utc=analysis_time,
                    timeframe=timeframe,
                    description=nested.evidence[0] if nested.evidence else "Nested premium zone",
                    territory=PremiumDiscountZone.PREMIUM,
                ),
            )
        for nested in nested_discount:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.NESTED_DISCOUNT_ZONE,
                    timestamp_utc=analysis_time,
                    timeframe=timeframe,
                    description=nested.evidence[0] if nested.evidence else "Nested discount zone",
                    territory=PremiumDiscountZone.DISCOUNT,
                ),
            )

        fibonacci = self._project_fibonacci(primary, structure)
        if self._config.fibonacci_enabled and primary.is_valid:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.FIBONACCI_RANGE_COMPUTED,
                    timestamp_utc=analysis_time,
                    timeframe=timeframe,
                    description="Fibonacci dealing range computed",
                    range_id=primary.range_id,
                ),
            )

        ote_zone = self._derive_ote(primary, fibonacci, zone_entries, structure)
        if ote_zone is not None:
            events.append(
                PremiumDiscountEvent(
                    kind=PremiumDiscountEventKind.OTE_ZONE_DERIVED,
                    timestamp_utc=analysis_time,
                    timeframe=timeframe,
                    description="OTE zone derived",
                    ote_id=ote_zone.ote_id,
                    territory=ote_zone.territory,
                ),
            )

        strength, quality, bias, confidence = self._quality.score_analysis(
            dealing_range=primary,
            structure=structure,
            price_location=price_location,
            current_price=reference_price,
            liquidity_state=liquidity_state,
            zone_entries=zone_entries,
            htf_context=htf_premium_discount_context,
            mtf_premium=mtf_premium,
            mtf_discount=mtf_discount,
            bar_count=bar_count,
        )
        events.append(
            PremiumDiscountEvent(
                kind=PremiumDiscountEventKind.PREMIUM_QUALITY_UPDATED,
                timestamp_utc=analysis_time,
                timeframe=timeframe,
                description=f"Analysis quality updated to {quality.value}",
            ),
        )

        institutional_context = self._build_institutional_context(
            primary=primary,
            price_location=price_location,
            premium_arrays=premium_arrays,
            discount_arrays=discount_arrays,
            mtf_premium=mtf_premium,
            mtf_discount=mtf_discount,
            ote_zone=ote_zone,
            structure=structure,
            liquidity_state=liquidity_state,
            confidence=confidence,
        )
        events.append(
            PremiumDiscountEvent(
                kind=PremiumDiscountEventKind.INSTITUTIONAL_CONTEXT_UPDATED,
                timestamp_utc=analysis_time,
                timeframe=timeframe,
                description="Institutional pricing context updated",
            ),
        )

        if bias is PremiumDiscountBias.UNDETERMINED:
            evidence.extend(primary.evidence)
        else:
            evidence.append(f"Price in {price_location.value} relative to equilibrium")
            evidence.append(f"Primary range scope: {primary.scope.value}")

        state = PremiumDiscountState(
            active_dealing_range=primary if primary.is_valid else None,
            active_external_range=external if external.is_valid else None,
            active_internal_range=internal if internal.is_valid else None,
            last_price_location=price_location,
            last_analysis_utc=analysis_time,
            bar_count=bar_count,
        )

        events.append(
            PremiumDiscountEvent(
                kind=PremiumDiscountEventKind.PREMIUM_DISCOUNT_UPDATED,
                timestamp_utc=analysis_time,
                timeframe=timeframe,
                description="Premium / discount analysis complete",
                range_id=primary.range_id,
            ),
        )

        return PremiumDiscountAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_utc=analysis_time,
            current_price=reference_price,
            dealing_range=primary,
            external_range=external,
            internal_range=internal,
            swing_high=primary.swing_high,
            swing_low=primary.swing_low,
            premium_zone=premium_zone,
            discount_zone=discount_zone,
            equilibrium=equilibrium,
            price_location=price_location,
            premium_arrays=premium_arrays,
            discount_arrays=discount_arrays,
            internal_premium=internal_premium,
            internal_discount=internal_discount,
            htf_premium=htf_premium,
            htf_discount=htf_discount,
            mtf_premium_alignment=mtf_premium,
            mtf_discount_alignment=mtf_discount,
            nested_premium_zones=nested_premium,
            nested_discount_zones=nested_discount,
            fibonacci_range=fibonacci,
            ote_zone=ote_zone,
            institutional_context=institutional_context,
            bias=bias,
            confidence=confidence,
            quality=quality,
            strength=strength,
            evidence=evidence,
            state=state,
            events=events,
        )

    def _resolve_price(self, candle: NormalizedCandle) -> Decimal:
        mode = self._config.price_reference
        if mode == PriceReferenceMode.MID.value:
            return (candle.high + candle.low) / Decimal("2")
        if mode == PriceReferenceMode.HLC3.value:
            return (candle.high + candle.low + candle.close) / Decimal("3")
        return candle.close

    def _project_fibonacci(
        self,
        dealing_range,
        structure: MarketStructure | None,
    ) -> FibonacciDealingRange:
        if not self._config.fibonacci_enabled or not dealing_range.is_valid:
            direction = FibDirection.BULLISH
            return FibonacciDealingRange(
                range_id=dealing_range.range_id,
                direction=direction,
                levels=[],
                ote_low_level=dealing_range.low,
                ote_high_level=dealing_range.low,
                equilibrium_level=dealing_range.equilibrium,
            )

        direction = self._quality.resolve_fib_direction(structure)
        if direction is FibDirection.BEARISH:
            return self._bearish.project_fibonacci(dealing_range)
        return self._bullish.project_fibonacci(dealing_range)

    def _derive_ote(self, dealing_range, fibonacci, zone_entries, structure):
        if not self._config.ote_enabled or not dealing_range.is_valid:
            return None
        direction = self._quality.resolve_fib_direction(structure)
        if direction is FibDirection.BEARISH:
            return self._bearish.derive_ote(dealing_range, fibonacci, zone_entries)
        return self._bullish.derive_ote(dealing_range, fibonacci, zone_entries)

    def _build_institutional_context(
        self,
        *,
        primary,
        price_location,
        premium_arrays,
        discount_arrays,
        mtf_premium,
        mtf_discount,
        ote_zone,
        structure,
        liquidity_state,
        confidence,
    ) -> InstitutionalPricingContext:
        narrative: list[str] = [
            f"Active dealing range ({primary.scope.value}): {primary.low} – {primary.high}",
            f"Equilibrium at {primary.equilibrium}",
            f"Current price in {price_location.value} territory",
        ]

        if premium_arrays or discount_arrays:
            if len(premium_arrays) >= len(discount_arrays):
                narrative.append(f"{len(premium_arrays)} premium array(s) active")
            else:
                narrative.append(f"{len(discount_arrays)} discount array(s) active")

        if self._config.institutional_include_htf_in_narrative:
            if mtf_premium or mtf_discount:
                narrative.append("Multi-timeframe alignment detected")
            else:
                narrative.append("HTF alignment not confirmed")

        if self._config.institutional_include_ote_in_narrative:
            if ote_zone:
                narrative.append(
                    f"OTE available in {ote_zone.territory.value} ({ote_zone.low} – {ote_zone.high})",
                )
            else:
                narrative.append("OTE not derivable")

        if structure:
            narrative.append(f"Structure trend: {structure.current_trend.value}")
        if liquidity_state and liquidity_state.recent_sweeps:
            narrative.append(f"{len(liquidity_state.recent_sweeps)} recent liquidity sweep(s)")

        narrative = narrative[: self._config.institutional_max_narrative_lines]
        dominant = None
        if len(premium_arrays) > len(discount_arrays):
            dominant = PremiumDiscountZone.PREMIUM
        elif len(discount_arrays) > len(premium_arrays):
            dominant = PremiumDiscountZone.DISCOUNT

        return InstitutionalPricingContext(
            narrative=narrative,
            current_price_location=price_location,
            preferred_buy_territory=PremiumDiscountZone.DISCOUNT,
            preferred_sell_territory=PremiumDiscountZone.PREMIUM,
            active_dealing_range_scope=primary.scope,
            structure_trend=structure.current_trend if structure else None,
            liquidity_bias=(
                liquidity_state.recent_sweeps[-1].direction.value
                if liquidity_state and liquidity_state.recent_sweeps
                else None
            ),
            dominant_array_territory=dominant,
            mtf_aligned=bool(mtf_premium or mtf_discount),
            ote_available=ote_zone is not None,
            confidence=confidence,
        )

    @staticmethod
    def _range_event(kind, dealing_range, timeframe, timestamp, description):
        return PremiumDiscountEvent(
            kind=kind,
            timestamp_utc=timestamp,
            timeframe=timeframe,
            description=description,
            range_id=dealing_range.range_id,
        )

    @staticmethod
    def _swing_event(kind, anchor, timeframe, timestamp):
        return PremiumDiscountEvent(
            kind=kind,
            timestamp_utc=timestamp,
            timeframe=timeframe,
            description=f"Swing {anchor.kind.value} anchored at {anchor.price}",
            price=anchor.price,
        )
