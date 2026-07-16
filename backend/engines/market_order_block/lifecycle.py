"""Order block lifecycle classification."""

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_order_block.config import OrderBlockConfig
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockStatus,
)


class LifecycleManager:
    """Classify and update order block lifecycle status."""

    def __init__(self, config: OrderBlockConfig) -> None:
        self._config = config

    def update_status(
        self,
        block: OrderBlock,
        candles: list[NormalizedCandle],
    ) -> OrderBlock:
        """Evaluate lifecycle from displacement bar through latest candle."""
        start_index = block.displacement_bar_index + 1
        status = OrderBlockStatus.FRESH
        mitigation_index: int | None = block.mitigation_bar_index
        invalidation_index: int | None = block.invalidation_bar_index

        for index in range(start_index, len(candles)):
            candle = candles[index]

            if status is OrderBlockStatus.INVALIDATED:
                break

            if self._is_invalidated(block, candle):
                status = OrderBlockStatus.INVALIDATED
                invalidation_index = index
                continue

            if status is OrderBlockStatus.FRESH and self._touches_zone(block, candle):
                status = OrderBlockStatus.MITIGATED
                mitigation_index = index

        return block.model_copy(
            update={
                "status": status,
                "mitigation_bar_index": mitigation_index,
                "invalidation_bar_index": invalidation_index,
            },
        )

    def classify_blocks(
        self,
        blocks: list[OrderBlock],
        candles: list[NormalizedCandle],
    ) -> list[OrderBlock]:
        """Update lifecycle for all blocks."""
        return [self.update_status(block, candles) for block in blocks]

    def expire_old_blocks(
        self,
        blocks: list[OrderBlock],
        current_bar_count: int,
    ) -> list[OrderBlock]:
        """Mark blocks beyond max age as invalidated."""
        expired: list[OrderBlock] = []
        for block in blocks:
            age = current_bar_count - block.origin_bar_index
            if age > self._config.max_block_age_bars and block.status is not OrderBlockStatus.INVALIDATED:
                expired.append(
                    block.model_copy(
                        update={"status": OrderBlockStatus.INVALIDATED},
                    ),
                )
            else:
                expired.append(block)
        return expired

    def _touches_zone(self, block: OrderBlock, candle: NormalizedCandle) -> bool:
        mode = self._config.mitigation_touch_mode
        if mode == "wick":
            return candle.low <= block.high and candle.high >= block.low
        if mode == "body":
            body_high = max(candle.open, candle.close)
            body_low = min(candle.open, candle.close)
            return body_low <= block.high and body_high >= block.low

        return block.low <= candle.close <= block.high

    def _is_invalidated(self, block: OrderBlock, candle: NormalizedCandle) -> bool:
        mode = self._config.invalidation_mode
        if block.direction is OrderBlockDirection.BULLISH:
            if mode == "close":
                return candle.close < block.low
            body_low = min(candle.open, candle.close)
            return body_low < block.low

        if mode == "close":
            return candle.close > block.high
        body_high = max(candle.open, candle.close)
        return body_high > block.high
