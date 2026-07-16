"""Breaker block lifecycle, confirmation, mitigation, and expiration."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_breaker.config import BreakerBlockConfig
from backend.engines.market_breaker.schemas import (
    BreakerBlock,
    BreakerBlockDirection,
    BreakerBlockStatus,
)


class LifecycleManager:
    """Classify and update breaker block lifecycle status."""

    def __init__(self, config: BreakerBlockConfig) -> None:
        self._config = config

    def validate_confirmation(
        self,
        breaker: BreakerBlock,
        candles: list[NormalizedCandle],
    ) -> bool:
        """Check whether breaker passes confirmation rules."""
        confirmed, _ = self._evaluate_confirmation(breaker, candles)
        return confirmed

    def compute_confirmation_reason(
        self,
        breaker: BreakerBlock,
        candles: list[NormalizedCandle],
    ) -> str:
        """Return human-readable confirmation explanation."""
        confirmed, reason = self._evaluate_confirmation(breaker, candles)
        if confirmed:
            return reason
        if breaker.status is BreakerBlockStatus.CONFIRMED:
            return breaker.confirmation_reason or "Previously confirmed"
        return reason

    def update_status(
        self,
        breaker: BreakerBlock,
        candles: list[NormalizedCandle],
    ) -> BreakerBlock:
        """Evaluate lifecycle from formation bar through latest candle."""
        status = breaker.status
        confirmation_index = breaker.confirmation_bar_index
        confirmation_time = breaker.confirmation_time_utc
        mitigation_index = breaker.mitigation_bar_index
        invalidation_index = breaker.invalidation_breaker_bar_index
        expiration_index = breaker.expiration_bar_index
        is_confirmed = breaker.is_confirmed
        confirmation_reason = breaker.confirmation_reason

        start_index = breaker.formation_bar_index
        age_bars = len(candles) - breaker.formation_bar_index

        if status is BreakerBlockStatus.EXPIRED:
            return breaker

        if status in {BreakerBlockStatus.CANDIDATE, BreakerBlockStatus.CONFIRMED}:
            retest_window = (
                breaker.invalidation_bar_index
                + self._config.max_bars_after_invalidation
            )
            if status is BreakerBlockStatus.CANDIDATE:
                bars_since_invalidation = len(candles) - 1 - breaker.invalidation_bar_index
                if bars_since_invalidation > self._config.max_bars_after_invalidation:
                    return breaker.model_copy(
                        update={
                            "status": BreakerBlockStatus.EXPIRED,
                            "expiration_bar_index": len(candles) - 1,
                            "confirmation_reason": (
                                f"Retest window exceeded ({self._config.max_bars_after_invalidation} bars)"
                            ),
                        },
                    )

            if age_bars > self._config.max_breaker_age_bars:
                return breaker.model_copy(
                    update={
                        "status": BreakerBlockStatus.EXPIRED,
                        "expiration_bar_index": len(candles) - 1,
                        "confirmation_reason": (
                            f"Exceeded max breaker age ({self._config.max_breaker_age_bars} bars)"
                        ),
                    },
                )

        for index in range(start_index, len(candles)):
            candle = candles[index]

            if status is BreakerBlockStatus.EXPIRED:
                break

            if status in {BreakerBlockStatus.INVALIDATED, BreakerBlockStatus.MITIGATED}:
                break

            if status is BreakerBlockStatus.CANDIDATE:
                if index > retest_window:
                    status = BreakerBlockStatus.EXPIRED
                    expiration_index = index
                    confirmation_reason = (
                        f"Retest window exceeded ({self._config.max_bars_after_invalidation} bars)"
                    )
                    break

                confirmed, reason = self._check_confirmation_at_bar(breaker, candles, index)
                if confirmed:
                    status = BreakerBlockStatus.CONFIRMED
                    is_confirmed = True
                    confirmation_index = index
                    confirmation_time = candle.close_time_utc
                    confirmation_reason = reason

            elif status is BreakerBlockStatus.CONFIRMED:
                if self._is_breaker_invalidated(breaker, candle):
                    status = BreakerBlockStatus.INVALIDATED
                    invalidation_index = index
                    continue

                if self._detect_mitigation(breaker, candle):
                    status = BreakerBlockStatus.MITIGATED
                    mitigation_index = index

        return breaker.model_copy(
            update={
                "status": status,
                "is_confirmed": is_confirmed,
                "confirmation_reason": confirmation_reason,
                "confirmation_bar_index": confirmation_index,
                "confirmation_time_utc": confirmation_time,
                "mitigation_bar_index": mitigation_index,
                "invalidation_breaker_bar_index": invalidation_index,
                "expiration_bar_index": expiration_index,
            },
        )

    def classify_breakers(
        self,
        breakers: list[BreakerBlock],
        candles: list[NormalizedCandle],
    ) -> list[BreakerBlock]:
        """Update lifecycle for all breakers."""
        return [self.update_status(breaker, candles) for breaker in breakers]

    def _evaluate_confirmation(
        self,
        breaker: BreakerBlock,
        candles: list[NormalizedCandle],
    ) -> tuple[bool, str]:
        if breaker.is_confirmed or breaker.status is BreakerBlockStatus.CONFIRMED:
            return True, breaker.confirmation_reason or "Breaker confirmed"

        min_bar = breaker.invalidation_bar_index + self._config.min_bars_after_invalidation
        max_bar = breaker.invalidation_bar_index + self._config.max_bars_after_invalidation

        for index in range(min_bar, min(max_bar + 1, len(candles))):
            confirmed, reason = self._check_confirmation_at_bar(breaker, candles, index)
            if confirmed:
                return True, reason

        return False, (
            f"Awaiting retest within {self._config.max_bars_after_invalidation} bars"
        )

    def _check_confirmation_at_bar(
        self,
        breaker: BreakerBlock,
        candles: list[NormalizedCandle],
        index: int,
    ) -> tuple[bool, str]:
        if index <= breaker.invalidation_bar_index:
            return False, "Before minimum bars after invalidation"

        min_bar = breaker.invalidation_bar_index + self._config.min_bars_after_invalidation
        if index < min_bar:
            return False, "Before minimum bars after invalidation"

        candle = candles[index]
        mode = self._config.confirmation_mode

        if mode == "wick_touch":
            if not self._wick_enters_zone(breaker, candle):
                return False, "No wick touch"
            reason = f"Wick entered zone {index - breaker.invalidation_bar_index} bars after invalidation"
        elif mode == "body_touch":
            if not self._body_enters_zone(breaker, candle):
                return False, "No body touch"
            reason = f"Body entered zone {index - breaker.invalidation_bar_index} bars after invalidation"
        elif mode == "close_inside":
            if not (breaker.low <= candle.close <= breaker.high):
                return False, "Close not inside zone"
            reason = f"Close inside zone {index - breaker.invalidation_bar_index} bars after invalidation"
        elif mode == "rejection":
            if not self._is_rejection_candle(breaker, candle):
                return False, "No rejection candle"
            reason = (
                f"Rejection candle at bar {index} "
                f"({index - breaker.invalidation_bar_index} bars after invalidation)"
            )
        else:
            return False, f"Unknown confirmation mode: {mode}"

        if self._config.require_displacement_after_invalidation:
            if not self._has_displacement_after(breaker, candles, index):
                return False, "No displacement after invalidation"

        return True, reason

    def _wick_enters_zone(
        self,
        breaker: BreakerBlock,
        candle: NormalizedCandle,
    ) -> bool:
        return candle.low <= breaker.high and candle.high >= breaker.low

    def _body_enters_zone(
        self,
        breaker: BreakerBlock,
        candle: NormalizedCandle,
    ) -> bool:
        body_high = max(candle.open, candle.close)
        body_low = min(candle.open, candle.close)
        return body_low <= breaker.high and body_high >= breaker.low

    def _is_rejection_candle(
        self,
        breaker: BreakerBlock,
        candle: NormalizedCandle,
    ) -> bool:
        if not self._wick_enters_zone(breaker, candle):
            return False

        body_high = max(candle.open, candle.close)
        body_low = min(candle.open, candle.close)
        body_size = body_high - body_low
        if body_size <= 0:
            return False

        if breaker.direction is BreakerBlockDirection.BULLISH:
            wick_below = body_low - candle.low
            if wick_below <= 0:
                return False
            if candle.close < breaker.low:
                return False
            wick_ratio = wick_below / body_size
            return wick_ratio >= Decimal(str(self._config.rejection_wick_ratio))

        wick_above = candle.high - body_high
        if wick_above <= 0:
            return False
        if candle.close > breaker.high:
            return False
        wick_ratio = wick_above / body_size
        return wick_ratio >= Decimal(str(self._config.rejection_wick_ratio))

    def _has_displacement_after(
        self,
        breaker: BreakerBlock,
        candles: list[NormalizedCandle],
        confirmation_index: int,
    ) -> bool:
        if confirmation_index + 1 >= len(candles):
            return False

        next_candle = candles[confirmation_index + 1]
        if breaker.direction is BreakerBlockDirection.BULLISH:
            return next_candle.close > breaker.high
        return next_candle.close < breaker.low

    def _detect_mitigation(
        self,
        breaker: BreakerBlock,
        candle: NormalizedCandle,
    ) -> bool:
        mode = self._config.mitigation_mode
        if mode == "wick":
            return self._wick_enters_zone(breaker, candle)
        if mode == "body":
            return self._body_enters_zone(breaker, candle)
        if mode == "close":
            return breaker.low <= candle.close <= breaker.high
        if mode == "partial":
            return self._partial_mitigation(breaker, candle)

        return False

    def _partial_mitigation(
        self,
        breaker: BreakerBlock,
        candle: NormalizedCandle,
    ) -> bool:
        zone_size = breaker.high - breaker.low
        if zone_size <= 0:
            return False

        overlap_low = max(breaker.low, candle.low)
        overlap_high = min(breaker.high, candle.high)
        if overlap_high <= overlap_low:
            return False

        overlap_size = overlap_high - overlap_low
        percent = (overlap_size / zone_size) * Decimal("100")
        return percent >= Decimal(str(self._config.mitigation_percent))

    def _is_breaker_invalidated(
        self,
        breaker: BreakerBlock,
        candle: NormalizedCandle,
    ) -> bool:
        mode = self._config.invalidation_mode
        if breaker.direction is BreakerBlockDirection.BULLISH:
            if mode == "close":
                return candle.close < breaker.low
            if mode == "body":
                return min(candle.open, candle.close) < breaker.low
            return candle.low < breaker.low

        if mode == "close":
            return candle.close > breaker.high
        if mode == "body":
            return max(candle.open, candle.close) > breaker.high
        return candle.high > breaker.high

    @staticmethod
    def _bar_time(candles: list[NormalizedCandle], index: int | None) -> datetime:
        if index is None or index < 0 or index >= len(candles):
            return datetime.now(tz=UTC)
        return candles[index].close_time_utc
