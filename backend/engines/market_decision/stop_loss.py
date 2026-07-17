"""Stop loss generation for trade decisions."""

from decimal import Decimal

from backend.engines.market_decision.config import MarketDecisionConfig
from backend.engines.market_decision.schemas import (
    EntrySpec,
    EvidenceBundle,
    GateResult,
    TradeDirection,
)


class StopLossGenerator:
    """Compute protective stop beyond invalidation structure."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def generate(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
        entry: EntrySpec,
        entry_price: Decimal,
    ) -> tuple[Decimal | None, GateResult]:
        if direction is TradeDirection.NONE:
            return None, GateResult(passed=False, blocking_reason="No direction for stop loss")

        buffer = Decimal(str(self._config.stop_loss.buffer_pips)) * self._config.pip_size_decimal
        invalidation_levels: list[Decimal] = []

        if bundle.structure is not None:
            if direction is TradeDirection.BUY and bundle.structure.swing_lows:
                invalidation_levels.append(bundle.structure.swing_lows[-1].price)
            elif direction is TradeDirection.SELL and bundle.structure.swing_highs:
                invalidation_levels.append(bundle.structure.swing_highs[-1].price)

        if entry.zone_low is not None and direction is TradeDirection.BUY:
            invalidation_levels.append(entry.zone_low)
        if entry.zone_high is not None and direction is TradeDirection.SELL:
            invalidation_levels.append(entry.zone_high)

        if bundle.order_blocks is not None and bundle.order_blocks.fresh_blocks:
            block = bundle.order_blocks.fresh_blocks[0]
            if direction is TradeDirection.BUY:
                invalidation_levels.append(block.low)
            else:
                invalidation_levels.append(block.high)

        if bundle.liquidity is not None:
            if direction is TradeDirection.BUY and bundle.liquidity.equal_lows:
                invalidation_levels.append(bundle.liquidity.equal_lows[-1].price)
            elif direction is TradeDirection.SELL and bundle.liquidity.equal_highs:
                invalidation_levels.append(bundle.liquidity.equal_highs[-1].price)

        if not invalidation_levels:
            fallback_distance = (
                Decimal(str(self._config.stop_loss.fallback_atr_multiplier))
                * Decimal("10")
                * self._config.pip_size_decimal
            )
            if direction is TradeDirection.BUY:
                stop = entry_price - fallback_distance
            else:
                stop = entry_price + fallback_distance
        elif direction is TradeDirection.BUY:
            stop = min(invalidation_levels) - buffer
        else:
            stop = max(invalidation_levels) + buffer

        stop_size_pips = abs(entry_price - stop) / self._config.pip_size_decimal
        if stop_size_pips > Decimal(str(self._config.risk.max_stop_size_pips)):
            return (
                None,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason=(
                        f"Stop size {stop_size_pips.quantize(Decimal('0.1'))} pips exceeds maximum "
                        f"{self._config.risk.max_stop_size_pips}"
                    ),
                ),
            )

        if direction is TradeDirection.BUY and stop >= entry_price:
            return (
                None,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason="BUY stop loss must be below entry price",
                ),
            )
        if direction is TradeDirection.SELL and stop <= entry_price:
            return (
                None,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason="SELL stop loss must be above entry price",
                ),
            )

        return stop, GateResult(passed=True)
