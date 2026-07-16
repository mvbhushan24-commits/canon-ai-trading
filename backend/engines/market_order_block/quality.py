"""Order block quality scoring."""

from decimal import Decimal

from backend.engines.market_liquidity.schemas import LiquidityAnalysis, LiquiditySide
from backend.engines.market_order_block.config import OrderBlockConfig
from backend.engines.market_order_block.schemas import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockQuality,
    OrderBlockStatus,
)
from backend.engines.market_structure.schemas import CHoCHDirection, MarketStructure, TrendDirection


class QualityScorer:
    """Compute composite strength and quality classification."""

    def __init__(self, config: OrderBlockConfig) -> None:
        self._config = config

    def score(
        self,
        block: OrderBlock,
        *,
        displacement_magnitude: Decimal,
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
        bar_count: int = 0,
    ) -> tuple[Decimal, OrderBlockQuality, bool, bool, list[str]]:
        """Return strength, quality tier, alignment flags, and evidence."""
        evidence: list[str] = []
        weights = self._config.quality_weights

        displacement_score = self._displacement_score(displacement_magnitude)
        structure_score, structure_alignment = self._structure_score(block, structure, evidence)
        liquidity_score, liquidity_confluence = self._liquidity_score(
            block,
            liquidity,
            evidence,
        )
        freshness_score = self._freshness_score(block, bar_count, evidence)

        strength = (
            displacement_score * Decimal(str(weights.displacement))
            + structure_score * Decimal(str(weights.structure))
            + liquidity_score * Decimal(str(weights.liquidity))
            + freshness_score * Decimal(str(weights.freshness))
        )
        strength = min(Decimal("1"), max(Decimal("0"), strength))
        quality = self._quality_tier(strength)

        return strength, quality, structure_alignment, liquidity_confluence, evidence

    def passes_minimum(self, strength: Decimal) -> bool:
        return strength >= Decimal(str(self._config.min_quality_score))

    def _displacement_score(self, magnitude: Decimal) -> Decimal:
        minimum = Decimal(str(self._config.min_displacement_price))
        if minimum <= 0:
            return Decimal("0")
        ratio = magnitude / minimum
        return min(Decimal("1"), max(Decimal("0"), ratio / Decimal("2")))

    def _structure_score(
        self,
        block: OrderBlock,
        structure: MarketStructure | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool]:
        if structure is None:
            evidence.append("Structure context unavailable")
            return Decimal("0.3"), False

        trend = structure.current_trend
        aligned = (
            block.direction is OrderBlockDirection.BULLISH
            and trend is TrendDirection.BULLISH
        ) or (
            block.direction is OrderBlockDirection.BEARISH
            and trend is TrendDirection.BEARISH
        )

        if aligned:
            evidence.append(f"Aligned with {trend.value} structure trend")
            return Decimal("1"), True

        if self.has_counter_trend_choch(block, structure):
            evidence.append("Counter-trend block supported by CHoCH")
            return Decimal("0.7"), False

        if trend is TrendDirection.RANGE:
            evidence.append("Structure in range — neutral alignment")
            return Decimal("0.5"), False

        evidence.append(f"Counter to {trend.value} structure trend")
        return Decimal("0.2"), False

    def has_counter_trend_choch(
        self,
        block: OrderBlock,
        structure: MarketStructure,
    ) -> bool:
        for event in structure.choch_events:
            if event.bar_index < block.origin_bar_index:
                continue
            if block.direction is OrderBlockDirection.BULLISH:
                if event.direction is CHoCHDirection.BULLISH:
                    return True
            elif event.direction is CHoCHDirection.BEARISH:
                return True
        return False

    def _liquidity_score(
        self,
        block: OrderBlock,
        liquidity: LiquidityAnalysis | None,
        evidence: list[str],
    ) -> tuple[Decimal, bool]:
        if not self._config.use_liquidity_confluence or liquidity is None:
            if liquidity is None:
                evidence.append("Liquidity context unavailable")
            return Decimal("0.3"), False

        confluence = self._has_liquidity_confluence(block, liquidity)
        if confluence:
            evidence.append("Liquidity sweep confluence near order block zone")
            return Decimal("1"), True

        if block.direction is OrderBlockDirection.BULLISH:
            if liquidity.bias is LiquiditySide.SELL_SIDE:
                return Decimal("0.6"), False
        elif liquidity.bias is LiquiditySide.BUY_SIDE:
            return Decimal("0.6"), False

        return Decimal("0.4"), False

    def _has_liquidity_confluence(
        self,
        block: OrderBlock,
        liquidity: LiquidityAnalysis,
    ) -> bool:
        tolerance = Decimal(str(self._config.pip_size * 5))

        for sweep in liquidity.sweeps:
            if abs(sweep.swept_level - block.high) <= tolerance:
                return True
            if abs(sweep.swept_level - block.low) <= tolerance:
                return True

        for zone in liquidity.zones:
            if zone.lower_bound <= block.high and zone.upper_bound >= block.low:
                return True

        return False

    def _freshness_score(
        self,
        block: OrderBlock,
        bar_count: int,
        evidence: list[str],
    ) -> Decimal:
        if block.status is OrderBlockStatus.INVALIDATED:
            return Decimal("0")

        if block.status is OrderBlockStatus.FRESH:
            evidence.append("Block remains fresh")
            return Decimal("1")

        if bar_count <= 0:
            return Decimal("0.5")

        age = bar_count - block.origin_bar_index
        max_age = self._config.max_block_age_bars
        if age >= max_age:
            return Decimal("0.1")

        ratio = Decimal(str(age)) / Decimal(str(max_age))
        return max(Decimal("0.2"), Decimal("1") - ratio)

    @staticmethod
    def _quality_tier(strength: Decimal) -> OrderBlockQuality:
        if strength >= Decimal("0.7"):
            return OrderBlockQuality.HIGH
        if strength >= Decimal("0.4"):
            return OrderBlockQuality.MEDIUM
        return OrderBlockQuality.LOW
