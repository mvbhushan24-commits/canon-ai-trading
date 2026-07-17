"""Swing anchor selection and dealing range construction."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_premium_discount.config import (
    PremiumDiscountConfig,
    SwingSelectionMode,
)
from backend.engines.market_premium_discount.schemas import (
    DealingRange,
    DealingRangeScope,
    PremiumDiscountQuality,
    SwingAnchor,
)
from backend.engines.market_structure import MarketStructure, SwingPoint
from backend.engines.market_structure.schemas import SwingKind, SwingLabel


def _format_price(price: Decimal) -> str:
    return str(price).replace(".", "_")


class SwingAnchorSelector:
    """Select swing high and swing low anchors for dealing ranges."""

    def __init__(self, config: PremiumDiscountConfig) -> None:
        self._config = config

    def select_anchors(
        self,
        structure: MarketStructure,
        scope: DealingRangeScope,
        candles: list[NormalizedCandle],
    ) -> tuple[SwingAnchor | None, SwingAnchor | None]:
        """Select swing high and low anchors for the given scope."""
        structure_state = (
            structure.external_structure
            if scope is DealingRangeScope.EXTERNAL
            else structure.internal_structure
        )

        mode = self._config.swing_selection_mode
        lookback_start = max(0, len(candles) - self._config.swing_lookback_bars)

        if mode == SwingSelectionMode.STRUCTURE_STATE.value:
            high = self._anchor_from_swing(
                structure_state.last_swing_high,
                candles,
            )
            low = self._anchor_from_swing(
                structure_state.last_swing_low,
                candles,
            )
            return high, low

        swing_highs = self._swing_pool(structure, SwingKind.SWING_HIGH, scope)
        swing_lows = self._swing_pool(structure, SwingKind.SWING_LOW, scope)

        if mode == SwingSelectionMode.RANGE_EXTREME.value:
            high = self._extreme_anchor(swing_highs, candles, SwingKind.SWING_HIGH, maximize=True)
            low = self._extreme_anchor(swing_lows, candles, SwingKind.SWING_LOW, maximize=False)
            return high, low

        high = self._latest_anchor(swing_highs, candles, SwingKind.SWING_HIGH, lookback_start)
        low = self._latest_anchor(swing_lows, candles, SwingKind.SWING_LOW, lookback_start)
        return high, low

    def score_swing_quality(
        self,
        swing: SwingPoint | None,
        structure: MarketStructure | None,
        *,
        bar_count: int,
    ) -> Decimal:
        """Score swing quality from label, recency, and structure proximity."""
        if swing is None:
            return Decimal("0")

        score = Decimal("0.4")
        if swing.label is not SwingLabel.NONE:
            score += Decimal("0.25")
            if swing.label in {SwingLabel.HH, SwingLabel.LL}:
                score += Decimal("0.05")

        if bar_count > 0:
            recency = Decimal(str(max(0, bar_count - swing.bar_index))) / Decimal(str(bar_count))
            score += (Decimal("1") - min(recency, Decimal("1"))) * Decimal("0.2")

        if structure is not None:
            if structure.bos_events:
                latest_bos = structure.bos_events[-1]
                if abs(latest_bos.bar_index - swing.bar_index) <= 5:
                    score += Decimal("0.1")
            score += min(structure.confidence, Decimal("1")) * Decimal("0.1")

        return min(Decimal("1"), max(Decimal("0"), score))

    def _swing_pool(
        self,
        structure: MarketStructure,
        kind: SwingKind,
        scope: DealingRangeScope,
    ) -> list[SwingPoint]:
        primary = structure.swing_highs if kind is SwingKind.SWING_HIGH else structure.swing_lows
        state = (
            structure.external_structure
            if scope is DealingRangeScope.EXTERNAL
            else structure.internal_structure
        )
        fallback = state.last_swing_high if kind is SwingKind.SWING_HIGH else state.last_swing_low
        pool = list(primary)
        if fallback is not None and all(item.bar_index != fallback.bar_index for item in pool):
            pool.append(fallback)
        return pool

    def _anchor_from_swing(
        self,
        swing: SwingPoint | None,
        candles: list[NormalizedCandle],
    ) -> SwingAnchor | None:
        if swing is None:
            return None
        return SwingAnchor(
            price=swing.price,
            timestamp_utc=swing.timestamp_utc,
            bar_index=swing.bar_index,
            kind=swing.kind,
            label=swing.label,
            quality_score=Decimal("0"),
        )

    def _latest_anchor(
        self,
        swings: list[SwingPoint],
        candles: list[NormalizedCandle],
        kind: SwingKind,
        lookback_start: int,
    ) -> SwingAnchor | None:
        candidates = [swing for swing in swings if swing.bar_index >= lookback_start]
        if not candidates and swings:
            candidates = swings
        if not candidates:
            return None

        if self._config.prefer_labeled_swings:
            labeled = [swing for swing in candidates if swing.label is not SwingLabel.NONE]
            if labeled:
                candidates = labeled

        selected = max(candidates, key=lambda swing: swing.bar_index)
        return SwingAnchor(
            price=selected.price,
            timestamp_utc=selected.timestamp_utc,
            bar_index=selected.bar_index,
            kind=kind,
            label=selected.label,
            quality_score=Decimal("0"),
        )

    def _extreme_anchor(
        self,
        swings: list[SwingPoint],
        candles: list[NormalizedCandle],
        kind: SwingKind,
        *,
        maximize: bool,
    ) -> SwingAnchor | None:
        if not swings:
            return None
        selected = max(swings, key=lambda swing: swing.price) if maximize else min(
            swings,
            key=lambda swing: swing.price,
        )
        return SwingAnchor(
            price=selected.price,
            timestamp_utc=selected.timestamp_utc,
            bar_index=selected.bar_index,
            kind=kind,
            label=selected.label,
            quality_score=Decimal("0"),
        )


class DealingRangeBuilder:
    """Construct and validate dealing ranges from swing anchors."""

    def __init__(self, config: PremiumDiscountConfig) -> None:
        self._config = config
        self._selector = SwingAnchorSelector(config)

    def build(
        self,
        structure: MarketStructure | None,
        scope: DealingRangeScope,
        candles: list[NormalizedCandle],
        *,
        timeframe: str,
    ) -> DealingRange:
        """Build dealing range for scope; returns invalid range when evidence insufficient."""
        if structure is None:
            return self._invalid_range(
                scope,
                timeframe,
                reason="Structure context unavailable",
            )

        swing_high, swing_low = self._selector.select_anchors(structure, scope, candles)
        if swing_high is None or swing_low is None:
            return self._invalid_range(
                scope,
                timeframe,
                reason="Missing swing anchors",
            )

        bar_count = len(candles)
        swing_high = swing_high.model_copy(
            update={
                "quality_score": self._selector.score_swing_quality(
                    self._find_swing_point(structure, swing_high),
                    structure,
                    bar_count=bar_count,
                ),
            },
        )
        swing_low = swing_low.model_copy(
            update={
                "quality_score": self._selector.score_swing_quality(
                    self._find_swing_point(structure, swing_low),
                    structure,
                    bar_count=bar_count,
                ),
            },
        )

        if (
            swing_high.quality_score < Decimal(str(self._config.min_swing_quality_score))
            or swing_low.quality_score < Decimal(str(self._config.min_swing_quality_score))
        ):
            return self._invalid_range(
                scope,
                timeframe,
                reason="Swing quality below minimum threshold",
                swing_high=swing_high,
                swing_low=swing_low,
            )

        if (
            swing_high.bar_index == swing_low.bar_index
            and not self._config.allow_same_bar_range
        ):
            return self._invalid_range(
                scope,
                timeframe,
                reason="Swing high and low on same bar",
                swing_high=swing_high,
                swing_low=swing_low,
            )

        high = max(swing_high.price, swing_low.price)
        low = min(swing_high.price, swing_low.price)
        if high <= low:
            return self._invalid_range(
                scope,
                timeframe,
                reason="Invalid dealing range bounds",
                swing_high=swing_high,
                swing_low=swing_low,
            )

        range_size = high - low
        if range_size < self._config.min_range_size_price:
            return self._invalid_range(
                scope,
                timeframe,
                reason="Range size below minimum",
                swing_high=swing_high,
                swing_low=swing_low,
                high=high,
                low=low,
            )

        equilibrium = (high + low) / Decimal("2")
        formation_bar = max(swing_high.bar_index, swing_low.bar_index)
        formation_time = max(swing_high.timestamp_utc, swing_low.timestamp_utc)
        range_id = (
            f"dr-{scope.value}-{_format_price(high)}-{_format_price(low)}-{timeframe.lower()}"
        )

        evidence = [
            f"{scope.value} dealing range from swing high {swing_high.price} and low {swing_low.price}",
            f"Equilibrium at {equilibrium}",
        ]

        return DealingRange(
            range_id=range_id,
            scope=scope,
            high=high,
            low=low,
            equilibrium=equilibrium,
            range_size=range_size,
            swing_high=swing_high,
            swing_low=swing_low,
            formation_bar_index=formation_bar,
            formation_time_utc=formation_time,
            is_valid=True,
            quality=PremiumDiscountQuality.MEDIUM,
            strength=Decimal("0.5"),
            evidence=evidence,
        )

    @staticmethod
    def _find_swing_point(
        structure: MarketStructure,
        anchor: SwingAnchor,
    ) -> SwingPoint | None:
        pool = structure.swing_highs + structure.swing_lows
        for swing in pool:
            if swing.bar_index == anchor.bar_index and swing.kind == anchor.kind:
                return swing
        return None

    def _invalid_range(
        self,
        scope: DealingRangeScope,
        timeframe: str,
        *,
        reason: str,
        swing_high: SwingAnchor | None = None,
        swing_low: SwingAnchor | None = None,
        high: Decimal | None = None,
        low: Decimal | None = None,
    ) -> DealingRange:
        placeholder_time = datetime.now(tz=UTC)
        placeholder_high = swing_high or SwingAnchor(
            price=Decimal("0"),
            timestamp_utc=placeholder_time,
            bar_index=0,
            kind=SwingKind.SWING_HIGH,
        )
        placeholder_low = swing_low or SwingAnchor(
            price=Decimal("0"),
            timestamp_utc=placeholder_time,
            bar_index=0,
            kind=SwingKind.SWING_LOW,
        )
        range_high = high or max(placeholder_high.price, placeholder_low.price)
        range_low = low or min(placeholder_high.price, placeholder_low.price)
        if range_high <= range_low:
            range_high = Decimal("1")
            range_low = Decimal("0")

        equilibrium = (range_high + range_low) / Decimal("2")
        range_id = f"dr-{scope.value}-invalid-{timeframe.lower()}"

        return DealingRange(
            range_id=range_id,
            scope=scope,
            high=range_high,
            low=range_low,
            equilibrium=equilibrium,
            range_size=range_high - range_low,
            swing_high=placeholder_high,
            swing_low=placeholder_low,
            formation_bar_index=0,
            formation_time_utc=placeholder_time,
            is_valid=False,
            invalidation_reason=reason,
            quality=PremiumDiscountQuality.LOW,
            strength=Decimal("0"),
            evidence=[reason],
        )
