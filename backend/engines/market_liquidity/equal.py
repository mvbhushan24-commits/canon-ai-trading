"""Equal highs/lows and buy-side/sell-side liquidity detection."""

from decimal import Decimal

from backend.engines.market_liquidity.config import MarketLiquidityConfig
from backend.engines.market_liquidity.schemas import (
    EqualLevelCluster,
    LiquidityKind,
    LiquidityLevel,
)
from backend.engines.market_structure.schemas import MarketStructure, SwingKind, SwingPoint


class EqualLiquidityDetector:
    """Detect equal highs, equal lows, and derived buy/sell-side liquidity."""

    def __init__(self, config: MarketLiquidityConfig) -> None:
        self._config = config

    def detect_equal_highs(
        self,
        structure: MarketStructure | None,
        swing_highs: list[SwingPoint] | None = None,
    ) -> list[EqualLevelCluster]:
        """Detect equal high clusters within pip tolerance."""
        highs = swing_highs or self._swing_highs(structure)
        return self._cluster_levels(
            highs,
            LiquidityKind.EQUAL_HIGH,
            self._config.equal_high_tolerance_price,
        )

    def detect_equal_lows(
        self,
        structure: MarketStructure | None,
        swing_lows: list[SwingPoint] | None = None,
    ) -> list[EqualLevelCluster]:
        """Detect equal low clusters within pip tolerance."""
        lows = swing_lows or self._swing_lows(structure)
        return self._cluster_levels(
            lows,
            LiquidityKind.EQUAL_LOW,
            self._config.equal_low_tolerance_price,
        )

    def detect_buy_side(self, equal_highs: list[EqualLevelCluster]) -> list[LiquidityLevel]:
        """Buy-side liquidity sits above equal highs."""
        levels: list[LiquidityLevel] = []
        for cluster in equal_highs:
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.BUY_SIDE,
                    price=cluster.price,
                    timestamp_utc=cluster.levels[0].timestamp_utc,
                    bar_index=cluster.levels[0].bar_index,
                    is_active=cluster.is_active,
                    strength=Decimal(str(min(1.0, 0.4 + cluster.touched_count * 0.15))),
                    touched_count=cluster.touched_count,
                )
            )
        return levels

    def detect_sell_side(self, equal_lows: list[EqualLevelCluster]) -> list[LiquidityLevel]:
        """Sell-side liquidity sits below equal lows."""
        levels: list[LiquidityLevel] = []
        for cluster in equal_lows:
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.SELL_SIDE,
                    price=cluster.price,
                    timestamp_utc=cluster.levels[0].timestamp_utc,
                    bar_index=cluster.levels[0].bar_index,
                    is_active=cluster.is_active,
                    strength=Decimal(str(min(1.0, 0.4 + cluster.touched_count * 0.15))),
                    touched_count=cluster.touched_count,
                )
            )
        return levels

    def _cluster_levels(
        self,
        swings: list[SwingPoint],
        kind: LiquidityKind,
        tolerance: float,
    ) -> list[EqualLevelCluster]:
        if not swings:
            return []

        tolerance_decimal = Decimal(str(tolerance))
        ordered = sorted(swings, key=lambda s: s.bar_index)
        clusters: list[EqualLevelCluster] = []
        used: set[int] = set()

        for index, swing in enumerate(ordered):
            if index in used:
                continue
            group = [swing]
            used.add(index)
            for other_index, other in enumerate(ordered):
                if other_index in used:
                    continue
                if abs(other.price - swing.price) <= tolerance_decimal:
                    group.append(other)
                    used.add(other_index)

            cluster = self._build_cluster(group, kind)
            if cluster is not None:
                clusters.append(cluster)

        return clusters

    def _build_cluster(
        self,
        swings: list[SwingPoint],
        kind: LiquidityKind,
    ) -> EqualLevelCluster | None:
        if len(swings) < self._config.minimum_cluster_size:
            return None

        avg_price = sum((s.price for s in swings), Decimal("0")) / Decimal(len(swings))
        levels = [
            LiquidityLevel(
                kind=kind,
                price=swing.price,
                timestamp_utc=swing.timestamp_utc,
                bar_index=swing.bar_index,
                touched_count=1,
                strength=Decimal("0.6"),
            )
            for swing in swings
        ]
        return EqualLevelCluster(
            kind=kind,
            price=avg_price,
            levels=levels,
            touched_count=len(swings),
            is_active=True,
        )

    @staticmethod
    def _swing_highs(structure: MarketStructure | None) -> list[SwingPoint]:
        if structure is None:
            return []
        return list(structure.swing_highs)

    @staticmethod
    def _swing_lows(structure: MarketStructure | None) -> list[SwingPoint]:
        if structure is None:
            return []
        return list(structure.swing_lows)

    @staticmethod
    def internal_liquidity(structure: MarketStructure | None) -> list[LiquidityLevel]:
        """Map internal structure swings to liquidity levels."""
        if structure is None:
            return []

        levels: list[LiquidityLevel] = []
        internal = structure.internal_structure
        if internal.last_swing_high is not None:
            swing = internal.last_swing_high
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.INTERNAL_SWING_HIGH,
                    price=swing.price,
                    timestamp_utc=swing.timestamp_utc,
                    bar_index=swing.bar_index,
                    strength=Decimal("0.55"),
                )
            )
        if internal.last_swing_low is not None:
            swing = internal.last_swing_low
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.INTERNAL_SWING_LOW,
                    price=swing.price,
                    timestamp_utc=swing.timestamp_utc,
                    bar_index=swing.bar_index,
                    strength=Decimal("0.55"),
                )
            )

        for swing in structure.swing_highs:
            if swing.kind != SwingKind.SWING_HIGH:
                continue
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.INTERNAL_SWING_HIGH,
                    price=swing.price,
                    timestamp_utc=swing.timestamp_utc,
                    bar_index=swing.bar_index,
                    strength=Decimal("0.5"),
                )
            )
        for swing in structure.swing_lows:
            if swing.kind != SwingKind.SWING_LOW:
                continue
            levels.append(
                LiquidityLevel(
                    kind=LiquidityKind.INTERNAL_SWING_LOW,
                    price=swing.price,
                    timestamp_utc=swing.timestamp_utc,
                    bar_index=swing.bar_index,
                    strength=Decimal("0.5"),
                )
            )
        return levels
