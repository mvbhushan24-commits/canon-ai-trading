"""Breaker candidate formation from invalidated upstream zones."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_breaker.config import BreakerBlockConfig
from backend.engines.market_breaker.schemas import (
    BreakerBlockDirection,
    BreakerCandidate,
    BreakerSourceType,
)
from backend.engines.market_fvg.schemas import FairValueGap, FairValueGapDirection, FairValueGapStatus
from backend.engines.market_order_block.schemas import OrderBlock, OrderBlockDirection, OrderBlockQuality


class OriginDetector:
    """Derive breaker candidates from invalidated order blocks and FVGs."""

    _QUALITY_RANK = {
        OrderBlockQuality.HIGH.value: 3,
        OrderBlockQuality.MEDIUM.value: 2,
        OrderBlockQuality.LOW.value: 1,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    def __init__(self, config: BreakerBlockConfig) -> None:
        self._config = config

    def derive_from_order_blocks(
        self,
        invalidated_blocks: list[OrderBlock],
        candles: list[NormalizedCandle],
    ) -> list[BreakerCandidate]:
        """Map invalidated order blocks to breaker candidates."""
        candidates: list[BreakerCandidate] = []
        seen_sources: set[str] = set()
        lookback_start = max(0, len(candles) - self._config.lookback)

        for block in invalidated_blocks:
            if self._config.deduplicate_by_source and block.block_id in seen_sources:
                continue

            if block.invalidation_bar_index is None:
                continue
            if block.invalidation_bar_index < lookback_start:
                continue
            if not self._meets_min_quality(block.quality.value):
                continue

            zone_size = block.high - block.low
            if zone_size < self._config.min_zone_size_price:
                continue

            direction = self._flip_direction(block.direction)
            invalidation_time = self._bar_time(candles, block.invalidation_bar_index)
            formation_index = min(
                block.invalidation_bar_index + 1,
                len(candles) - 1,
            )
            formation_time = self._bar_time(candles, formation_index)

            candidates.append(
                BreakerCandidate(
                    source_type=BreakerSourceType.ORDER_BLOCK,
                    source_id=block.block_id,
                    source_direction=block.direction.value,
                    direction=direction,
                    high=block.high,
                    low=block.low,
                    invalidation_bar_index=block.invalidation_bar_index,
                    invalidation_time_utc=invalidation_time,
                    source_strength=block.strength,
                    source_quality=block.quality.value,
                    formation_bar_index=formation_index,
                    formation_time_utc=formation_time,
                ),
            )
            seen_sources.add(block.block_id)

        return candidates

    def derive_from_fvgs(
        self,
        invalidated_fvgs: list[FairValueGap],
        candles: list[NormalizedCandle],
    ) -> list[BreakerCandidate]:
        """Map invalidated fair value gaps to breaker candidates."""
        if not self._config.fvg_breaker_enabled:
            return []

        candidates: list[BreakerCandidate] = []
        seen_sources: set[str] = set()
        lookback_start = max(0, len(candles) - self._config.lookback)

        for gap in invalidated_fvgs:
            if gap.status is not FairValueGapStatus.INVALIDATED:
                continue
            if self._config.deduplicate_by_source and gap.gap_id in seen_sources:
                continue
            if gap.invalidation_bar_index is None:
                continue
            if gap.invalidation_bar_index < lookback_start:
                continue
            if not self._meets_min_quality(gap.quality.value):
                continue

            zone_size = gap.high - gap.low
            if zone_size < self._config.min_zone_size_price:
                continue

            direction = self._flip_fvg_direction(gap.direction)
            invalidation_time = self._bar_time(candles, gap.invalidation_bar_index)
            formation_index = min(
                gap.invalidation_bar_index + 1,
                len(candles) - 1,
            )
            formation_time = self._bar_time(candles, formation_index)

            candidates.append(
                BreakerCandidate(
                    source_type=BreakerSourceType.FAIR_VALUE_GAP,
                    source_id=gap.gap_id,
                    source_direction=gap.direction.value,
                    direction=direction,
                    high=gap.high,
                    low=gap.low,
                    invalidation_bar_index=gap.invalidation_bar_index,
                    invalidation_time_utc=invalidation_time,
                    source_strength=gap.strength,
                    source_quality=gap.quality.value,
                    formation_bar_index=formation_index,
                    formation_time_utc=formation_time,
                ),
            )
            seen_sources.add(gap.gap_id)

        return candidates

    def _meets_min_quality(self, quality: str) -> bool:
        min_rank = self._QUALITY_RANK.get(self._config.min_source_quality, 2)
        source_rank = self._QUALITY_RANK.get(quality.lower(), 0)
        return source_rank >= min_rank

    @staticmethod
    def _flip_direction(direction: OrderBlockDirection) -> BreakerBlockDirection:
        if direction is OrderBlockDirection.BULLISH:
            return BreakerBlockDirection.BEARISH
        return BreakerBlockDirection.BULLISH

    @staticmethod
    def _flip_fvg_direction(direction: FairValueGapDirection) -> BreakerBlockDirection:
        if direction is FairValueGapDirection.BULLISH:
            return BreakerBlockDirection.BEARISH
        return BreakerBlockDirection.BULLISH

    @staticmethod
    def _bar_time(candles: list[NormalizedCandle], index: int) -> datetime:
        if index < 0 or index >= len(candles):
            return datetime.now(tz=UTC)
        return candles[index].close_time_utc
