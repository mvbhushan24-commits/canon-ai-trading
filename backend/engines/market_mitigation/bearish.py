"""Bearish mitigation block formation detection."""

from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_mitigation.config import MitigationBlockConfig
from backend.engines.market_mitigation.schemas import MitigationBlockDirection, MitigationCandidate
from backend.engines.market_structure import MarketStructure
from backend.engines.market_structure.schemas import BOSDirection


class BearishMitigationDetector:
    """Identify bearish mitigation blocks from bullish origin candles."""

    def __init__(self, config: MitigationBlockConfig) -> None:
        self._config = config

    def find_formations(
        self,
        candles: list[NormalizedCandle],
        structure: MarketStructure | None = None,
    ) -> list[MitigationCandidate]:
        """Return bearish mitigation candidates from displacement legs."""
        candidates: list[MitigationCandidate] = []
        scan_end = len(candles) - 1
        if scan_end < 2:
            return candidates

        lookback_start = max(0, len(candles) - self._config.lookback)

        for index in range(max(1, lookback_start), scan_end):
            origin = candles[index]
            if origin.close <= origin.open:
                continue

            zone_high, zone_low = self._zone_bounds(origin)
            zone_size = zone_high - zone_low
            if zone_size < self._config.min_zone_size_price:
                continue

            displacement_index, magnitude = self._find_displacement(
                candles,
                index,
                zone_low,
            )
            if displacement_index is None or magnitude < self._config.min_displacement_price:
                continue

            if self._config.require_bos_displacement and structure is not None:
                if not self._has_bos_confirmation(structure, index, displacement_index):
                    continue

            formation_index = displacement_index
            evidence = [
                f"Bearish mitigation from bullish origin at bar {index}",
                f"Displacement magnitude {magnitude}",
            ]

            candidates.append(
                MitigationCandidate(
                    direction=MitigationBlockDirection.BEARISH,
                    high=zone_high,
                    low=zone_low,
                    origin_bar_index=index,
                    origin_time_utc=origin.open_time_utc,
                    displacement_bar_index=displacement_index,
                    displacement_time_utc=candles[displacement_index].close_time_utc,
                    formation_bar_index=formation_index,
                    formation_time_utc=candles[formation_index].close_time_utc,
                    displacement_magnitude=magnitude,
                    evidence=evidence,
                ),
            )

        return candidates

    def _zone_bounds(self, candle: NormalizedCandle) -> tuple[Decimal, Decimal]:
        mode = self._config.zone_bound_mode
        if mode == "body":
            return max(candle.open, candle.close), min(candle.open, candle.close)
        if mode == "wick":
            return candle.high, candle.low
        return candle.high, candle.low

    def _find_displacement(
        self,
        candles: list[NormalizedCandle],
        origin_index: int,
        zone_low: Decimal,
    ) -> tuple[int | None, Decimal]:
        start = origin_index + 1
        min_low = zone_low
        displacement_index: int | None = None

        for index in range(start, min(start + 10, len(candles))):
            candle = candles[index]
            if candle.close >= candle.open:
                break
            min_low = min(min_low, candle.low)
            magnitude = zone_low - min_low
            if magnitude >= self._config.min_displacement_price:
                displacement_index = index
                return displacement_index, magnitude

        if displacement_index is not None:
            return displacement_index, zone_low - min_low
        return None, Decimal("0")

    @staticmethod
    def _has_bos_confirmation(
        structure: MarketStructure,
        origin_index: int,
        displacement_index: int,
    ) -> bool:
        for event in structure.bos_events:
            if event.bar_index < origin_index:
                continue
            if event.bar_index > displacement_index:
                continue
            if event.direction is BOSDirection.BEARISH:
                return True
        return False
