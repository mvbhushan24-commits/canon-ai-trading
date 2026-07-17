"""Mitigation block detection orchestrator."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_breaker.schemas import BreakerBlock
from backend.engines.market_data import NormalizedCandle
from backend.engines.market_fvg.schemas import FairValueGapState
from backend.engines.market_liquidity import LiquidityState
from backend.engines.market_mitigation.config import MitigationBlockConfig
from backend.engines.market_mitigation.lifecycle import LifecycleManager
from backend.engines.market_mitigation.origin import OriginDetector
from backend.engines.market_mitigation.quality import QualityScorer
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockAnalysis,
    MitigationBlockBias,
    MitigationBlockDirection,
    MitigationBlockEvent,
    MitigationBlockEventKind,
    MitigationBlockQuality,
    MitigationBlockState,
    MitigationBlockStatus,
    MitigationCandidate,
    MitigationSourceType,
    StructureScope,
)
from backend.engines.market_fvg.schemas import PremiumDiscountZone
from backend.engines.market_order_block import OrderBlock
from backend.engines.market_structure import MarketStructure


class MitigationBlockDetector:
    """Orchestrate formation, lifecycle, confluence, and quality detection."""

    def __init__(
        self,
        config: MitigationBlockConfig,
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
        order_blocks: list[OrderBlock] | None = None,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        prior_state: MitigationBlockState | None = None,
        htf_mitigation_blocks: list[MitigationBlock] | None = None,
        ltf_mitigation_blocks: list[MitigationBlock] | None = None,
    ) -> MitigationBlockAnalysis:
        """Run full mitigation block analysis pipeline."""
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

        active_gaps = (
            fair_value_gap_state.active_gaps if fair_value_gap_state else None
        )

        bullish = self.detect_bullish_blocks(scan_candles, structure)
        bearish = self.detect_bearish_blocks(scan_candles, structure)
        detected = bullish + bearish

        confluence_candidates = self._origin.derive_from_confluence(
            scan_candles,
            order_blocks=order_blocks,
            fair_value_gaps=active_gaps,
            breaker_blocks=breaker_blocks,
            mitigation_blocks=htf_mitigation_blocks,
        )
        for candidate in confluence_candidates:
            block = self._candidate_to_block(
                candidate,
                scan_candles,
                structure,
                order_blocks=order_blocks,
                liquidity_state=liquidity_state,
                fair_value_gap_state=fair_value_gap_state,
                breaker_blocks=breaker_blocks,
                htf_mitigation_blocks=htf_mitigation_blocks,
                ltf_mitigation_blocks=ltf_mitigation_blocks,
            )
            if block is not None and block.block_id not in {b.block_id for b in detected}:
                detected.append(block)

        prior_blocks = prior_state.active_blocks if prior_state else []
        merged = self._merge_blocks(prior_blocks, detected)
        classified = self.classify_lifecycle(merged, scan_candles, structure=structure)

        filtered = self._filter_blocks(
            classified,
            scan_candles,
            structure,
            order_blocks=order_blocks,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            htf_mitigation_blocks=htf_mitigation_blocks,
            ltf_mitigation_blocks=ltf_mitigation_blocks,
        )

        fresh_blocks = [b for b in filtered if b.status is MitigationBlockStatus.FRESH]
        partial_blocks = [b for b in filtered if b.status is MitigationBlockStatus.PARTIAL]
        confirmed_blocks = [
            b for b in filtered if b.status is MitigationBlockStatus.CONFIRMED
        ]
        used_blocks = [b for b in filtered if b.status is MitigationBlockStatus.USED]
        invalidated_blocks = [
            b for b in filtered if b.status is MitigationBlockStatus.INVALIDATED
        ]
        expired_blocks = [b for b in filtered if b.status is MitigationBlockStatus.EXPIRED]
        bullish_blocks = [
            b for b in filtered if b.direction is MitigationBlockDirection.BULLISH
        ]
        bearish_blocks = [
            b for b in filtered if b.direction is MitigationBlockDirection.BEARISH
        ]
        nested_blocks = [b for b in filtered if b.is_nested]
        internal_blocks = [
            b for b in filtered if b.structure_scope is StructureScope.INTERNAL
        ]
        external_blocks = [
            b for b in filtered if b.structure_scope is StructureScope.EXTERNAL
        ]
        htf_aligned_blocks = [b for b in filtered if b.htf_aligned]

        active_blocks = [
            b
            for b in filtered
            if b.status
            in {
                MitigationBlockStatus.FRESH,
                MitigationBlockStatus.PARTIAL,
                MitigationBlockStatus.CONFIRMED,
            }
        ]

        bias, confidence, evidence = self._determine_bias(confirmed_blocks, structure)
        events = self._build_timeline_events(
            filtered,
            scan_candles,
            timeframe,
            prior_blocks,
        )

        state = MitigationBlockState(
            active_blocks=active_blocks,
            last_analysis_utc=analysis_time,
            bar_count=bar_count,
        )

        return MitigationBlockAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_utc=analysis_time,
            mitigation_blocks=filtered,
            fresh_blocks=fresh_blocks,
            partial_blocks=partial_blocks,
            confirmed_blocks=confirmed_blocks,
            used_blocks=used_blocks,
            invalidated_blocks=invalidated_blocks,
            expired_blocks=expired_blocks,
            bullish_blocks=bullish_blocks,
            bearish_blocks=bearish_blocks,
            nested_blocks=nested_blocks,
            internal_blocks=internal_blocks,
            external_blocks=external_blocks,
            htf_aligned_blocks=htf_aligned_blocks,
            bias=bias,
            confidence=confidence,
            evidence=evidence,
            state=state,
            events=sorted(events, key=lambda event: event.timestamp_utc),
        )

    def detect_bullish_blocks(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        *,
        order_blocks: list[OrderBlock] | None = None,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        htf_mitigation_blocks: list[MitigationBlock] | None = None,
        ltf_mitigation_blocks: list[MitigationBlock] | None = None,
    ) -> list[MitigationBlock]:
        """Detect bullish mitigation blocks only."""
        return self._detect_direction(
            candles,
            MitigationBlockDirection.BULLISH,
            structure,
            order_blocks=order_blocks,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            htf_mitigation_blocks=htf_mitigation_blocks,
            ltf_mitigation_blocks=ltf_mitigation_blocks,
        )

    def detect_bearish_blocks(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        *,
        order_blocks: list[OrderBlock] | None = None,
        liquidity_state: LiquidityState | None = None,
        fair_value_gap_state: FairValueGapState | None = None,
        breaker_blocks: list[BreakerBlock] | None = None,
        htf_mitigation_blocks: list[MitigationBlock] | None = None,
        ltf_mitigation_blocks: list[MitigationBlock] | None = None,
    ) -> list[MitigationBlock]:
        """Detect bearish mitigation blocks only."""
        return self._detect_direction(
            candles,
            MitigationBlockDirection.BEARISH,
            structure,
            order_blocks=order_blocks,
            liquidity_state=liquidity_state,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            htf_mitigation_blocks=htf_mitigation_blocks,
            ltf_mitigation_blocks=ltf_mitigation_blocks,
        )

    def classify_lifecycle(
        self,
        blocks: list[MitigationBlock],
        candles: list[NormalizedCandle],
        *,
        structure: MarketStructure | None = None,
    ) -> list[MitigationBlock]:
        """Update fresh, partial, confirmed, used, invalidated, and expired status."""
        return self._lifecycle.classify_blocks(blocks, candles, structure=structure)

    def _detect_direction(
        self,
        candles: list[NormalizedCandle],
        direction: MitigationBlockDirection,
        structure: MarketStructure | None,
        *,
        order_blocks: list[OrderBlock] | None,
        liquidity_state: LiquidityState | None,
        fair_value_gap_state: FairValueGapState | None,
        breaker_blocks: list[BreakerBlock] | None,
        htf_mitigation_blocks: list[MitigationBlock] | None,
        ltf_mitigation_blocks: list[MitigationBlock] | None,
    ) -> list[MitigationBlock]:
        candidates = self._origin.derive_from_displacement(candles, structure)
        candidates = [c for c in candidates if c.direction is direction]

        blocks: list[MitigationBlock] = []
        for candidate in candidates:
            block = self._candidate_to_block(
                candidate,
                candles,
                structure,
                order_blocks=order_blocks,
                liquidity_state=liquidity_state,
                fair_value_gap_state=fair_value_gap_state,
                breaker_blocks=breaker_blocks,
                htf_mitigation_blocks=htf_mitigation_blocks,
                ltf_mitigation_blocks=ltf_mitigation_blocks,
            )
            if block is not None:
                blocks.append(block)
        return blocks

    def _candidate_to_block(
        self,
        candidate: MitigationCandidate,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
        *,
        order_blocks: list[OrderBlock] | None,
        liquidity_state: LiquidityState | None,
        fair_value_gap_state: FairValueGapState | None,
        breaker_blocks: list[BreakerBlock] | None,
        htf_mitigation_blocks: list[MitigationBlock] | None,
        ltf_mitigation_blocks: list[MitigationBlock] | None,
    ) -> MitigationBlock | None:
        block_id = self._build_block_id(candidate)
        provisional = MitigationBlock(
            block_id=block_id,
            direction=candidate.direction,
            status=MitigationBlockStatus.FRESH,
            high=candidate.high,
            low=candidate.low,
            origin_bar_index=candidate.origin_bar_index,
            origin_time_utc=candidate.origin_time_utc,
            displacement_bar_index=candidate.displacement_bar_index,
            displacement_time_utc=candidate.displacement_time_utc,
            formation_bar_index=candidate.formation_bar_index,
            formation_time_utc=candidate.formation_time_utc,
            quality=MitigationBlockQuality.LOW,
            strength=Decimal("0"),
            is_confirmed=False,
            confirmation_reason="Awaiting price interaction",
            source_type=candidate.source_type,
            is_nested=candidate.parent_zone_id is not None,
            parent_zone_id=candidate.parent_zone_id,
            parent_zone_type=(
                candidate.source_type
                if candidate.parent_zone_id
                else None
            ),
            evidence=list(candidate.evidence),
        )

        scored = self._quality.score(
            provisional,
            candles_count=len(candles),
            structure=structure,
            liquidity_state=liquidity_state,
            order_blocks=order_blocks,
            fair_value_gap_state=fair_value_gap_state,
            breaker_blocks=breaker_blocks,
            htf_mitigation_blocks=htf_mitigation_blocks,
            ltf_mitigation_blocks=ltf_mitigation_blocks,
            displacement_magnitude=candidate.displacement_magnitude,
        )

        if not self._quality.passes_minimum(scored.strength):
            return None

        if self._config.require_structure_alignment and not scored.structure_alignment:
            if structure is None or not self._quality.has_counter_trend_choch(
                scored,
                structure,
            ):
                return None

        return scored

    def _filter_blocks(
        self,
        blocks: list[MitigationBlock],
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
        *,
        order_blocks: list[OrderBlock] | None,
        liquidity_state: LiquidityState | None,
        fair_value_gap_state: FairValueGapState | None,
        breaker_blocks: list[BreakerBlock] | None,
        htf_mitigation_blocks: list[MitigationBlock] | None,
        ltf_mitigation_blocks: list[MitigationBlock] | None,
    ) -> list[MitigationBlock]:
        """Re-score after lifecycle and filter by minimum quality."""
        filtered: list[MitigationBlock] = []
        for block in blocks:
            scored = self._quality.score(
                block,
                candles_count=len(candles),
                structure=structure,
                liquidity_state=liquidity_state,
                order_blocks=order_blocks,
                fair_value_gap_state=fair_value_gap_state,
                breaker_blocks=breaker_blocks,
                htf_mitigation_blocks=htf_mitigation_blocks,
                ltf_mitigation_blocks=ltf_mitigation_blocks,
            )

            if not self._quality.passes_minimum(scored.strength):
                continue

            if self._config.require_structure_alignment and not scored.structure_alignment:
                if structure is None or not self._quality.has_counter_trend_choch(
                    scored,
                    structure,
                ):
                    continue

            confirmation_reason = self._lifecycle.compute_confirmation_reason(
                scored,
                candles,
            )
            is_confirmed = scored.status in {
                MitigationBlockStatus.CONFIRMED,
                MitigationBlockStatus.USED,
            } or self._lifecycle.validate_confirmation(scored, candles)

            filtered.append(
                scored.model_copy(
                    update={
                        "is_confirmed": is_confirmed,
                        "confirmation_reason": confirmation_reason,
                    },
                ),
            )
        return filtered

    def _merge_blocks(
        self,
        prior_blocks: list[MitigationBlock],
        detected: list[MitigationBlock],
    ) -> list[MitigationBlock]:
        merged: dict[str, MitigationBlock] = {
            block.block_id: block for block in prior_blocks
        }
        seen_origins: set[tuple[int, str]] = set()

        for block in prior_blocks:
            seen_origins.add((block.origin_bar_index, block.direction.value))

        for block in detected:
            origin_key = (block.origin_bar_index, block.direction.value)
            if self._config.deduplicate_by_origin and origin_key in seen_origins:
                if block.block_id not in merged:
                    continue

            existing = merged.get(block.block_id)
            if existing is None:
                merged[block.block_id] = block
                seen_origins.add(origin_key)
                continue

            merged[block.block_id] = existing.model_copy(
                update={
                    "quality": block.quality,
                    "strength": block.strength,
                    "structure_scope": block.structure_scope,
                    "structure_alignment": block.structure_alignment,
                    "liquidity_confluence": block.liquidity_confluence,
                    "order_block_confluence": block.order_block_confluence,
                    "fvg_confluence": block.fvg_confluence,
                    "breaker_confluence": block.breaker_confluence,
                    "htf_aligned": block.htf_aligned,
                    "htf_block_ids": block.htf_block_ids,
                    "ltf_nested": block.ltf_nested,
                    "ltf_block_ids": block.ltf_block_ids,
                    "confluence_ids": block.confluence_ids,
                    "premium_discount": block.premium_discount,
                    "dealing_range_high": block.dealing_range_high,
                    "dealing_range_low": block.dealing_range_low,
                    "is_nested": block.is_nested,
                    "parent_zone_id": block.parent_zone_id,
                    "parent_zone_type": block.parent_zone_type,
                    "evidence": block.evidence,
                },
            )
            seen_origins.add(origin_key)

        return sorted(
            merged.values(),
            key=lambda block: (block.formation_time_utc, block.block_id),
        )

    def _build_block_id(self, candidate: MitigationCandidate) -> str:
        prefix = "bull" if candidate.direction is MitigationBlockDirection.BULLISH else "bear"
        price_token = str(candidate.high).replace(".", "_")
        time_token = int(candidate.origin_time_utc.timestamp())
        return (
            f"mb-{prefix}-{price_token}-"
            f"{candidate.origin_bar_index}-{time_token}"
        )

    def _build_timeline_events(
        self,
        blocks: list[MitigationBlock],
        candles: list[NormalizedCandle],
        timeframe: str,
        prior_blocks: list[MitigationBlock],
    ) -> list[MitigationBlockEvent]:
        prior_by_id = {block.block_id: block for block in prior_blocks}
        events: list[MitigationBlockEvent] = []

        def bar_time(index: int | None) -> datetime:
            if index is None or index < 0 or index >= len(candles):
                return candles[-1].close_time_utc if candles else datetime.now(tz=UTC)
            return candles[index].close_time_utc

        for block in blocks:
            prior = prior_by_id.get(block.block_id)

            if prior is None:
                events.append(
                    MitigationBlockEvent(
                        kind=(
                            MitigationBlockEventKind.BULLISH_MITIGATION_BLOCK_DETECTED
                            if block.direction is MitigationBlockDirection.BULLISH
                            else MitigationBlockEventKind.BEARISH_MITIGATION_BLOCK_DETECTED
                        ),
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description=f"{block.direction.value} mitigation block detected",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.high,
                    ),
                )
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.MITIGATION_BLOCK_DETECTED,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="Mitigation block detected",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.high,
                    ),
                )
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.FRESH_MITIGATION_BLOCK,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="Block registered as fresh",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=MitigationBlockStatus.FRESH,
                        price=block.high,
                        touch_count=0,
                        mitigation_percent=Decimal("0"),
                    ),
                )

            if block.is_nested and (prior is None or not prior.is_nested):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.NESTED_MITIGATION_BLOCK,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="Nested mitigation relationship detected",
                        block_id=block.block_id,
                        direction=block.direction,
                        parent_zone_id=block.parent_zone_id,
                    ),
                )

            if block.structure_scope is StructureScope.INTERNAL and (
                prior is None or prior.structure_scope is not StructureScope.INTERNAL
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.INTERNAL_MITIGATION_BLOCK,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="Internal structure scope classified",
                        block_id=block.block_id,
                        direction=block.direction,
                    ),
                )

            if block.structure_scope is StructureScope.EXTERNAL and (
                prior is None or prior.structure_scope is not StructureScope.EXTERNAL
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.EXTERNAL_MITIGATION_BLOCK,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="External structure scope classified",
                        block_id=block.block_id,
                        direction=block.direction,
                    ),
                )

            if block.liquidity_confluence and (
                prior is None or not prior.liquidity_confluence
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.LIQUIDITY_CONFLUENCE_MITIGATION,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="Liquidity confluence detected",
                        block_id=block.block_id,
                        direction=block.direction,
                    ),
                )

            if block.order_block_confluence and (
                prior is None or not prior.order_block_confluence
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.ORDER_BLOCK_CONFLUENCE_MITIGATION,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="Order block confluence detected",
                        block_id=block.block_id,
                        direction=block.direction,
                    ),
                )

            if block.fvg_confluence and (prior is None or not prior.fvg_confluence):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.FVG_CONFLUENCE_MITIGATION,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="FVG confluence detected",
                        block_id=block.block_id,
                        direction=block.direction,
                    ),
                )

            if block.breaker_confluence and (
                prior is None or not prior.breaker_confluence
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.BREAKER_CONFLUENCE_MITIGATION,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="Breaker confluence detected",
                        block_id=block.block_id,
                        direction=block.direction,
                    ),
                )

            if block.htf_aligned and (prior is None or not prior.htf_aligned):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.HTF_MITIGATION_ALIGNED,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="HTF alignment detected",
                        block_id=block.block_id,
                        direction=block.direction,
                    ),
                )

            if block.ltf_nested and (prior is None or not prior.ltf_nested):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.LTF_MITIGATION_NESTED,
                        timestamp_utc=block.formation_time_utc,
                        timeframe=timeframe,
                        description="LTF nesting detected",
                        block_id=block.block_id,
                        direction=block.direction,
                    ),
                )

            if block.status is MitigationBlockStatus.PARTIAL and (
                prior is None or prior.status is MitigationBlockStatus.FRESH
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.PARTIAL_MITIGATION_BLOCK,
                        timestamp_utc=bar_time(block.last_touch_bar_index),
                        timeframe=timeframe,
                        description="Partial mitigation detected",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        touch_count=block.touch_count,
                        mitigation_percent=block.mitigation_percent,
                        price=block.low,
                    ),
                )

            if prior is not None and block.touch_count > prior.touch_count:
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.MULTI_TOUCH_MITIGATION_BLOCK,
                        timestamp_utc=bar_time(block.last_touch_bar_index),
                        timeframe=timeframe,
                        description="Additional touch recorded",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        touch_count=block.touch_count,
                        mitigation_percent=block.mitigation_percent,
                    ),
                )

            if block.mitigation_percent >= Decimal(
                str(self._config.full_mitigation_percent),
            ) and (
                prior is None
                or prior.mitigation_percent
                < Decimal(str(self._config.full_mitigation_percent))
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.FULL_MITIGATION_BLOCK,
                        timestamp_utc=bar_time(block.last_touch_bar_index),
                        timeframe=timeframe,
                        description="Full mitigation threshold reached",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        touch_count=block.touch_count,
                        mitigation_percent=block.mitigation_percent,
                    ),
                )

            if block.status is MitigationBlockStatus.CONFIRMED and (
                prior is None or prior.status is not MitigationBlockStatus.CONFIRMED
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.CONFIRMED_MITIGATION_BLOCK,
                        timestamp_utc=bar_time(block.confirmation_bar_index),
                        timeframe=timeframe,
                        description=block.confirmation_reason,
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        touch_count=block.touch_count,
                        mitigation_percent=block.mitigation_percent,
                        price=block.high,
                    ),
                )

            if block.status is MitigationBlockStatus.USED and (
                prior is not None and prior.status is not MitigationBlockStatus.USED
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.USED_MITIGATION_BLOCK,
                        timestamp_utc=bar_time(block.used_bar_index),
                        timeframe=timeframe,
                        description="Zone fully consumed",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        mitigation_percent=block.mitigation_percent,
                        touch_count=block.touch_count,
                    ),
                )

            if block.status is MitigationBlockStatus.INVALIDATED and (
                prior is not None and prior.status is not MitigationBlockStatus.INVALIDATED
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.INVALIDATED_MITIGATION_BLOCK,
                        timestamp_utc=bar_time(block.invalidation_bar_index),
                        timeframe=timeframe,
                        description="Block invalidated",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.low,
                    ),
                )

            if block.status is MitigationBlockStatus.EXPIRED and (
                prior is not None and prior.status is not MitigationBlockStatus.EXPIRED
            ):
                events.append(
                    MitigationBlockEvent(
                        kind=MitigationBlockEventKind.EXPIRED_MITIGATION_BLOCK,
                        timestamp_utc=bar_time(block.expiration_bar_index),
                        timeframe=timeframe,
                        description="Block expired",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.high,
                    ),
                )

        return events

    @staticmethod
    def _determine_bias(
        confirmed_blocks: list[MitigationBlock],
        structure: MarketStructure | None,
    ) -> tuple[MitigationBlockBias, Decimal, list[str]]:
        evidence: list[str] = []

        if not confirmed_blocks:
            evidence.append("No confirmed mitigation blocks")
            return MitigationBlockBias.UNDETERMINED, Decimal("0"), evidence

        bullish = [
            b for b in confirmed_blocks if b.direction is MitigationBlockDirection.BULLISH
        ]
        bearish = [
            b for b in confirmed_blocks if b.direction is MitigationBlockDirection.BEARISH
        ]

        bullish_in_discount = sum(
            1 for b in bullish if b.premium_discount is PremiumDiscountZone.DISCOUNT
        )
        bearish_in_premium = sum(
            1 for b in bearish if b.premium_discount is PremiumDiscountZone.PREMIUM
        )

        if structure is not None:
            evidence.append(f"Structure trend: {structure.current_trend.value}")

        if len(bullish) > len(bearish):
            evidence.append(
                f"Confirmed bullish blocks dominate ({len(bullish)} vs {len(bearish)})",
            )
            if bullish_in_discount:
                evidence.append(
                    f"{bullish_in_discount} confirmed bullish blocks in discount",
                )
            confidence = Decimal(str(len(bullish) / max(len(confirmed_blocks), 1)))
            return MitigationBlockBias.BULLISH, min(Decimal("1"), confidence), evidence

        if len(bearish) > len(bullish):
            evidence.append(
                f"Confirmed bearish blocks dominate ({len(bearish)} vs {len(bullish)})",
            )
            if bearish_in_premium:
                evidence.append(
                    f"{bearish_in_premium} confirmed bearish blocks in premium",
                )
            confidence = Decimal(str(len(bearish) / max(len(confirmed_blocks), 1)))
            return MitigationBlockBias.BEARISH, min(Decimal("1"), confidence), evidence

        evidence.append("Balanced confirmed bullish and bearish blocks")
        return MitigationBlockBias.NEUTRAL, Decimal("0.5"), evidence
