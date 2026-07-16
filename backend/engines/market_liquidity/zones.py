"""Liquidity zone construction from clustered equal levels."""

import uuid
from decimal import Decimal

from backend.engines.market_liquidity.config import MarketLiquidityConfig
from backend.engines.market_liquidity.schemas import (
    EqualLevelCluster,
    LiquiditySide,
    LiquidityZone,
)


class ZoneBuilder:
    """Build liquidity zones around equal high/low clusters."""

    def __init__(self, config: MarketLiquidityConfig) -> None:
        self._config = config

    def build_zones(
        self,
        equal_highs: list[EqualLevelCluster],
        equal_lows: list[EqualLevelCluster],
    ) -> list[LiquidityZone]:
        """Create liquidity zones with configurable buffer."""
        buffer = Decimal(str(self._config.zone_buffer_price))
        zones: list[LiquidityZone] = []

        for cluster in equal_highs:
            zones.append(
                LiquidityZone(
                    zone_id=self._zone_id("buy", cluster.price),
                    side=LiquiditySide.BUY_SIDE,
                    upper_bound=cluster.price + buffer,
                    lower_bound=cluster.price - buffer,
                    anchor_price=cluster.price,
                    cluster_size=cluster.touched_count,
                    timestamp_utc=cluster.levels[0].timestamp_utc,
                    is_active=cluster.is_active,
                )
            )

        for cluster in equal_lows:
            zones.append(
                LiquidityZone(
                    zone_id=self._zone_id("sell", cluster.price),
                    side=LiquiditySide.SELL_SIDE,
                    upper_bound=cluster.price + buffer,
                    lower_bound=cluster.price - buffer,
                    anchor_price=cluster.price,
                    cluster_size=cluster.touched_count,
                    timestamp_utc=cluster.levels[0].timestamp_utc,
                    is_active=cluster.is_active,
                )
            )

        return self._deduplicate_zones(zones)

    @staticmethod
    def _zone_id(prefix: str, price: Decimal) -> str:
        return f"{prefix}-{str(price).replace('.', '_')}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _deduplicate_zones(zones: list[LiquidityZone]) -> list[LiquidityZone]:
        seen: set[tuple[str, str]] = set()
        unique: list[LiquidityZone] = []
        for zone in zones:
            key = (zone.side.value, str(zone.anchor_price))
            if key in seen:
                continue
            seen.add(key)
            unique.append(zone)
        return unique
