"""Breaker block detection orchestrator."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_breaker.config import BreakerBlockConfig
from backend.engines.market_breaker.lifecycle import LifecycleManager
from backend.engines.market_breaker.origin import OriginDetector
from backend.engines.market_breaker.quality import QualityScorer
from backend.engines.market_breaker.schemas import (
    BreakerBlock,
    BreakerBlockAnalysis,
    BreakerBlockBias,
    BreakerBlockDirection,
    BreakerBlockEvent,
    BreakerBlockEventKind,
    BreakerBlockQuality,
    BreakerBlockState,
    BreakerBlockStatus,
    BreakerCandidate,
    BreakerSourceType,
)
from backend.engines.market_fvg.schemas import FairValueGap, FairValueGapState, PremiumDiscountZone
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_structure import MarketStructure


class BreakerBlockDetector:
    """Orchestrate formation, confirmation, lifecycle, and quality detection."""

    def __init__(
        self,
        config: BreakerBlockConfig,
        origin_detector: OriginDetector | None = None,
        lifecycle_manager: LifecycleManager | None = None,
        quality_scorer: QualityScorer | None = None,
    ) -> None:
        self._config = config
        self._origin = origin_detector or OriginDetector(config)
        self._lifecycle = lifecycle_manager or LifecycleManager(config)
        self._quality = quality_scorer or QualityScorer(config)

    def detect(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        invalidated_order_blocks: list[OrderBlock] | None = None,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        prior_state: BreakerBlockState | None = None,
        invalidated_fvgs: list[FairValueGap] | None = None,
    ) -> BreakerBlockAnalysis:
        """Run full breaker block analysis pipeline."""
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

        blocks = invalidated_order_blocks or []
        fvgs = invalidated_fvgs or []

        bullish = self.detect_bullish_breakers(
            scan_candles,
            blocks,
            structure,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
            invalidated_fvgs=fvgs,
        )
        bearish = self.detect_bearish_breakers(
            scan_candles,
            blocks,
            structure,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
            invalidated_fvgs=fvgs,
        )
        detected = bullish + bearish

        prior_breakers = prior_state.active_breakers if prior_state else []
        merged = self._merge_breakers(prior_breakers, detected)
        classified = self.classify_lifecycle(merged, scan_candles)

        filtered = self._filter_breakers(
            classified,
            scan_candles,
            structure,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
        )

        candidate_breakers = [
            b for b in filtered if b.status is BreakerBlockStatus.CANDIDATE
        ]
        confirmed_breakers = [
            b for b in filtered if b.status is BreakerBlockStatus.CONFIRMED
        ]
        mitigated_breakers = [
            b for b in filtered if b.status is BreakerBlockStatus.MITIGATED
        ]
        invalidated_breakers = [
            b for b in filtered if b.status is BreakerBlockStatus.INVALIDATED
        ]
        expired_breakers = [
            b for b in filtered if b.status is BreakerBlockStatus.EXPIRED
        ]
        bullish_breakers = [
            b for b in filtered if b.direction is BreakerBlockDirection.BULLISH
        ]
        bearish_breakers = [
            b for b in filtered if b.direction is BreakerBlockDirection.BEARISH
        ]

        active_breakers = [
            b
            for b in filtered
            if b.status in {BreakerBlockStatus.CANDIDATE, BreakerBlockStatus.CONFIRMED}
        ]

        bias, confidence, evidence = self._determine_bias(
            confirmed_breakers,
            structure,
        )
        events = self._build_timeline_events(
            filtered,
            scan_candles,
            timeframe,
            prior_breakers,
        )

        state = BreakerBlockState(
            active_breakers=active_breakers,
            last_analysis_utc=analysis_time,
            bar_count=bar_count,
        )

        return BreakerBlockAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_utc=analysis_time,
            breaker_blocks=filtered,
            candidate_breakers=candidate_breakers,
            confirmed_breakers=confirmed_breakers,
            mitigated_breakers=mitigated_breakers,
            invalidated_breakers=invalidated_breakers,
            expired_breakers=expired_breakers,
            bullish_breakers=bullish_breakers,
            bearish_breakers=bearish_breakers,
            bias=bias,
            confidence=confidence,
            evidence=evidence,
            state=state,
            events=sorted(events, key=lambda event: event.timestamp_utc),
        )

    def detect_bullish_breakers(
        self,
        candles: list[NormalizedCandle],
        invalidated_order_blocks: list[OrderBlock],
        structure: MarketStructure | None = None,
        *,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        invalidated_fvgs: list[FairValueGap] | None = None,
    ) -> list[BreakerBlock]:
        """Detect bullish breakers only."""
        return self._detect_direction(
            candles,
            BreakerBlockDirection.BULLISH,
            invalidated_order_blocks,
            structure,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
            invalidated_fvgs=invalidated_fvgs,
        )

    def detect_bearish_breakers(
        self,
        candles: list[NormalizedCandle],
        invalidated_order_blocks: list[OrderBlock],
        structure: MarketStructure | None = None,
        *,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        invalidated_fvgs: list[FairValueGap] | None = None,
    ) -> list[BreakerBlock]:
        """Detect bearish breakers only."""
        return self._detect_direction(
            candles,
            BreakerBlockDirection.BEARISH,
            invalidated_order_blocks,
            structure,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
            invalidated_fvgs=invalidated_fvgs,
        )

    def classify_lifecycle(
        self,
        breakers: list[BreakerBlock],
        candles: list[NormalizedCandle],
    ) -> list[BreakerBlock]:
        """Update candidate, confirmed, mitigated, invalidated, and expired status."""
        return self._lifecycle.classify_breakers(breakers, candles)

    def _detect_direction(
        self,
        candles: list[NormalizedCandle],
        direction: BreakerBlockDirection,
        invalidated_order_blocks: list[OrderBlock],
        structure: MarketStructure | None,
        *,
        liquidity_state: LiquidityState | None,
        fair_value_gap_state: FairValueGapState | None,
        invalidated_fvgs: list[FairValueGap] | None,
    ) -> list[BreakerBlock]:
        ob_candidates = self._origin.derive_from_order_blocks(
            invalidated_order_blocks,
            candles,
        )
        fvg_candidates = self._origin.derive_from_fvgs(
            invalidated_fvgs or [],
            candles,
        )
        candidates = [
            candidate
            for candidate in ob_candidates + fvg_candidates
            if candidate.direction is direction
        ]

        breakers: list[BreakerBlock] = []
        for candidate in candidates:
            breaker = self._candidate_to_breaker(
                candidate,
                candles,
                structure,
                liquidity_state,
                fair_value_gap_state,
            )
            if breaker is not None:
                breakers.append(breaker)
        return breakers

    def _candidate_to_breaker(
        self,
        candidate: BreakerCandidate,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
        liquidity_state: LiquidityState | None,
        fair_value_gap_state: FairValueGapState | None,
    ) -> BreakerBlock | None:
        breaker_id = self._build_breaker_id(candidate)
        confirmation_reason = self._lifecycle.compute_confirmation_reason(
            BreakerBlock(
                breaker_id=breaker_id,
                direction=candidate.direction,
                status=BreakerBlockStatus.CANDIDATE,
                high=candidate.high,
                low=candidate.low,
                source_type=candidate.source_type,
                source_id=candidate.source_id,
                source_direction=candidate.source_direction,
                invalidation_bar_index=candidate.invalidation_bar_index,
                invalidation_time_utc=candidate.invalidation_time_utc,
                formation_bar_index=candidate.formation_bar_index,
                formation_time_utc=candidate.formation_time_utc,
                quality=BreakerBlockQuality.LOW,
                strength=Decimal("0"),
                is_confirmed=False,
                confirmation_reason="Awaiting retest",
                structure_alignment=False,
                liquidity_confluence=False,
                fvg_confluence=False,
                evidence=[f"Source quality: {candidate.source_quality}"],
            ),
            candles,
        )

        provisional = BreakerBlock(
            breaker_id=breaker_id,
            direction=candidate.direction,
            status=BreakerBlockStatus.CANDIDATE,
            high=candidate.high,
            low=candidate.low,
            source_type=candidate.source_type,
            source_id=candidate.source_id,
            source_direction=candidate.source_direction,
            invalidation_bar_index=candidate.invalidation_bar_index,
            invalidation_time_utc=candidate.invalidation_time_utc,
            formation_bar_index=candidate.formation_bar_index,
            formation_time_utc=candidate.formation_time_utc,
            quality=BreakerBlockQuality.LOW,
            strength=Decimal("0"),
            is_confirmed=False,
            confirmation_reason=confirmation_reason,
            structure_alignment=False,
            liquidity_confluence=False,
            fvg_confluence=False,
            evidence=[
                f"Source quality: {candidate.source_quality}",
                f"Derived from {candidate.source_type.value} {candidate.source_id}",
            ],
        )

        displacement = self._quality.compute_invalidation_displacement(provisional, candles)
        (
            strength,
            quality,
            structure_alignment,
            liquidity_confluence,
            fvg_confluence,
            liquidity_ids,
            fvg_ids,
            quality_evidence,
            premium_zone,
            range_high,
            range_low,
        ) = self._quality.score(
            provisional,
            candles_count=len(candles),
            structure=structure,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
            invalidation_displacement=displacement,
        )

        if not self._quality.passes_minimum(strength):
            return None

        if self._config.require_structure_alignment and not structure_alignment:
            if structure is None or not self._quality.has_counter_trend_choch(
                provisional,
                structure,
            ):
                return None

        evidence = provisional.evidence + quality_evidence
        return provisional.model_copy(
            update={
                "quality": quality,
                "strength": strength,
                "structure_alignment": structure_alignment,
                "liquidity_confluence": liquidity_confluence,
                "fvg_confluence": fvg_confluence,
                "liquidity_confluence_ids": liquidity_ids,
                "fvg_confluence_ids": fvg_ids,
                "premium_discount": premium_zone,
                "dealing_range_high": range_high,
                "dealing_range_low": range_low,
                "evidence": evidence,
            },
        )

    def _filter_breakers(
        self,
        breakers: list[BreakerBlock],
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
        *,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
    ) -> list[BreakerBlock]:
        """Re-score after lifecycle and filter by minimum quality."""
        filtered: list[BreakerBlock] = []
        for breaker in breakers:
            displacement = self._quality.compute_invalidation_displacement(breaker, candles)
            (
                strength,
                quality,
                structure_alignment,
                liquidity_confluence,
                fvg_confluence,
                liquidity_ids,
                fvg_ids,
                quality_evidence,
                premium_zone,
                range_high,
                range_low,
            ) = self._quality.score(
                breaker,
                candles_count=len(candles),
                structure=structure,
                liquidity_state=liquidity_state,
                fair_value_gap_state=fair_value_gap_state,
                invalidation_displacement=displacement,
            )

            if not self._quality.passes_minimum(strength):
                continue

            if self._config.require_structure_alignment and not structure_alignment:
                if structure is None or not self._quality.has_counter_trend_choch(
                    breaker,
                    structure,
                ):
                    continue

            confirmation_reason = self._lifecycle.compute_confirmation_reason(
                breaker,
                candles,
            )
            is_confirmed = breaker.status in {
                BreakerBlockStatus.CONFIRMED,
                BreakerBlockStatus.MITIGATED,
            } or self._lifecycle.validate_confirmation(breaker, candles)

            filtered.append(
                breaker.model_copy(
                    update={
                        "quality": quality,
                        "strength": strength,
                        "is_confirmed": is_confirmed,
                        "confirmation_reason": confirmation_reason,
                        "structure_alignment": structure_alignment,
                        "liquidity_confluence": liquidity_confluence,
                        "fvg_confluence": fvg_confluence,
                        "liquidity_confluence_ids": liquidity_ids,
                        "fvg_confluence_ids": fvg_ids,
                        "premium_discount": premium_zone,
                        "dealing_range_high": range_high,
                        "dealing_range_low": range_low,
                        "evidence": breaker.evidence + quality_evidence,
                    },
                ),
            )
        return filtered

    def _merge_breakers(
        self,
        prior_breakers: list[BreakerBlock],
        detected: list[BreakerBlock],
    ) -> list[BreakerBlock]:
        merged: dict[str, BreakerBlock] = {
            breaker.breaker_id: breaker for breaker in prior_breakers
        }
        seen_sources: set[str] = set()

        for breaker in prior_breakers:
            seen_sources.add(breaker.source_id)

        for breaker in detected:
            if self._config.deduplicate_by_source and breaker.source_id in seen_sources:
                continue

            existing = merged.get(breaker.breaker_id)
            if existing is None:
                merged[breaker.breaker_id] = breaker
                seen_sources.add(breaker.source_id)
                continue

            merged[breaker.breaker_id] = existing.model_copy(
                update={
                    "quality": breaker.quality,
                    "strength": breaker.strength,
                    "structure_alignment": breaker.structure_alignment,
                    "liquidity_confluence": breaker.liquidity_confluence,
                    "fvg_confluence": breaker.fvg_confluence,
                    "liquidity_confluence_ids": breaker.liquidity_confluence_ids,
                    "fvg_confluence_ids": breaker.fvg_confluence_ids,
                    "premium_discount": breaker.premium_discount,
                    "dealing_range_high": breaker.dealing_range_high,
                    "dealing_range_low": breaker.dealing_range_low,
                    "evidence": breaker.evidence,
                },
            )
            seen_sources.add(breaker.source_id)

        return sorted(
            merged.values(),
            key=lambda breaker: (breaker.formation_time_utc, breaker.breaker_id),
        )

    def _build_breaker_id(self, candidate: BreakerCandidate) -> str:
        prefix = "bull" if candidate.direction is BreakerBlockDirection.BULLISH else "bear"
        price_token = str(candidate.high).replace(".", "_")
        time_token = int(candidate.invalidation_time_utc.timestamp())
        return (
            f"brk-{prefix}-{price_token}-"
            f"{candidate.invalidation_bar_index}-{time_token}"
        )

    def _build_timeline_events(
        self,
        breakers: list[BreakerBlock],
        candles: list[NormalizedCandle],
        timeframe: str,
        prior_breakers: list[BreakerBlock],
    ) -> list[BreakerBlockEvent]:
        prior_by_id = {breaker.breaker_id: breaker for breaker in prior_breakers}
        events: list[BreakerBlockEvent] = []

        def bar_time(index: int | None) -> datetime:
            if index is None or index < 0 or index >= len(candles):
                return candles[-1].close_time_utc if candles else datetime.now(tz=UTC)
            return candles[index].close_time_utc

        for breaker in breakers:
            prior = prior_by_id.get(breaker.breaker_id)

            if prior is None:
                events.append(
                    BreakerBlockEvent(
                        kind=(
                            BreakerBlockEventKind.BULLISH_BREAKER_BLOCK_DETECTED
                            if breaker.direction is BreakerBlockDirection.BULLISH
                            else BreakerBlockEventKind.BEARISH_BREAKER_BLOCK_DETECTED
                        ),
                        timestamp_utc=breaker.formation_time_utc,
                        timeframe=timeframe,
                        description=f"{breaker.direction.value} breaker block detected",
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        status=breaker.status,
                        price=breaker.high,
                        source_id=breaker.source_id,
                    ),
                )
                events.append(
                    BreakerBlockEvent(
                        kind=BreakerBlockEventKind.BREAKER_BLOCK_DETECTED,
                        timestamp_utc=breaker.formation_time_utc,
                        timeframe=timeframe,
                        description="Breaker block detected",
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        status=breaker.status,
                        price=breaker.high,
                        source_id=breaker.source_id,
                    ),
                )
                events.append(
                    BreakerBlockEvent(
                        kind=BreakerBlockEventKind.CANDIDATE_BREAKER_BLOCK,
                        timestamp_utc=breaker.formation_time_utc,
                        timeframe=timeframe,
                        description="Breaker registered as candidate",
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        status=BreakerBlockStatus.CANDIDATE,
                        price=breaker.high,
                        source_id=breaker.source_id,
                    ),
                )

            if breaker.liquidity_confluence and (
                prior is None or not prior.liquidity_confluence
            ):
                events.append(
                    BreakerBlockEvent(
                        kind=BreakerBlockEventKind.LIQUIDITY_CONFLUENCE_BREAKER,
                        timestamp_utc=breaker.formation_time_utc,
                        timeframe=timeframe,
                        description="Liquidity confluence detected",
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        source_id=breaker.source_id,
                    ),
                )

            if breaker.fvg_confluence and (prior is None or not prior.fvg_confluence):
                events.append(
                    BreakerBlockEvent(
                        kind=BreakerBlockEventKind.FVG_CONFLUENCE_BREAKER,
                        timestamp_utc=breaker.formation_time_utc,
                        timeframe=timeframe,
                        description="FVG confluence detected",
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        source_id=breaker.source_id,
                    ),
                )

            if breaker.status is BreakerBlockStatus.CONFIRMED and (
                prior is None or prior.status is not BreakerBlockStatus.CONFIRMED
            ):
                events.append(
                    BreakerBlockEvent(
                        kind=BreakerBlockEventKind.CONFIRMED_BREAKER_BLOCK,
                        timestamp_utc=bar_time(breaker.confirmation_bar_index),
                        timeframe=timeframe,
                        description=breaker.confirmation_reason,
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        status=breaker.status,
                        price=breaker.high,
                        source_id=breaker.source_id,
                    ),
                )

            if breaker.status is BreakerBlockStatus.MITIGATED and (
                prior is not None and prior.status is not BreakerBlockStatus.MITIGATED
            ):
                events.append(
                    BreakerBlockEvent(
                        kind=BreakerBlockEventKind.MITIGATED_BREAKER_BLOCK,
                        timestamp_utc=bar_time(breaker.mitigation_bar_index),
                        timeframe=timeframe,
                        description="Breaker block mitigated",
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        status=breaker.status,
                        price=breaker.low,
                        source_id=breaker.source_id,
                    ),
                )

            if breaker.status is BreakerBlockStatus.INVALIDATED and (
                prior is not None and prior.status is not BreakerBlockStatus.INVALIDATED
            ):
                events.append(
                    BreakerBlockEvent(
                        kind=BreakerBlockEventKind.INVALIDATED_BREAKER_BLOCK,
                        timestamp_utc=bar_time(breaker.invalidation_breaker_bar_index),
                        timeframe=timeframe,
                        description="Breaker block invalidated",
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        status=breaker.status,
                        price=breaker.low,
                        source_id=breaker.source_id,
                    ),
                )

            if breaker.status is BreakerBlockStatus.EXPIRED and (
                prior is not None and prior.status is not BreakerBlockStatus.EXPIRED
            ):
                events.append(
                    BreakerBlockEvent(
                        kind=BreakerBlockEventKind.EXPIRED_BREAKER_BLOCK,
                        timestamp_utc=bar_time(breaker.expiration_bar_index),
                        timeframe=timeframe,
                        description="Breaker block expired",
                        breaker_id=breaker.breaker_id,
                        direction=breaker.direction,
                        status=breaker.status,
                        price=breaker.high,
                        source_id=breaker.source_id,
                    ),
                )

        return events

    @staticmethod
    def _determine_bias(
        confirmed_breakers: list[BreakerBlock],
        structure: MarketStructure | None,
    ) -> tuple[BreakerBlockBias, Decimal, list[str]]:
        evidence: list[str] = []

        if not confirmed_breakers:
            evidence.append("No confirmed breaker blocks")
            return BreakerBlockBias.UNDETERMINED, Decimal("0"), evidence

        bullish = [
            b
            for b in confirmed_breakers
            if b.direction is BreakerBlockDirection.BULLISH
        ]
        bearish = [
            b
            for b in confirmed_breakers
            if b.direction is BreakerBlockDirection.BEARISH
        ]

        bullish_in_discount = sum(
            1
            for b in bullish
            if b.premium_discount is PremiumDiscountZone.DISCOUNT
        )
        bearish_in_premium = sum(
            1
            for b in bearish
            if b.premium_discount is PremiumDiscountZone.PREMIUM
        )

        if structure is not None:
            evidence.append(f"Structure trend: {structure.current_trend.value}")

        if len(bullish) > len(bearish):
            evidence.append(
                f"Confirmed bullish breakers dominate ({len(bullish)} vs {len(bearish)})",
            )
            if bullish_in_discount:
                evidence.append(
                    f"{bullish_in_discount} confirmed bullish breakers in discount",
                )
            confidence = Decimal(str(len(bullish) / max(len(confirmed_breakers), 1)))
            return BreakerBlockBias.BULLISH, min(Decimal("1"), confidence), evidence

        if len(bearish) > len(bullish):
            evidence.append(
                f"Confirmed bearish breakers dominate ({len(bearish)} vs {len(bullish)})",
            )
            if bearish_in_premium:
                evidence.append(
                    f"{bearish_in_premium} confirmed bearish breakers in premium",
                )
            confidence = Decimal(str(len(bearish) / max(len(confirmed_breakers), 1)))
            return BreakerBlockBias.BEARISH, min(Decimal("1"), confidence), evidence

        evidence.append("Balanced confirmed bullish and bearish breakers")
        return BreakerBlockBias.NEUTRAL, Decimal("0.5"), evidence
