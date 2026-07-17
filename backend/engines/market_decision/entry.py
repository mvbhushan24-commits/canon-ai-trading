"""Entry zone derivation and validation."""

from decimal import Decimal

from backend.engines.market_decision.config import MarketDecisionConfig
from backend.engines.market_decision.schemas import (
    CandidateZone,
    EntrySpec,
    EntryType,
    EvidenceBundle,
    GateResult,
    TradeDirection,
)
from backend.engines.market_fvg.schemas import FairValueGapDirection, FairValueGapStatus
from backend.engines.market_mitigation.schemas import MitigationBlockDirection, MitigationBlockStatus
from backend.engines.market_order_block.schemas import OrderBlockDirection, OrderBlockStatus


class EntryGenerator:
    """Derive and validate entry zones from confluent institutional zones."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def generate(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
    ) -> tuple[EntrySpec | None, GateResult, list[CandidateZone]]:
        if direction is TradeDirection.NONE:
            return None, GateResult(passed=False, blocking_reason="No direction for entry"), []

        candidates = self._collect_candidates(bundle, direction)
        if not candidates:
            return (
                None,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason="No institutional entry zone candidates found",
                ),
                [],
            )

        ranked = sorted(
            candidates,
            key=lambda zone: (zone.strength, -zone.distance_pips),
            reverse=True,
        )
        primary = ranked[0]
        max_distance = Decimal(str(self._config.entry.max_entry_distance_pips)) * self._config.pip_size_decimal
        if primary.distance_pips > max_distance / self._config.pip_size_decimal:
            return (
                None,
                GateResult(
                    passed=False,
                    error_code="INVALID_RISK",
                    blocking_reason=(
                        f"Nearest entry zone {primary.distance_pips} pips exceeds maximum "
                        f"{self._config.entry.max_entry_distance_pips}"
                    ),
                ),
                candidates,
            )

        entry_type = EntryType.ZONE
        if primary.engine_id == "market_premium_discount":
            entry_type = EntryType.OTE

        entry_price = primary.midpoint if self._config.entry.zone_midpoint_entry else None
        entry = EntrySpec(
            price=entry_price,
            zone_high=primary.zone_high,
            zone_low=primary.zone_low,
            entry_type=entry_type,
            source_engine=primary.engine_id,
            source_zone_id=primary.zone_id,
            distance_pips=primary.distance_pips,
        )
        return entry, GateResult(passed=True), candidates

    def entry_price(self, entry: EntrySpec) -> Decimal:
        if entry.price is not None:
            return entry.price
        if entry.zone_high is not None and entry.zone_low is not None:
            return (entry.zone_high + entry.zone_low) / 2
        raise ValueError("Entry specification has no price or zone bounds")

    def _collect_candidates(
        self,
        bundle: EvidenceBundle,
        direction: TradeDirection,
    ) -> list[CandidateZone]:
        candidates: list[CandidateZone] = []
        price = bundle.current_price

        if bundle.order_blocks is not None:
            target = (
                OrderBlockDirection.BULLISH
                if direction is TradeDirection.BUY
                else OrderBlockDirection.BEARISH
            )
            for block in bundle.order_blocks.fresh_blocks:
                if block.direction is not target:
                    continue
                if not self._zone_on_correct_side(block.low, block.high, price, direction):
                    continue
                midpoint = (block.high + block.low) / 2
                candidates.append(
                    CandidateZone(
                        zone_id=block.block_id,
                        engine_id="order_block",
                        zone_high=block.high,
                        zone_low=block.low,
                        midpoint=midpoint,
                        direction=direction,
                        quality=block.quality.value,
                        strength=block.strength,
                        distance_pips=self._distance_pips(price, midpoint),
                    ),
                )

        if bundle.fair_value_gaps is not None:
            target = (
                FairValueGapDirection.BULLISH
                if direction is TradeDirection.BUY
                else FairValueGapDirection.BEARISH
            )
            for gap in bundle.fair_value_gaps.open_gaps:
                if gap.direction is not target:
                    continue
                if gap.status not in {FairValueGapStatus.OPEN, FairValueGapStatus.PARTIAL}:
                    continue
                if not self._zone_on_correct_side(gap.low, gap.high, price, direction):
                    continue
                midpoint = (gap.high + gap.low) / 2
                candidates.append(
                    CandidateZone(
                        zone_id=gap.gap_id,
                        engine_id="fair_value_gap",
                        zone_high=gap.high,
                        zone_low=gap.low,
                        midpoint=midpoint,
                        direction=direction,
                        quality=gap.quality.value,
                        strength=gap.strength,
                        distance_pips=self._distance_pips(price, midpoint),
                    ),
                )

        if bundle.breaker_blocks is not None:
            target = "bullish" if direction is TradeDirection.BUY else "bearish"
            for breaker in bundle.breaker_blocks.confirmed_breakers:
                if breaker.direction.value != target:
                    continue
                if not self._zone_on_correct_side(breaker.low, breaker.high, price, direction):
                    continue
                midpoint = (breaker.high + breaker.low) / 2
                candidates.append(
                    CandidateZone(
                        zone_id=breaker.breaker_id,
                        engine_id="market_breaker",
                        zone_high=breaker.high,
                        zone_low=breaker.low,
                        midpoint=midpoint,
                        direction=direction,
                        quality=breaker.quality.value,
                        strength=breaker.strength,
                        distance_pips=self._distance_pips(price, midpoint),
                    ),
                )

        if bundle.mitigation_blocks is not None:
            target = (
                MitigationBlockDirection.BULLISH
                if direction is TradeDirection.BUY
                else MitigationBlockDirection.BEARISH
            )
            active = bundle.mitigation_blocks.fresh_blocks + bundle.mitigation_blocks.confirmed_blocks
            for block in active:
                if block.direction is not target:
                    continue
                if block.status not in {MitigationBlockStatus.FRESH, MitigationBlockStatus.CONFIRMED}:
                    continue
                if not self._zone_on_correct_side(block.low, block.high, price, direction):
                    continue
                midpoint = (block.high + block.low) / 2
                candidates.append(
                    CandidateZone(
                        zone_id=block.block_id,
                        engine_id="market_mitigation",
                        zone_high=block.high,
                        zone_low=block.low,
                        midpoint=midpoint,
                        direction=direction,
                        quality=block.quality.value,
                        strength=block.strength,
                        distance_pips=self._distance_pips(price, midpoint),
                    ),
                )

        if self._config.entry.prefer_ote and bundle.premium_discount is not None:
            ote = bundle.premium_discount.ote_zone
            if ote is not None and self._zone_on_correct_side(ote.low, ote.high, price, direction):
                midpoint = (ote.high + ote.low) / 2
                candidates.append(
                    CandidateZone(
                        zone_id=ote.ote_id,
                        engine_id="market_premium_discount",
                        zone_high=ote.high,
                        zone_low=ote.low,
                        midpoint=midpoint,
                        direction=direction,
                        quality=ote.quality.value,
                        strength=ote.strength,
                        distance_pips=self._distance_pips(price, midpoint),
                    ),
                )

        return candidates

    def _zone_on_correct_side(
        self,
        zone_low: Decimal,
        zone_high: Decimal,
        current_price: Decimal,
        direction: TradeDirection,
    ) -> bool:
        if direction is TradeDirection.BUY:
            return zone_high <= current_price
        return zone_low >= current_price

    def _distance_pips(self, current_price: Decimal, target: Decimal) -> Decimal:
        distance = abs(current_price - target)
        return (distance / self._config.pip_size_decimal).quantize(Decimal("0.1"))
