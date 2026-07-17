"""Bearish premium / discount analysis — premium territory and bearish Fib."""

from decimal import Decimal
from uuid import uuid4

from backend.engines.market_premium_discount.config import PremiumDiscountConfig
from backend.engines.market_premium_discount.schemas import (
    ArrayZoneEntry,
    DealingRange,
    FibDirection,
    FibonacciDealingRange,
    FibonacciLevel,
    OptimalTradeEntryZone,
    PremiumDiscountQuality,
    PremiumDiscountZone,
)
from backend.engines.market_structure.schemas import TrendDirection


class BearishPremiumDiscountAnalyzer:
    """Premium-side Fibonacci projection and OTE derivation."""

    def __init__(self, config: PremiumDiscountConfig) -> None:
        self._config = config

    def project_fibonacci(
        self,
        dealing_range: DealingRange,
    ) -> FibonacciDealingRange:
        """Project Fibonacci levels from range high toward low."""
        levels: list[FibonacciLevel] = []
        for ratio_value in self._config.fibonacci_levels:
            ratio = Decimal(str(ratio_value))
            price = dealing_range.high - (dealing_range.range_size * ratio)
            label = self._fib_label(ratio)
            levels.append(FibonacciLevel(ratio=ratio, price=price, label=label))

        ote_high = dealing_range.high - (
            dealing_range.range_size * Decimal(str(self._config.ote_fib_low))
        )
        ote_low = dealing_range.high - (
            dealing_range.range_size * Decimal(str(self._config.ote_fib_high))
        )
        equilibrium = dealing_range.high - (dealing_range.range_size * Decimal("0.5"))

        return FibonacciDealingRange(
            range_id=dealing_range.range_id,
            direction=FibDirection.BEARISH,
            levels=levels,
            ote_low_level=ote_low,
            ote_high_level=ote_high,
            equilibrium_level=equilibrium,
        )

    def derive_ote(
        self,
        dealing_range: DealingRange,
        fibonacci: FibonacciDealingRange,
        zone_entries: list[ArrayZoneEntry],
    ) -> OptimalTradeEntryZone | None:
        """Derive premium OTE band for bearish / short context."""
        if not self._config.ote_enabled or not dealing_range.is_valid:
            return None

        low = fibonacci.ote_low_level
        high = fibonacci.ote_high_level
        if low >= high:
            return None

        overlapping = [
            entry.zone_id
            for entry in zone_entries
            if self._zones_overlap(entry.low, entry.high, low, high)
        ]
        if self._config.ote_require_zone_overlap and len(overlapping) < self._config.ote_min_overlapping_zones:
            return None

        strength = Decimal("0.5") + Decimal("0.1") * Decimal(str(min(len(overlapping), 5)))
        strength = min(Decimal("1"), strength)
        quality = (
            PremiumDiscountQuality.HIGH
            if strength >= Decimal("0.7")
            else PremiumDiscountQuality.MEDIUM
            if strength >= Decimal("0.45")
            else PremiumDiscountQuality.LOW
        )

        evidence = [
            "Bearish OTE derived in premium territory",
            f"OTE band {low} – {high}",
        ]
        if overlapping:
            evidence.append(f"{len(overlapping)} institutional zones overlap OTE")

        return OptimalTradeEntryZone(
            ote_id=f"ote-bear-{uuid4().hex[:12]}",
            territory=PremiumDiscountZone.PREMIUM,
            direction=FibDirection.BEARISH,
            high=high,
            low=low,
            fib_low_ratio=Decimal(str(self._config.ote_fib_low)),
            fib_high_ratio=Decimal(str(self._config.ote_fib_high)),
            overlapping_zone_ids=overlapping,
            quality=quality,
            strength=strength,
            evidence=evidence,
        )

    def supports_trend(self, trend: TrendDirection | None) -> bool:
        """Return whether bearish premium context aligns with structure trend."""
        return trend in {TrendDirection.BEARISH, TrendDirection.RANGE, None}

    @staticmethod
    def _fib_label(ratio: Decimal) -> str:
        if ratio == Decimal("0"):
            return "range_high"
        if ratio == Decimal("1"):
            return "range_low"
        if ratio == Decimal("0.5"):
            return "equilibrium"
        return f"fib_{ratio}"

    @staticmethod
    def _zones_overlap(
        low_a: Decimal,
        high_a: Decimal,
        low_b: Decimal,
        high_b: Decimal,
    ) -> bool:
        return low_a <= high_b and high_a >= low_b
