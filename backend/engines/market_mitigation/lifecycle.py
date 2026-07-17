"""Mitigation block lifecycle, touch tracking, confirmation, and expiration."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_mitigation.config import MitigationBlockConfig
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockDirection,
    MitigationBlockStatus,
)
from backend.engines.market_structure import CHoCHDirection, MarketStructure


class LifecycleManager:
    """Classify and update mitigation block lifecycle status."""

    def __init__(self, config: MitigationBlockConfig) -> None:
        self._config = config

    def validate_confirmation(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
    ) -> bool:
        """Check whether block passes confirmation rules."""
        confirmed, _ = self._evaluate_confirmation(block, candles)
        return confirmed

    def compute_confirmation_reason(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
    ) -> str:
        """Return human-readable confirmation explanation."""
        if block.status is MitigationBlockStatus.FRESH and block.touch_count == 0:
            return "Awaiting price interaction"

        confirmed, reason = self._evaluate_confirmation(block, candles)
        if confirmed:
            return reason
        if block.is_confirmed or block.status is MitigationBlockStatus.CONFIRMED:
            return block.confirmation_reason or "Previously confirmed"
        return reason

    def track_touches(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
    ) -> MitigationBlock:
        """Update touch count and mitigation percent from candle interactions."""
        return self.update_status(block, candles)

    def update_status(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
        *,
        structure: MarketStructure | None = None,
    ) -> MitigationBlock:
        """Evaluate lifecycle from formation bar through latest candle."""
        status = block.status
        mitigation_percent = block.mitigation_percent
        touch_count = block.touch_count
        first_touch = block.first_touch_bar_index
        last_touch = block.last_touch_bar_index
        confirmation_index = block.confirmation_bar_index
        confirmation_time = block.confirmation_time_utc
        used_index = block.used_bar_index
        invalidation_index = block.invalidation_bar_index
        expiration_index = block.expiration_bar_index
        is_confirmed = block.is_confirmed
        confirmation_reason = block.confirmation_reason

        if status in {MitigationBlockStatus.EXPIRED, MitigationBlockStatus.INVALIDATED}:
            return block

        start_index = block.formation_bar_index + 1
        last_touch_for_gap = -self._config.min_bars_between_touches - 1
        deepest_penetration = Decimal("0")
        zone_size = block.high - block.low
        ce_price = (block.high + block.low) / Decimal("2")

        for index in range(start_index, len(candles)):
            candle = candles[index]
            age = index - block.formation_bar_index

            if status not in {
                MitigationBlockStatus.USED,
                MitigationBlockStatus.INVALIDATED,
                MitigationBlockStatus.EXPIRED,
            }:
                if age > self._config.max_block_age_bars:
                    if status in {
                        MitigationBlockStatus.FRESH,
                        MitigationBlockStatus.PARTIAL,
                        MitigationBlockStatus.CONFIRMED,
                    }:
                        status = MitigationBlockStatus.EXPIRED
                        expiration_index = index
                        confirmation_reason = (
                            f"Exceeded max block age ({self._config.max_block_age_bars} bars)"
                        )
                        break

            if status is MitigationBlockStatus.USED and not self._config.invalidate_used_blocks:
                break

            if self._is_invalidated(block, candle, status):
                status = MitigationBlockStatus.INVALIDATED
                invalidation_index = index
                confirmation_reason = "Zone broken in opposing direction"
                break

            if (
                self._config.invalidate_on_choch
                and structure is not None
                and self._choch_invalidates(block, structure, index)
            ):
                status = MitigationBlockStatus.INVALIDATED
                invalidation_index = index
                confirmation_reason = "Counter-trend CHoCH invalidates block"
                break

            if index < block.formation_bar_index + self._config.min_bars_after_formation:
                continue

            touched, touch_price = self._detect_touch(block, candle)
            if not touched:
                continue

            penetration = self._compute_penetration(block, candle)
            deepest_penetration = max(deepest_penetration, penetration)
            if zone_size > 0:
                mitigation_percent = min(
                    Decimal("100"),
                    (deepest_penetration / zone_size) * Decimal("100"),
                )

            if self._config.ce_mitigation_enabled and self._touches_ce(block, candle, ce_price):
                mitigation_percent = Decimal(str(self._config.full_mitigation_percent))

            is_new_touch = index != last_touch and (
                index - last_touch_for_gap >= self._config.min_bars_between_touches
            )
            if is_new_touch:
                touch_count += 1
                last_touch_for_gap = index
                if first_touch is None:
                    first_touch = index
                last_touch = index

                if status is MitigationBlockStatus.FRESH:
                    status = MitigationBlockStatus.PARTIAL
                    confirmation_reason = "Partial mitigation detected"

            if mitigation_percent >= Decimal(str(self._config.full_mitigation_percent)):
                if status is MitigationBlockStatus.PARTIAL and not is_confirmed:
                    confirmed, reason = self._check_confirmation_at_bar(block, candles, index)
                    if confirmed or self._config.min_touch_count <= touch_count:
                        status = MitigationBlockStatus.CONFIRMED
                        is_confirmed = True
                        confirmation_index = index
                        confirmation_time = candle.close_time_utc
                        confirmation_reason = reason or "Full mitigation threshold reached"

                if status in {
                    MitigationBlockStatus.PARTIAL,
                    MitigationBlockStatus.CONFIRMED,
                }:
                    status = MitigationBlockStatus.USED
                    used_index = index
                    confirmation_reason = "Zone fully consumed"
                    break

            if status is MitigationBlockStatus.PARTIAL and not is_confirmed:
                confirmed, reason = self._check_confirmation_at_bar(block, candles, index)
                if confirmed and touch_count >= self._config.min_touch_count:
                    status = MitigationBlockStatus.CONFIRMED
                    is_confirmed = True
                    confirmation_index = index
                    confirmation_time = candle.close_time_utc
                    confirmation_reason = reason

            if status is MitigationBlockStatus.FRESH and touched:
                status = MitigationBlockStatus.PARTIAL

        return block.model_copy(
            update={
                "status": status,
                "mitigation_percent": mitigation_percent,
                "touch_count": touch_count,
                "first_touch_bar_index": first_touch,
                "last_touch_bar_index": last_touch,
                "confirmation_bar_index": confirmation_index,
                "confirmation_time_utc": confirmation_time,
                "used_bar_index": used_index,
                "invalidation_bar_index": invalidation_index,
                "expiration_bar_index": expiration_index,
                "is_confirmed": is_confirmed,
                "confirmation_reason": confirmation_reason,
            },
        )

    def classify_blocks(
        self,
        blocks: list[MitigationBlock],
        candles: list[NormalizedCandle],
        *,
        structure: MarketStructure | None = None,
    ) -> list[MitigationBlock]:
        """Update lifecycle for all blocks."""
        return [
            self.update_status(block, candles, structure=structure) for block in blocks
        ]

    def _evaluate_confirmation(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
    ) -> tuple[bool, str]:
        if block.is_confirmed or block.status is MitigationBlockStatus.CONFIRMED:
            return True, block.confirmation_reason or "Mitigation confirmed"

        min_bar = block.formation_bar_index + self._config.min_bars_after_formation
        for index in range(min_bar, len(candles)):
            confirmed, reason = self._check_confirmation_at_bar(block, candles, index)
            if confirmed and block.touch_count >= self._config.min_touch_count:
                return True, reason

        if block.touch_count >= self._config.min_touch_count and block.touch_count > 0:
            return False, (
                f"Awaiting confirmation ({block.touch_count} touches, "
                f"mode={self._config.confirmation_mode})"
            )
        return False, "No price interaction since formation"

    def _check_confirmation_at_bar(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
        index: int,
    ) -> tuple[bool, str]:
        if index <= block.formation_bar_index:
            return False, "Before minimum bars after formation"

        min_bar = block.formation_bar_index + self._config.min_bars_after_formation
        if index < min_bar:
            return False, "Before minimum bars after formation"

        candle = candles[index]
        mode = self._config.confirmation_mode

        if mode == "wick_touch":
            if not self._wick_enters_zone(block, candle):
                return False, "No wick touch"
            reason = (
                f"Wick entered zone {index - block.formation_bar_index} bars after formation"
            )
        elif mode == "body_touch":
            if not self._body_enters_zone(block, candle):
                return False, "No body touch"
            reason = (
                f"Body entered zone {index - block.formation_bar_index} bars after formation"
            )
        elif mode == "close_inside":
            if not (block.low <= candle.close <= block.high):
                return False, "Close not inside zone"
            reason = (
                f"Close inside zone {index - block.formation_bar_index} bars after formation"
            )
        elif mode == "rejection":
            if not self._is_rejection_candle(block, candle):
                return False, "No rejection candle"
            reason = (
                f"Rejection candle at bar {index} "
                f"({index - block.formation_bar_index} bars after formation)"
            )
        elif mode == "displacement_after":
            if not self._has_displacement_after(block, candles, index):
                return False, "No displacement after touch"
            reason = f"Displacement after touch at bar {index}"
        else:
            return False, f"Unknown confirmation mode: {mode}"

        if self._config.require_displacement_after_touch:
            if not self._has_displacement_after(block, candles, index):
                return False, "No displacement after touch"

        return True, reason

    def _detect_touch(
        self,
        block: MitigationBlock,
        candle: NormalizedCandle,
    ) -> tuple[bool, Decimal]:
        mode = self._config.mitigation_mode
        if mode == "wick":
            touched = self._wick_enters_zone(block, candle)
            price = min(candle.high, block.high)
        elif mode == "body":
            touched = self._body_enters_zone(block, candle)
            price = (max(candle.open, candle.close) + min(candle.open, candle.close)) / 2
        elif mode == "close":
            touched = block.low <= candle.close <= block.high
            price = candle.close
        else:
            touched = self._wick_enters_zone(block, candle) or self._body_enters_zone(
                block,
                candle,
            )
            price = candle.close

        return touched, Decimal(str(price))

    def _compute_penetration(
        self,
        block: MitigationBlock,
        candle: NormalizedCandle,
    ) -> Decimal:
        overlap_low = max(block.low, candle.low)
        overlap_high = min(block.high, candle.high)
        if overlap_high <= overlap_low:
            if block.direction is MitigationBlockDirection.BULLISH:
                if candle.low <= block.high:
                    return min(block.high - candle.low, block.high - block.low)
            elif candle.high >= block.low:
                return min(candle.high - block.low, block.high - block.low)
            return Decimal("0")
        return overlap_high - overlap_low

    @staticmethod
    def _touches_ce(
        block: MitigationBlock,
        candle: NormalizedCandle,
        ce_price: Decimal,
    ) -> bool:
        return candle.low <= ce_price <= candle.high

    def _wick_enters_zone(
        self,
        block: MitigationBlock,
        candle: NormalizedCandle,
    ) -> bool:
        return candle.low <= block.high and candle.high >= block.low

    def _body_enters_zone(
        self,
        block: MitigationBlock,
        candle: NormalizedCandle,
    ) -> bool:
        body_high = max(candle.open, candle.close)
        body_low = min(candle.open, candle.close)
        return body_low <= block.high and body_high >= block.low

    def _is_rejection_candle(
        self,
        block: MitigationBlock,
        candle: NormalizedCandle,
    ) -> bool:
        if not self._wick_enters_zone(block, candle):
            return False

        body_high = max(candle.open, candle.close)
        body_low = min(candle.open, candle.close)
        body_size = body_high - body_low
        if body_size <= 0:
            return False

        if block.direction is MitigationBlockDirection.BULLISH:
            wick_below = body_low - candle.low
            if wick_below <= 0 or candle.close < block.low:
                return False
            wick_ratio = wick_below / body_size
            return wick_ratio >= Decimal(str(self._config.rejection_wick_ratio))

        wick_above = candle.high - body_high
        if wick_above <= 0 or candle.close > block.high:
            return False
        wick_ratio = wick_above / body_size
        return wick_ratio >= Decimal(str(self._config.rejection_wick_ratio))

    def _has_displacement_after(
        self,
        block: MitigationBlock,
        candles: list[NormalizedCandle],
        touch_index: int,
    ) -> bool:
        if touch_index + 1 >= len(candles):
            return False

        next_candle = candles[touch_index + 1]
        min_move = self._config.min_displacement_price
        if block.direction is MitigationBlockDirection.BULLISH:
            return next_candle.close - block.high >= min_move
        return block.low - next_candle.close >= min_move

    def _is_invalidated(
        self,
        block: MitigationBlock,
        candle: NormalizedCandle,
        status: MitigationBlockStatus,
    ) -> bool:
        if status is MitigationBlockStatus.USED and not self._config.invalidate_used_blocks:
            return False

        mode = self._config.invalidation_mode
        if block.direction is MitigationBlockDirection.BULLISH:
            if mode == "close":
                return candle.close < block.low
            if mode == "body":
                return min(candle.open, candle.close) < block.low
            return candle.low < block.low

        if mode == "close":
            return candle.close > block.high
        if mode == "body":
            return max(candle.open, candle.close) > block.high
        return candle.high > block.high

    @staticmethod
    def _choch_invalidates(
        block: MitigationBlock,
        structure: MarketStructure,
        bar_index: int,
    ) -> bool:
        for event in structure.choch_events:
            if event.bar_index != bar_index:
                continue
            if block.direction is MitigationBlockDirection.BULLISH:
                if event.direction is CHoCHDirection.BEARISH:
                    return True
            elif event.direction is CHoCHDirection.BULLISH:
                return True
        return False

    @staticmethod
    def _bar_time(candles: list[NormalizedCandle], index: int | None) -> datetime:
        if index is None or index < 0 or index >= len(candles):
            return datetime.now(tz=UTC)
        return candles[index].close_time_utc
