"""Order block detection orchestrator."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_liquidity.schemas import LiquidityAnalysis
from backend.engines.market_order_block.config import OrderBlockConfig
from backend.engines.market_order_block.displacement import DisplacementValidator
from backend.engines.market_order_block.lifecycle import LifecycleManager
from backend.engines.market_order_block.origin import OriginDetector
from backend.engines.market_order_block.quality import QualityScorer
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockAnalysis,
    OrderBlockBias,
    OrderBlockDirection,
    OrderBlockEvent,
    OrderBlockEventKind,
    OrderBlockQuality,
    OrderBlockState,
    OrderBlockStatus,
    OriginCandidate,
)
from backend.engines.market_structure.schemas import MarketStructure


class OrderBlockDetector:
    """Orchestrate origin, displacement, lifecycle, and quality detection."""

    def __init__(
        self,
        config: OrderBlockConfig,
        origin_detector: OriginDetector | None = None,
        displacement_validator: DisplacementValidator | None = None,
        lifecycle_manager: LifecycleManager | None = None,
        quality_scorer: QualityScorer | None = None,
    ) -> None:
        self._config = config
        self._origin = origin_detector or OriginDetector(config)
        self._displacement = displacement_validator or DisplacementValidator(config)
        self._lifecycle = lifecycle_manager or LifecycleManager(config)
        self._quality = quality_scorer or QualityScorer(config)

    def detect(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
        prior_state: OrderBlockState | None = None,
    ) -> OrderBlockAnalysis:
        """Run full order block analysis pipeline."""
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

        bullish_blocks = self.detect_bullish_blocks(scan_candles, structure, liquidity)
        bearish_blocks = self.detect_bearish_blocks(scan_candles, structure, liquidity)
        detected = bullish_blocks + bearish_blocks

        prior_blocks = prior_state.active_blocks if prior_state else []
        merged = self._merge_blocks(prior_blocks, detected, scan_candles)
        classified = self.classify_lifecycle(merged, scan_candles)
        expired = self._lifecycle.expire_old_blocks(classified, bar_count)

        fresh_blocks = [b for b in expired if b.status is OrderBlockStatus.FRESH]
        mitigated_blocks = [b for b in expired if b.status is OrderBlockStatus.MITIGATED]
        invalidated_blocks = [
            b for b in expired if b.status is OrderBlockStatus.INVALIDATED
        ]

        bias, confidence, evidence = self._determine_bias(
            fresh_blocks,
            mitigated_blocks,
            structure,
        )
        events = self._build_timeline_events(
            expired,
            scan_candles,
            timeframe,
            prior_blocks,
        )

        state = OrderBlockState(
            active_blocks=expired,
            last_analysis_utc=analysis_time,
            bar_count=bar_count,
        )

        return OrderBlockAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_utc=analysis_time,
            order_blocks=expired,
            fresh_blocks=fresh_blocks,
            mitigated_blocks=mitigated_blocks,
            invalidated_blocks=invalidated_blocks,
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
        liquidity: LiquidityAnalysis | None = None,
    ) -> list[OrderBlock]:
        """Detect bullish order blocks only."""
        return self._detect_direction(
            candles,
            OrderBlockDirection.BULLISH,
            structure,
            liquidity,
        )

    def detect_bearish_blocks(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
    ) -> list[OrderBlock]:
        """Detect bearish order blocks only."""
        return self._detect_direction(
            candles,
            OrderBlockDirection.BEARISH,
            structure,
            liquidity,
        )

    def classify_lifecycle(
        self,
        blocks: list[OrderBlock],
        candles: list[NormalizedCandle],
    ) -> list[OrderBlock]:
        """Update fresh, mitigated, and invalidated status."""
        return self._lifecycle.classify_blocks(blocks, candles)

    def _detect_direction(
        self,
        candles: list[NormalizedCandle],
        direction: OrderBlockDirection,
        structure: MarketStructure | None,
        liquidity: LiquidityAnalysis | None,
    ) -> list[OrderBlock]:
        if direction is OrderBlockDirection.BULLISH:
            candidates = self._origin.find_bullish_origins(candles)
        else:
            candidates = self._origin.find_bearish_origins(candles)

        blocks: list[OrderBlock] = []
        for candidate in candidates:
            block = self._candidate_to_block(
                candidate,
                candles,
                structure,
                liquidity,
            )
            if block is not None:
                blocks.append(block)
        return blocks

    def _candidate_to_block(
        self,
        candidate: OriginCandidate,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None,
        liquidity: LiquidityAnalysis | None,
    ) -> OrderBlock | None:
        valid, displacement_index, magnitude, displacement_evidence = (
            self._displacement.validate(candidate, candles, structure)
        )
        if not valid:
            return None

        block_id = self._build_block_id(candidate)
        provisional = OrderBlock(
            block_id=block_id,
            direction=candidate.direction,
            status=OrderBlockStatus.FRESH,
            high=candidate.zone_high,
            low=candidate.zone_low,
            origin_bar_index=candidate.origin_bar_index,
            origin_time_utc=candidate.origin_time_utc,
            displacement_bar_index=displacement_index,
            quality=OrderBlockQuality.LOW,
            strength=Decimal("0"),
            structure_alignment=False,
            liquidity_confluence=False,
            evidence=list(displacement_evidence),
        )

        strength, quality, structure_alignment, liquidity_confluence, quality_evidence = (
            self._quality.score(
                provisional,
                displacement_magnitude=magnitude,
                structure=structure,
                liquidity=liquidity,
                bar_count=len(candles),
            )
        )

        if not self._quality.passes_minimum(strength):
            return None

        if self._config.require_structure_alignment and not structure_alignment:
            if structure is None or not self._quality.has_counter_trend_choch(
                provisional,
                structure,
            ):
                return None

        evidence = displacement_evidence + quality_evidence
        return provisional.model_copy(
            update={
                "quality": quality,
                "strength": strength,
                "structure_alignment": structure_alignment,
                "liquidity_confluence": liquidity_confluence,
                "evidence": evidence,
            },
        )

    def _merge_blocks(
        self,
        prior_blocks: list[OrderBlock],
        detected: list[OrderBlock],
        candles: list[NormalizedCandle],
    ) -> list[OrderBlock]:
        merged: dict[str, OrderBlock] = {
            block.block_id: block for block in prior_blocks
        }
        for block in detected:
            existing = merged.get(block.block_id)
            if existing is None:
                merged[block.block_id] = block
                continue

            merged[block.block_id] = existing.model_copy(
                update={
                    "quality": block.quality,
                    "strength": block.strength,
                    "structure_alignment": block.structure_alignment,
                    "liquidity_confluence": block.liquidity_confluence,
                    "evidence": block.evidence,
                },
            )

        return sorted(
            merged.values(),
            key=lambda block: (block.origin_time_utc, block.block_id),
        )

    def _build_block_id(self, candidate: OriginCandidate) -> str:
        prefix = "bull" if candidate.direction is OrderBlockDirection.BULLISH else "bear"
        price_token = str(candidate.zone_high).replace(".", "_")
        time_token = int(candidate.origin_time_utc.timestamp())
        return f"ob-{prefix}-{price_token}-{candidate.origin_bar_index}-{time_token}"

    def _build_timeline_events(
        self,
        blocks: list[OrderBlock],
        candles: list[NormalizedCandle],
        timeframe: str,
        prior_blocks: list[OrderBlock],
    ) -> list[OrderBlockEvent]:
        prior_by_id = {block.block_id: block for block in prior_blocks}
        events: list[OrderBlockEvent] = []

        def bar_time(index: int | None) -> datetime:
            if index is None or index < 0 or index >= len(candles):
                return candles[-1].close_time_utc if candles else datetime.now(tz=UTC)
            return candles[index].close_time_utc

        for block in blocks:
            prior = prior_by_id.get(block.block_id)
            if prior is None:
                events.append(
                    OrderBlockEvent(
                        kind=(
                            OrderBlockEventKind.BULLISH_ORDER_BLOCK_DETECTED
                            if block.direction is OrderBlockDirection.BULLISH
                            else OrderBlockEventKind.BEARISH_ORDER_BLOCK_DETECTED
                        ),
                        timestamp_utc=block.origin_time_utc,
                        timeframe=timeframe,
                        description=f"{block.direction.value} order block detected",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.high,
                    ),
                )
                events.append(
                    OrderBlockEvent(
                        kind=OrderBlockEventKind.ORDER_BLOCK_DETECTED,
                        timestamp_utc=block.origin_time_utc,
                        timeframe=timeframe,
                        description="Order block detected",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.high,
                    ),
                )

            if block.status is OrderBlockStatus.FRESH and (
                prior is None or prior.status is not OrderBlockStatus.FRESH
            ):
                events.append(
                    OrderBlockEvent(
                        kind=OrderBlockEventKind.FRESH_ORDER_BLOCK,
                        timestamp_utc=block.origin_time_utc,
                        timeframe=timeframe,
                        description="Order block confirmed fresh",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.high,
                    ),
                )

            if (
                block.status is OrderBlockStatus.MITIGATED
                and prior is not None
                and prior.status is not OrderBlockStatus.MITIGATED
            ):
                events.append(
                    OrderBlockEvent(
                        kind=OrderBlockEventKind.MITIGATED_ORDER_BLOCK,
                        timestamp_utc=bar_time(block.mitigation_bar_index),
                        timeframe=timeframe,
                        description="Order block mitigated",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.low,
                    ),
                )

            if (
                block.status is OrderBlockStatus.INVALIDATED
                and prior is not None
                and prior.status is not OrderBlockStatus.INVALIDATED
            ):
                events.append(
                    OrderBlockEvent(
                        kind=OrderBlockEventKind.INVALIDATED_ORDER_BLOCK,
                        timestamp_utc=bar_time(block.invalidation_bar_index),
                        timeframe=timeframe,
                        description="Order block invalidated",
                        block_id=block.block_id,
                        direction=block.direction,
                        status=block.status,
                        price=block.low,
                    ),
                )

        return events

    @staticmethod
    def _determine_bias(
        fresh_blocks: list[OrderBlock],
        mitigated_blocks: list[OrderBlock],
        structure: MarketStructure | None,
    ) -> tuple[OrderBlockBias, Decimal, list[str]]:
        evidence: list[str] = []
        active = fresh_blocks + mitigated_blocks

        if not active:
            evidence.append("No active order blocks")
            return OrderBlockBias.NEUTRAL, Decimal("0"), evidence

        bullish_count = sum(
            1 for block in active if block.direction is OrderBlockDirection.BULLISH
        )
        bearish_count = len(active) - bullish_count

        if structure is not None:
            evidence.append(f"Structure trend: {structure.current_trend.value}")

        if bullish_count > bearish_count:
            evidence.append(
                f"Fresh/mitigated bullish blocks dominate ({bullish_count} vs {bearish_count})",
            )
            confidence = Decimal(str(bullish_count / max(len(active), 1)))
            return OrderBlockBias.BULLISH, min(Decimal("1"), confidence), evidence

        if bearish_count > bullish_count:
            evidence.append(
                f"Fresh/mitigated bearish blocks dominate ({bearish_count} vs {bullish_count})",
            )
            confidence = Decimal(str(bearish_count / max(len(active), 1)))
            return OrderBlockBias.BEARISH, min(Decimal("1"), confidence), evidence

        evidence.append("Balanced bullish and bearish order blocks")
        return OrderBlockBias.NEUTRAL, Decimal("0.5"), evidence
