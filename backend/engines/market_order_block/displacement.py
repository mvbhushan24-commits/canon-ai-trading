"""Displacement move validation for order block candidates."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_order_block.config import OrderBlockConfig
from backend.engines.market_order_block.schemas import OrderBlockDirection, OriginCandidate
from backend.engines.market_structure.schemas import BOSDirection, MarketStructure


class DisplacementValidator:
    """Validate displacement magnitude and structure confirmation."""

    def __init__(self, config: OrderBlockConfig) -> None:
        self._config = config

    def validate(
        self,
        candidate: OriginCandidate,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
    ) -> tuple[bool, int, Decimal, list[str]]:
        """Return validity, displacement bar index, magnitude, and evidence."""
        evidence: list[str] = []
        start = candidate.displacement_start_index
        end = min(start + self._config.min_impulse_candles, len(candles))
        if end <= start:
            return False, start, Decimal("0"), evidence

        displacement_index = end - 1
        magnitude = self._displacement_magnitude(candidate, candles, displacement_index)
        min_required = Decimal(str(self._config.min_displacement_price))

        if magnitude < min_required:
            return False, displacement_index, magnitude, evidence

        evidence.append(
            f"Displacement {magnitude} exceeds minimum {min_required}",
        )

        if structure is not None and self._has_bos_confirmation(
            candidate,
            structure,
            displacement_index,
        ):
            evidence.append("Break of structure confirms displacement")

        return True, displacement_index, magnitude, evidence

    def _displacement_magnitude(
        self,
        candidate: OriginCandidate,
        candles: list[NormalizedCandle],
        displacement_index: int,
    ) -> Decimal:
        start = candidate.displacement_start_index
        segment = candles[start : displacement_index + 1]
        if not segment:
            return Decimal("0")

        if candidate.direction is OrderBlockDirection.BULLISH:
            move_high = max(candle.high for candle in segment)
            return move_high - candidate.zone_high

        move_low = min(candle.low for candle in segment)
        return candidate.zone_low - move_low

    def _has_bos_confirmation(
        self,
        candidate: OriginCandidate,
        structure: MarketStructure,
        displacement_index: int,
    ) -> bool:
        for event in structure.bos_events:
            if event.bar_index < candidate.origin_bar_index:
                continue
            if event.bar_index > displacement_index:
                continue
            if candidate.direction is OrderBlockDirection.BULLISH:
                if event.direction is BOSDirection.BULLISH:
                    return True
            elif event.direction is BOSDirection.BEARISH:
                return True
        return False
