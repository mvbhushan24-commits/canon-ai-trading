"""Take profit generation for trade decisions."""

from decimal import Decimal

from backend.engines.market_decision.config import MarketDecisionConfig
from backend.engines.market_decision.schemas import EvidenceBundle, TradeDirection


class TakeProfitGenerator:
    """Compute profit targets at liquidity and structure levels."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def generate(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
        entry_price: Decimal,
        stop_loss: Decimal,
    ) -> list[Decimal]:
        if direction is TradeDirection.NONE:
            return []

        targets: list[Decimal] = []
        min_distance = Decimal(str(self._config.take_profit.min_target_distance_pips)) * self._config.pip_size_decimal

        if self._config.take_profit.prefer_liquidity_pools and bundle.liquidity is not None:
            if direction is TradeDirection.BUY:
                pool_prices = [
                    level.price
                    for level in bundle.liquidity.sell_side_liquidity
                    if level.price > entry_price + min_distance
                ]
            else:
                pool_prices = [
                    level.price
                    for level in bundle.liquidity.buy_side_liquidity
                    if level.price < entry_price - min_distance
                ]
            targets.extend(sorted(pool_prices, reverse=direction is TradeDirection.SELL))

        if bundle.structure is not None:
            if direction is TradeDirection.BUY:
                structure_targets = [
                    swing.price
                    for swing in bundle.structure.swing_highs
                    if swing.price > entry_price + min_distance
                ]
            else:
                structure_targets = [
                    swing.price
                    for swing in bundle.structure.swing_lows
                    if swing.price < entry_price - min_distance
                ]
            targets.extend(sorted(structure_targets, reverse=direction is TradeDirection.SELL))

        if bundle.fair_value_gaps is not None:
            for gap in bundle.fair_value_gaps.open_gaps:
                target = gap.high if direction is TradeDirection.BUY else gap.low
                if direction is TradeDirection.BUY and target > entry_price + min_distance:
                    targets.append(target)
                elif direction is TradeDirection.SELL and target < entry_price - min_distance:
                    targets.append(target)

        if bundle.premium_discount is not None:
            if direction is TradeDirection.BUY:
                targets.append(bundle.premium_discount.dealing_range.high)
            else:
                targets.append(bundle.premium_discount.dealing_range.low)

        unique_targets: list[Decimal] = []
        seen: set[str] = set()
        for target in targets:
            key = str(target)
            if key not in seen:
                seen.add(key)
                unique_targets.append(target)

        if direction is TradeDirection.BUY:
            unique_targets.sort()
        else:
            unique_targets.sort(reverse=True)

        if not unique_targets:
            risk = abs(entry_price - stop_loss)
            multiplier = Decimal(str(self._config.take_profit.rr_fallback_multiplier))
            if direction is TradeDirection.BUY:
                unique_targets.append(entry_price + risk * multiplier)
            else:
                unique_targets.append(entry_price - risk * multiplier)

        return unique_targets[: self._config.take_profit.max_targets]
