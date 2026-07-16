"""Fair value gap detection orchestrator."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.bearish import BearishFVGDetector
from backend.engines.market_fvg.bullish import BullishFVGDetector
from backend.engines.market_fvg.config import FairValueGapConfig
from backend.engines.market_fvg.mitigation import LifecycleUpdate, MitigationManager
from backend.engines.market_fvg.quality import MTFAlignmentScorer, QualityScorer
from backend.engines.market_fvg.schemas import (
    FVGFormationCandidate,
    FairValueGap,
    FairValueGapAnalysis,
    FairValueGapBias,
    FairValueGapDirection,
    FairValueGapEvent,
    FairValueGapEventKind,
    FairValueGapQuality,
    FairValueGapState,
    FairValueGapStatus,
    MTFGapAlignment,
    PremiumDiscountZone,
)
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_order_block import OrderBlockState
from backend.engines.market_structure import MarketStructure


class FairValueGapDetector:
    """Orchestrate formation, lifecycle, nesting, MTF, and quality detection."""

    def __init__(
        self,
        config: FairValueGapConfig,
        bullish_detector: BullishFVGDetector | None = None,
        bearish_detector: BearishFVGDetector | None = None,
        mitigation_manager: MitigationManager | None = None,
        quality_scorer: QualityScorer | None = None,
        mtf_scorer: MTFAlignmentScorer | None = None,
    ) -> None:
        self._config = config
        self._bullish = bullish_detector or BullishFVGDetector()
        self._bearish = bearish_detector or BearishFVGDetector()
        self._mitigation = mitigation_manager or MitigationManager(config)
        self._quality = quality_scorer or QualityScorer(config)
        self._mtf = mtf_scorer or MTFAlignmentScorer(config)
        self._ce_encroached_ids: set[str] = set()

    def detect(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_block_state: OrderBlockState | None = None,
        prior_state: FairValueGapState | None = None,
        higher_timeframe_gaps: list[FairValueGap] | None = None,
    ) -> FairValueGapAnalysis:
        """Run full fair value gap analysis pipeline."""
        sorted_candles = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        if not sorted_candles:
            sorted_candles = sorted(candles, key=lambda candle: candle.open_time_utc)

        lookback = min(len(sorted_candles), self._config.lookback)
        scan_candles = sorted_candles[-lookback:]
        symbol = scan_candles[0].symbol
        timeframe = scan_candles[0].timeframe
        analysis_time = scan_candles[-1].close_time_utc
        bar_count = len(sorted_candles)

        bullish_gaps = self.detect_bullish_gaps(
            scan_candles,
            structure,
            liquidity_state,
            order_block_state,
            higher_timeframe_gaps=higher_timeframe_gaps,
            timeframe=timeframe,
        )
        bearish_gaps = self.detect_bearish_gaps(
            scan_candles,
            structure,
            liquidity_state,
            order_block_state,
            higher_timeframe_gaps=higher_timeframe_gaps,
            timeframe=timeframe,
        )
        detected = bullish_gaps + bearish_gaps

        prior_gaps = prior_state.active_gaps if prior_state else []
        merged = self._merge_gaps(prior_gaps, detected)
        lifecycle_updates = self._mitigation.classify_gaps(
            merged,
            scan_candles,
            current_bar_count=bar_count,
        )
        classified = [update.gap for update in lifecycle_updates]
        nested = self.resolve_nesting(classified)

        open_gaps = [g for g in nested if g.status is FairValueGapStatus.OPEN]
        partial_gaps = [g for g in nested if g.status is FairValueGapStatus.PARTIAL]
        filled_gaps = [g for g in nested if g.status is FairValueGapStatus.FILLED]
        mitigated_gaps = [g for g in nested if g.status is FairValueGapStatus.MITIGATED]
        invalidated_gaps = [g for g in nested if g.status is FairValueGapStatus.INVALIDATED]
        expired_gaps = [g for g in nested if g.status is FairValueGapStatus.EXPIRED]

        bias, confidence, evidence = self._determine_bias(open_gaps, partial_gaps)
        events = self._build_timeline_events(
            nested,
            lifecycle_updates,
            scan_candles,
            timeframe,
            prior_gaps,
        )

        active_gaps = open_gaps + partial_gaps
        state = FairValueGapState(
            active_gaps=active_gaps,
            last_analysis_utc=analysis_time,
            bar_count=bar_count,
        )

        return FairValueGapAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_utc=analysis_time,
            fair_value_gaps=nested,
            open_gaps=open_gaps,
            partial_gaps=partial_gaps,
            filled_gaps=filled_gaps,
            mitigated_gaps=mitigated_gaps,
            invalidated_gaps=invalidated_gaps,
            expired_gaps=expired_gaps,
            bullish_gaps=[g for g in nested if g.direction is FairValueGapDirection.BULLISH],
            bearish_gaps=[g for g in nested if g.direction is FairValueGapDirection.BEARISH],
            bias=bias,
            confidence=confidence,
            evidence=evidence,
            state=state,
            events=sorted(events, key=lambda event: event.timestamp_utc),
        )

    def detect_bullish_gaps(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_block_state: OrderBlockState | None = None,
        *,
        higher_timeframe_gaps: list[FairValueGap] | None = None,
        timeframe: str | None = None,
    ) -> list[FairValueGap]:
        """Detect bullish fair value gaps only."""
        candidates = self._bullish.find_formations(candles)
        target_timeframe = timeframe or candles[0].timeframe
        return self._candidates_to_gaps(
            candidates,
            candles,
            structure,
            liquidity_state,
            order_block_state,
            higher_timeframe_gaps=higher_timeframe_gaps,
            timeframe=target_timeframe,
        )

    def detect_bearish_gaps(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity_state: LiquidityState | None = None,
        order_block_state: OrderBlockState | None = None,
        *,
        higher_timeframe_gaps: list[FairValueGap] | None = None,
        timeframe: str | None = None,
    ) -> list[FairValueGap]:
        """Detect bearish fair value gaps only."""
        candidates = self._bearish.find_formations(candles)
        target_timeframe = timeframe or candles[0].timeframe
        return self._candidates_to_gaps(
            candidates,
            candles,
            structure,
            liquidity_state,
            order_block_state,
            higher_timeframe_gaps=higher_timeframe_gaps,
            timeframe=target_timeframe,
        )

    def classify_lifecycle(
        self,
        gaps: list[FairValueGap],
        candles: list[NormalizedCandle],
    ) -> list[FairValueGap]:
        """Update open, partial, filled, mitigated, invalidated, and expired status."""
        closed = sorted(
            [c for c in candles if c.is_closed],
            key=lambda candle: candle.open_time_utc,
        )
        updates = self._mitigation.classify_gaps(
            gaps,
            closed,
            current_bar_count=len(closed),
        )
        return [update.gap for update in updates]

    def resolve_nesting(self, gaps: list[FairValueGap]) -> list[FairValueGap]:
        """Resolve parent-child nesting relationships."""
        return self._mitigation.resolve_nesting(gaps)

    def score_mtf_alignment(
        self,
        gap: FairValueGap,
        higher_timeframe_gaps: list[FairValueGap] | None,
        *,
        timeframe: str,
    ) -> MTFGapAlignment | None:
        """Score multi-timeframe alignment for a single gap."""
        return self._mtf.score(
            gap,
            higher_timeframe_gaps,
            timeframe=timeframe,
        )

    def _candidates_to_gaps(
        self,
        candidates: list[FVGFormationCandidate],
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
        liquidity_state: LiquidityState | None,
        order_block_state: OrderBlockState | None,
        *,
        higher_timeframe_gaps: list[FairValueGap] | None,
        timeframe: str,
    ) -> list[FairValueGap]:
        gaps: list[FairValueGap] = []
        seen_indices: set[tuple[int, int, int]] = set()

        for candidate in candidates:
            key = (
                candidate.candle_a_index,
                candidate.candle_b_index,
                candidate.candle_c_index,
            )
            if key in seen_indices:
                continue

            gap = self._candidate_to_gap(
                candidate,
                candles,
                structure,
                liquidity_state,
                order_block_state,
                higher_timeframe_gaps=higher_timeframe_gaps,
                timeframe=timeframe,
            )
            if gap is not None:
                seen_indices.add(key)
                gaps.append(gap)

        return gaps

    def _candidate_to_gap(
        self,
        candidate: FVGFormationCandidate,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
        liquidity_state: LiquidityState | None,
        order_block_state: OrderBlockState | None,
        *,
        higher_timeframe_gaps: list[FairValueGap] | None,
        timeframe: str,
    ) -> FairValueGap | None:
        gap_size = candidate.high - candidate.low
        gap_size_pips = gap_size / Decimal(str(self._config.pip_size))
        validity_reason = "Valid three-candle imbalance"

        if gap_size_pips < Decimal(str(self._config.min_gap_size_pips)):
            return None

        if self._config.require_impulse_candle and not self._passes_impulse(
            candidate,
            candles,
        ):
            return None

        ce_price = (candidate.high + candidate.low) / Decimal("2")
        gap_id = self._build_gap_id(candidate)

        premium_zone, range_high, range_low, premium_evidence = (
            self._mitigation.classify_premium_discount(
                FairValueGap(
                    gap_id=gap_id,
                    direction=candidate.direction,
                    status=FairValueGapStatus.OPEN,
                    high=candidate.high,
                    low=candidate.low,
                    ce_price=ce_price,
                    gap_size=gap_size,
                    gap_size_pips=gap_size_pips,
                    origin_bar_index=candidate.origin_bar_index,
                    origin_time_utc=candidate.origin_time_utc,
                    candle_a_index=candidate.candle_a_index,
                    candle_b_index=candidate.candle_b_index,
                    candle_c_index=candidate.candle_c_index,
                    quality=FairValueGapQuality.LOW,
                    strength=Decimal("0"),
                ),
                structure,
            )
        )

        provisional = FairValueGap(
            gap_id=gap_id,
            direction=candidate.direction,
            status=FairValueGapStatus.OPEN,
            high=candidate.high,
            low=candidate.low,
            ce_price=ce_price,
            gap_size=gap_size,
            gap_size_pips=gap_size_pips,
            is_valid=True,
            validity_reason=validity_reason,
            origin_bar_index=candidate.origin_bar_index,
            origin_time_utc=candidate.origin_time_utc,
            candle_a_index=candidate.candle_a_index,
            candle_b_index=candidate.candle_b_index,
            candle_c_index=candidate.candle_c_index,
            quality=FairValueGapQuality.LOW,
            strength=Decimal("0"),
            premium_discount=premium_zone,
            dealing_range_high=range_high,
            dealing_range_low=range_low,
            evidence=list(premium_evidence),
        )

        (
            strength,
            quality,
            structure_alignment,
            liquidity_confluence,
            order_block_confluence,
            mtf_alignment,
            quality_evidence,
        ) = self._quality.score(
            provisional,
            candles=candles,
            structure=structure,
            liquidity_state=liquidity_state,
            order_block_state=order_block_state,
            higher_timeframe_gaps=higher_timeframe_gaps,
            timeframe=timeframe,
            premium_discount=premium_zone,
        )

        if not self._quality.passes_minimum(strength):
            return None

        if self._config.require_structure_alignment and not structure_alignment:
            if structure is None or not self._quality.has_counter_trend_choch(
                provisional,
                structure,
            ):
                return None

        evidence = premium_evidence + quality_evidence
        return provisional.model_copy(
            update={
                "quality": quality,
                "strength": strength,
                "structure_alignment": structure_alignment,
                "liquidity_confluence": liquidity_confluence,
                "order_block_confluence": order_block_confluence,
                "mtf_alignment": mtf_alignment,
                "evidence": evidence,
            },
        )

    def _passes_impulse(
        self,
        candidate: FVGFormationCandidate,
        candles: list[NormalizedCandle],
    ) -> bool:
        candle = candles[candidate.candle_b_index]
        candle_range = candle.high - candle.low
        if candle_range <= 0:
            return False
        body = abs(candle.close - candle.open)
        ratio = body / candle_range
        return ratio >= self._config.min_impulse_body_ratio

    def _merge_gaps(
        self,
        prior_gaps: list[FairValueGap],
        detected: list[FairValueGap],
    ) -> list[FairValueGap]:
        merged: dict[str, FairValueGap] = {gap.gap_id: gap for gap in prior_gaps}

        for gap in detected:
            existing = merged.get(gap.gap_id)
            if existing is None:
                merged[gap.gap_id] = gap
                continue

            merged[gap.gap_id] = existing.model_copy(
                update={
                    "quality": gap.quality,
                    "strength": gap.strength,
                    "structure_alignment": gap.structure_alignment,
                    "liquidity_confluence": gap.liquidity_confluence,
                    "order_block_confluence": gap.order_block_confluence,
                    "premium_discount": gap.premium_discount,
                    "dealing_range_high": gap.dealing_range_high,
                    "dealing_range_low": gap.dealing_range_low,
                    "mtf_alignment": gap.mtf_alignment,
                    "evidence": gap.evidence,
                },
            )

        return sorted(
            merged.values(),
            key=lambda gap: (gap.origin_time_utc, gap.gap_id),
        )

    def _build_gap_id(self, candidate: FVGFormationCandidate) -> str:
        prefix = "bull" if candidate.direction is FairValueGapDirection.BULLISH else "bear"
        price_token = str(candidate.high).replace(".", "_")
        time_token = int(candidate.origin_time_utc.timestamp())
        return f"fvg-{prefix}-{price_token}-{candidate.origin_bar_index}-{time_token}"

    def _build_timeline_events(
        self,
        gaps: list[FairValueGap],
        lifecycle_updates: list[LifecycleUpdate],
        candles: list[NormalizedCandle],
        timeframe: str,
        prior_gaps: list[FairValueGap],
    ) -> list[FairValueGapEvent]:
        prior_by_id = {gap.gap_id: gap for gap in prior_gaps}
        update_by_id = {update.gap.gap_id: update for update in lifecycle_updates}
        gap_by_id = {gap.gap_id: gap for gap in gaps}
        events: list[FairValueGapEvent] = []

        def bar_time(index: int | None) -> datetime:
            if index is None or index < 0 or index >= len(candles):
                return candles[-1].close_time_utc if candles else datetime.now(tz=UTC)
            return candles[index].close_time_utc

        for gap in gaps:
            prior = prior_by_id.get(gap.gap_id)
            lifecycle = update_by_id.get(gap.gap_id)

            if prior is None:
                events.append(
                    FairValueGapEvent(
                        kind=(
                            FairValueGapEventKind.BULLISH_FAIR_VALUE_GAP_DETECTED
                            if gap.direction is FairValueGapDirection.BULLISH
                            else FairValueGapEventKind.BEARISH_FAIR_VALUE_GAP_DETECTED
                        ),
                        timestamp_utc=gap.origin_time_utc,
                        timeframe=timeframe,
                        description=f"{gap.direction.value} fair value gap detected",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.ce_price,
                    ),
                )
                events.append(
                    FairValueGapEvent(
                        kind=FairValueGapEventKind.FAIR_VALUE_GAP_DETECTED,
                        timestamp_utc=gap.origin_time_utc,
                        timeframe=timeframe,
                        description="Fair value gap detected",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.ce_price,
                    ),
                )

            if gap.status is FairValueGapStatus.OPEN and (
                prior is None or prior.status is not FairValueGapStatus.OPEN
            ):
                events.append(
                    FairValueGapEvent(
                        kind=FairValueGapEventKind.OPEN_FAIR_VALUE_GAP,
                        timestamp_utc=gap.origin_time_utc,
                        timeframe=timeframe,
                        description="Fair value gap confirmed open",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.ce_price,
                    ),
                )

            if (
                gap.status is FairValueGapStatus.PARTIAL
                and prior is not None
                and prior.status is FairValueGapStatus.OPEN
            ):
                events.append(
                    FairValueGapEvent(
                        kind=FairValueGapEventKind.PARTIAL_FILL_FAIR_VALUE_GAP,
                        timestamp_utc=bar_time(gap.fill_bar_index),
                        timeframe=timeframe,
                        description="Fair value gap partially filled",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.ce_price,
                        fill_percent=gap.fill_percent,
                    ),
                )

            if lifecycle is not None and lifecycle.ce_encroached:
                prior_ce = prior is not None and gap.gap_id in self._ce_encroached_ids
                if not prior_ce:
                    self._ce_encroached_ids.add(gap.gap_id)
                    events.append(
                        FairValueGapEvent(
                            kind=FairValueGapEventKind.CE_ENCROACHED,
                            timestamp_utc=bar_time(lifecycle.ce_encroachment_bar_index),
                            timeframe=timeframe,
                            description="Consequent encroachment level touched",
                            gap_id=gap.gap_id,
                            direction=gap.direction,
                            status=gap.status,
                            price=lifecycle.ce_encroachment_price,
                            fill_percent=gap.fill_percent,
                        ),
                    )

            if (
                gap.status is FairValueGapStatus.FILLED
                and prior is not None
                and prior.status is not FairValueGapStatus.FILLED
            ):
                events.append(
                    FairValueGapEvent(
                        kind=FairValueGapEventKind.FILLED_FAIR_VALUE_GAP,
                        timestamp_utc=bar_time(gap.fill_bar_index),
                        timeframe=timeframe,
                        description="Fair value gap fully filled",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.low if gap.direction is FairValueGapDirection.BULLISH else gap.high,
                        fill_percent=gap.fill_percent,
                    ),
                )

            if (
                gap.status is FairValueGapStatus.MITIGATED
                and prior is not None
                and prior.status is not FairValueGapStatus.MITIGATED
            ):
                events.append(
                    FairValueGapEvent(
                        kind=FairValueGapEventKind.MITIGATED_FAIR_VALUE_GAP,
                        timestamp_utc=bar_time(gap.mitigation_bar_index),
                        timeframe=timeframe,
                        description="Fair value gap mitigated",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.ce_price,
                        fill_percent=gap.fill_percent,
                    ),
                )

            if (
                gap.status is FairValueGapStatus.INVALIDATED
                and prior is not None
                and prior.status is not FairValueGapStatus.INVALIDATED
            ):
                events.append(
                    FairValueGapEvent(
                        kind=FairValueGapEventKind.INVALIDATED_FAIR_VALUE_GAP,
                        timestamp_utc=bar_time(gap.invalidation_bar_index),
                        timeframe=timeframe,
                        description="Fair value gap invalidated",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.low if gap.direction is FairValueGapDirection.BULLISH else gap.high,
                    ),
                )

            if (
                gap.status is FairValueGapStatus.EXPIRED
                and prior is not None
                and prior.status is not FairValueGapStatus.EXPIRED
            ):
                events.append(
                    FairValueGapEvent(
                        kind=FairValueGapEventKind.EXPIRED_FAIR_VALUE_GAP,
                        timestamp_utc=bar_time(gap.expiration_bar_index),
                        timeframe=timeframe,
                        description="Fair value gap expired",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.ce_price,
                    ),
                )

            if gap.nested_parent_gap_id and (
                prior is None or prior.nested_parent_gap_id != gap.nested_parent_gap_id
            ):
                parent = gap_by_id.get(gap.nested_parent_gap_id)
                if parent is not None:
                    events.append(
                        FairValueGapEvent(
                            kind=FairValueGapEventKind.NESTED_FAIR_VALUE_GAP,
                            timestamp_utc=gap.origin_time_utc,
                            timeframe=timeframe,
                            description="Nested fair value gap resolved",
                            gap_id=gap.gap_id,
                            direction=gap.direction,
                            status=gap.status,
                            price=gap.ce_price,
                        ),
                    )

            if gap.mtf_alignment and (
                prior is None or prior.mtf_alignment != gap.mtf_alignment
            ):
                events.append(
                    FairValueGapEvent(
                        kind=FairValueGapEventKind.MTF_ALIGNED_FAIR_VALUE_GAP,
                        timestamp_utc=gap.origin_time_utc,
                        timeframe=timeframe,
                        description="Multi-timeframe fair value gap alignment confirmed",
                        gap_id=gap.gap_id,
                        direction=gap.direction,
                        status=gap.status,
                        price=gap.ce_price,
                    ),
                )

        return events

    @staticmethod
    def _determine_bias(
        open_gaps: list[FairValueGap],
        partial_gaps: list[FairValueGap],
    ) -> tuple[FairValueGapBias, Decimal, list[str]]:
        evidence: list[str] = []
        active = open_gaps + partial_gaps

        if not active:
            evidence.append("No active fair value gaps")
            return FairValueGapBias.NEUTRAL, Decimal("0"), evidence

        bullish_active = [
            gap
            for gap in active
            if gap.direction is FairValueGapDirection.BULLISH
            and gap.premium_discount is PremiumDiscountZone.DISCOUNT
        ]
        bearish_active = [
            gap
            for gap in active
            if gap.direction is FairValueGapDirection.BEARISH
            and gap.premium_discount is PremiumDiscountZone.PREMIUM
        ]

        if len(bullish_active) > len(bearish_active):
            evidence.append(
                f"Dominant bullish gaps in discount ({len(bullish_active)} vs {len(bearish_active)})",
            )
            confidence = Decimal(str(len(bullish_active) / max(len(active), 1)))
            avg_strength = sum(gap.strength for gap in bullish_active) / Decimal(
                str(len(bullish_active)),
            )
            return FairValueGapBias.BULLISH, min(Decimal("1"), (confidence + avg_strength) / 2), evidence

        if len(bearish_active) > len(bullish_active):
            evidence.append(
                f"Dominant bearish gaps in premium ({len(bearish_active)} vs {len(bullish_active)})",
            )
            confidence = Decimal(str(len(bearish_active) / max(len(active), 1)))
            avg_strength = sum(gap.strength for gap in bearish_active) / Decimal(
                str(len(bearish_active)),
            )
            return FairValueGapBias.BEARISH, min(Decimal("1"), (confidence + avg_strength) / 2), evidence

        if not bullish_active and not bearish_active:
            evidence.append("Active gaps lack premium/discount directional edge")
            return FairValueGapBias.UNDETERMINED, Decimal("0.3"), evidence

        evidence.append("Balanced fair value gap context")
        return FairValueGapBias.NEUTRAL, Decimal("0.5"), evidence
