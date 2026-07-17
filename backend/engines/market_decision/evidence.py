"""Evidence collection and normalization for the Market Decision Engine."""

from datetime import datetime
from decimal import Decimal

from backend.engines.market_breaker import BreakerBlockAnalysis
from backend.engines.market_decision.config import MarketDecisionConfig
from backend.engines.market_decision.schemas import (
    DirectionBias,
    EvidenceAvailability,
    EvidenceBundle,
    NormalizedEvidence,
    PriceLevel,
    TradeDirection,
)
from backend.engines.market_fvg import FairValueGapAnalysis
from backend.engines.market_liquidity import LiquidityAnalysis
from backend.engines.market_mitigation import MitigationBlockAnalysis
from backend.engines.market_order_block import OrderBlockAnalysis
from backend.engines.market_premium_discount import PremiumDiscountAnalysis
from backend.engines.market_sessions import SessionAnalysis
from backend.engines.market_structure import MarketStructure


class EvidenceCollector:
    """Assemble upstream envelopes into a unified evidence bundle."""

    def __init__(self, config: MarketDecisionConfig) -> None:
        self._config = config

    def collect(
        self,
        symbol: str,
        timestamp_utc: datetime,
        current_price: Decimal,
        *,
        spread: Decimal | None = None,
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
        order_blocks: OrderBlockAnalysis | None = None,
        fair_value_gaps: FairValueGapAnalysis | None = None,
        breaker_blocks: BreakerBlockAnalysis | None = None,
        mitigation_blocks: MitigationBlockAnalysis | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        sessions: SessionAnalysis | None = None,
    ) -> EvidenceBundle:
        availability = self._build_availability(
            timestamp_utc,
            structure=structure,
            liquidity=liquidity,
            order_blocks=order_blocks,
            fair_value_gaps=fair_value_gaps,
            breaker_blocks=breaker_blocks,
            mitigation_blocks=mitigation_blocks,
            premium_discount=premium_discount,
            sessions=sessions,
        )
        return EvidenceBundle(
            symbol=symbol,
            timestamp_utc=timestamp_utc,
            current_price=current_price,
            spread=spread,
            structure=structure if availability.structure_available else None,
            liquidity=liquidity if availability.liquidity_available else None,
            order_blocks=order_blocks if availability.order_block_available else None,
            fair_value_gaps=fair_value_gaps if availability.fvg_available else None,
            breaker_blocks=breaker_blocks if availability.breaker_available else None,
            mitigation_blocks=mitigation_blocks if availability.mitigation_available else None,
            premium_discount=premium_discount if availability.premium_discount_available else None,
            sessions=sessions if availability.sessions_available else None,
            availability=availability,
        )

    def _build_availability(
        self,
        reference_time: datetime,
        *,
        structure: MarketStructure | None,
        liquidity: LiquidityAnalysis | None,
        order_blocks: OrderBlockAnalysis | None,
        fair_value_gaps: FairValueGapAnalysis | None,
        breaker_blocks: BreakerBlockAnalysis | None,
        mitigation_blocks: MitigationBlockAnalysis | None,
        premium_discount: PremiumDiscountAnalysis | None,
        sessions: SessionAnalysis | None,
    ) -> EvidenceAvailability:
        ages = self._config.evidence.max_evidence_age_seconds
        availability = EvidenceAvailability()

        checks = [
            ("structure_available", "structure_stale", structure, ages.market_structure),
            ("liquidity_available", "liquidity_stale", liquidity, ages.market_liquidity),
            ("order_block_available", "order_block_stale", order_blocks, ages.order_block),
            ("fvg_available", "fvg_stale", fair_value_gaps, ages.fair_value_gap),
            ("breaker_available", "breaker_stale", breaker_blocks, ages.market_breaker),
            ("mitigation_available", "mitigation_stale", mitigation_blocks, ages.market_mitigation),
            (
                "premium_discount_available",
                "premium_discount_stale",
                premium_discount,
                ages.market_premium_discount,
            ),
            ("sessions_available", "sessions_stale", sessions, ages.market_sessions),
        ]

        for available_attr, stale_attr, envelope, max_age in checks:
            if envelope is None:
                continue
            setattr(availability, available_attr, True)
            envelope_time = getattr(envelope, "timestamp_utc", None)
            if envelope_time is not None:
                age_seconds = abs((reference_time - envelope_time).total_seconds())
                if age_seconds > max_age:
                    setattr(availability, stale_attr, True)

        return availability


class EvidenceNormalizer:
    """Map per-engine outputs to normalized evidence records."""

    def normalize(self, bundle: EvidenceBundle) -> list[NormalizedEvidence]:
        records: list[NormalizedEvidence] = []
        availability = bundle.availability

        if bundle.structure is not None:
            records.append(self._normalize_structure(bundle.structure, availability.structure_stale))
        if bundle.liquidity is not None:
            records.append(self._normalize_liquidity(bundle.liquidity, availability.liquidity_stale))
        if bundle.order_blocks is not None:
            records.append(self._normalize_order_blocks(bundle.order_blocks, availability.order_block_stale))
        if bundle.fair_value_gaps is not None:
            records.append(self._normalize_fvg(bundle.fair_value_gaps, availability.fvg_stale))
        if bundle.breaker_blocks is not None:
            records.append(self._normalize_breaker(bundle.breaker_blocks, availability.breaker_stale))
        if bundle.mitigation_blocks is not None:
            records.append(
                self._normalize_mitigation(bundle.mitigation_blocks, availability.mitigation_stale),
            )
        if bundle.premium_discount is not None:
            records.append(
                self._normalize_premium_discount(
                    bundle.premium_discount,
                    availability.premium_discount_stale,
                ),
            )
        if bundle.sessions is not None:
            records.append(self._normalize_sessions(bundle.sessions, availability.sessions_stale))

        return records

    def _normalize_structure(
        self,
        structure: MarketStructure,
        stale: bool,
    ) -> NormalizedEvidence:
        trend = structure.current_trend
        if trend.value == "bullish":
            bias = DirectionBias.BULLISH
        elif trend.value == "bearish":
            bias = DirectionBias.BEARISH
        elif trend.value == "range":
            bias = DirectionBias.NEUTRAL
        else:
            bias = DirectionBias.UNDETERMINED

        invalidation = None
        if structure.swing_lows and bias is DirectionBias.BULLISH:
            invalidation = structure.swing_lows[-1].price
        elif structure.swing_highs and bias is DirectionBias.BEARISH:
            invalidation = structure.swing_highs[-1].price

        levels: list[PriceLevel] = []
        for swing in structure.swing_highs[-3:]:
            levels.append(
                PriceLevel(
                    level_id=f"swing-high-{swing.bar_index}",
                    price=swing.price,
                    source_engine="market_structure",
                    label=swing.label.value,
                ),
            )
        for swing in structure.swing_lows[-3:]:
            levels.append(
                PriceLevel(
                    level_id=f"swing-low-{swing.bar_index}",
                    price=swing.price,
                    source_engine="market_structure",
                    label=swing.label.value,
                ),
            )

        confidence = min(max(structure.confidence, Decimal("0")), Decimal("1"))
        strength = confidence
        if structure.bos_events:
            strength = min(strength + Decimal("0.1"), Decimal("1"))

        return NormalizedEvidence(
            engine_id="market_structure",
            direction_bias=bias,
            confidence=confidence,
            strength=strength,
            quality_tier="high" if confidence >= Decimal("0.75") else "medium",
            key_levels=levels,
            invalidation_level=invalidation,
            evidence=structure.evidence[:5],
            available=True,
            stale=stale,
        )

    def _normalize_liquidity(
        self,
        liquidity: LiquidityAnalysis,
        stale: bool,
    ) -> NormalizedEvidence:
        side = liquidity.bias
        if side.value == "sell_side":
            bias = DirectionBias.BULLISH
        elif side.value == "buy_side":
            bias = DirectionBias.BEARISH
        elif side.value == "balanced":
            bias = DirectionBias.NEUTRAL
        else:
            bias = DirectionBias.UNDETERMINED

        levels = [
            PriceLevel(
                level_id=zone.zone_id,
                price=zone.anchor_price,
                zone_high=zone.upper_bound,
                zone_low=zone.lower_bound,
                source_engine="market_liquidity",
                label=zone.side.value,
            )
            for zone in liquidity.zones[:5]
        ]

        invalidation = liquidity.sweeps[-1].swept_level if liquidity.sweeps else None
        confidence = min(max(liquidity.confidence, Decimal("0")), Decimal("1"))
        strength = confidence
        if liquidity.sweeps:
            strength = min(strength + Decimal("0.1"), Decimal("1"))

        return NormalizedEvidence(
            engine_id="market_liquidity",
            direction_bias=bias,
            confidence=confidence,
            strength=strength,
            quality_tier="medium",
            key_levels=levels,
            invalidation_level=invalidation,
            evidence=liquidity.evidence[:5],
            available=True,
            stale=stale,
        )

    def _normalize_order_blocks(
        self,
        analysis: OrderBlockAnalysis,
        stale: bool,
    ) -> NormalizedEvidence:
        bias_value = analysis.bias.value
        bias = {
            "bullish": DirectionBias.BULLISH,
            "bearish": DirectionBias.BEARISH,
            "neutral": DirectionBias.NEUTRAL,
        }.get(bias_value, DirectionBias.UNDETERMINED)

        levels = [
            PriceLevel(
                level_id=block.block_id,
                price=(block.high + block.low) / 2,
                zone_high=block.high,
                zone_low=block.low,
                source_engine="order_block",
                label=block.direction.value,
            )
            for block in analysis.fresh_blocks[:5]
        ]
        invalidation = analysis.fresh_blocks[0].low if analysis.fresh_blocks else None
        confidence = min(max(analysis.confidence, Decimal("0")), Decimal("1"))

        return NormalizedEvidence(
            engine_id="order_block",
            direction_bias=bias,
            confidence=confidence,
            strength=analysis.fresh_blocks[0].strength if analysis.fresh_blocks else confidence,
            quality_tier=analysis.fresh_blocks[0].quality.value if analysis.fresh_blocks else None,
            key_levels=levels,
            invalidation_level=invalidation,
            evidence=analysis.evidence[:5],
            available=True,
            stale=stale,
        )

    def _normalize_fvg(
        self,
        analysis: FairValueGapAnalysis,
        stale: bool,
    ) -> NormalizedEvidence:
        bias_value = analysis.bias.value
        bias = {
            "bullish": DirectionBias.BULLISH,
            "bearish": DirectionBias.BEARISH,
            "neutral": DirectionBias.NEUTRAL,
        }.get(bias_value, DirectionBias.UNDETERMINED)

        levels = [
            PriceLevel(
                level_id=gap.gap_id,
                price=gap.ce_price,
                zone_high=gap.high,
                zone_low=gap.low,
                source_engine="fair_value_gap",
                label=gap.direction.value,
            )
            for gap in analysis.open_gaps[:5]
        ]
        invalidation = analysis.open_gaps[0].low if analysis.open_gaps else None
        confidence = min(max(analysis.confidence, Decimal("0")), Decimal("1"))

        return NormalizedEvidence(
            engine_id="fair_value_gap",
            direction_bias=bias,
            confidence=confidence,
            strength=analysis.open_gaps[0].strength if analysis.open_gaps else confidence,
            quality_tier=analysis.open_gaps[0].quality.value if analysis.open_gaps else None,
            key_levels=levels,
            invalidation_level=invalidation,
            evidence=analysis.evidence[:5],
            available=True,
            stale=stale,
        )

    def _normalize_breaker(
        self,
        analysis: BreakerBlockAnalysis,
        stale: bool,
    ) -> NormalizedEvidence:
        bias_value = analysis.bias.value
        bias = {
            "bullish": DirectionBias.BULLISH,
            "bearish": DirectionBias.BEARISH,
            "neutral": DirectionBias.NEUTRAL,
        }.get(bias_value, DirectionBias.UNDETERMINED)

        levels = [
            PriceLevel(
                level_id=breaker.breaker_id,
                price=(breaker.high + breaker.low) / 2,
                zone_high=breaker.high,
                zone_low=breaker.low,
                source_engine="market_breaker",
                label=breaker.direction.value,
            )
            for breaker in analysis.confirmed_breakers[:5]
        ]
        invalidation = analysis.confirmed_breakers[0].low if analysis.confirmed_breakers else None
        confidence = min(max(analysis.confidence, Decimal("0")), Decimal("1"))

        return NormalizedEvidence(
            engine_id="market_breaker",
            direction_bias=bias,
            confidence=confidence,
            strength=analysis.confirmed_breakers[0].strength if analysis.confirmed_breakers else confidence,
            quality_tier=analysis.confirmed_breakers[0].quality.value if analysis.confirmed_breakers else None,
            key_levels=levels,
            invalidation_level=invalidation,
            evidence=analysis.evidence[:5],
            available=True,
            stale=stale,
        )

    def _normalize_mitigation(
        self,
        analysis: MitigationBlockAnalysis,
        stale: bool,
    ) -> NormalizedEvidence:
        bias_value = analysis.bias.value
        bias = {
            "bullish": DirectionBias.BULLISH,
            "bearish": DirectionBias.BEARISH,
            "neutral": DirectionBias.NEUTRAL,
        }.get(bias_value, DirectionBias.UNDETERMINED)

        active = analysis.fresh_blocks + analysis.confirmed_blocks
        levels = [
            PriceLevel(
                level_id=block.block_id,
                price=(block.high + block.low) / 2,
                zone_high=block.high,
                zone_low=block.low,
                source_engine="market_mitigation",
                label=block.direction.value,
            )
            for block in active[:5]
        ]
        invalidation = active[0].low if active else None
        confidence = min(max(analysis.confidence, Decimal("0")), Decimal("1"))

        return NormalizedEvidence(
            engine_id="market_mitigation",
            direction_bias=bias,
            confidence=confidence,
            strength=active[0].strength if active else confidence,
            quality_tier=active[0].quality.value if active else None,
            key_levels=levels,
            invalidation_level=invalidation,
            evidence=analysis.evidence[:5],
            available=True,
            stale=stale,
        )

    def _normalize_premium_discount(
        self,
        analysis: PremiumDiscountAnalysis,
        stale: bool,
    ) -> NormalizedEvidence:
        bias_value = analysis.bias.value
        bias = {
            "bullish": DirectionBias.BULLISH,
            "bearish": DirectionBias.BEARISH,
            "neutral": DirectionBias.NEUTRAL,
        }.get(bias_value, DirectionBias.UNDETERMINED)

        levels: list[PriceLevel] = []
        if analysis.ote_zone is not None:
            levels.append(
                PriceLevel(
                    level_id=analysis.ote_zone.ote_id,
                    price=(analysis.ote_zone.high + analysis.ote_zone.low) / 2,
                    zone_high=analysis.ote_zone.high,
                    zone_low=analysis.ote_zone.low,
                    source_engine="market_premium_discount",
                    label="ote",
                ),
            )

        confidence = min(max(analysis.confidence, Decimal("0")), Decimal("1"))
        return NormalizedEvidence(
            engine_id="market_premium_discount",
            direction_bias=bias,
            confidence=confidence,
            strength=min(max(analysis.strength, Decimal("0")), Decimal("1")),
            quality_tier=analysis.quality.value,
            key_levels=levels,
            invalidation_level=analysis.equilibrium.price,
            evidence=analysis.evidence[:5],
            available=True,
            stale=stale,
        )

    def _normalize_sessions(
        self,
        analysis: SessionAnalysis,
        stale: bool,
    ) -> NormalizedEvidence:
        if analysis.time_of_day_filter.is_allowed and analysis.active_kill_zones:
            bias = DirectionBias.BULLISH if analysis.primary_session else DirectionBias.NEUTRAL
        elif not analysis.time_of_day_filter.is_allowed:
            bias = DirectionBias.UNDETERMINED
        else:
            bias = DirectionBias.NEUTRAL

        confidence = min(max(analysis.confidence, Decimal("0")), Decimal("1"))
        return NormalizedEvidence(
            engine_id="market_sessions",
            direction_bias=bias,
            confidence=confidence,
            strength=min(max(analysis.strength, Decimal("0")), Decimal("1")),
            quality_tier=analysis.quality.value,
            key_levels=[],
            invalidation_level=None,
            evidence=analysis.evidence[:5],
            available=True,
            stale=stale,
        )


def resolve_provisional_direction(
    bullish_weight: Decimal,
    bearish_weight: Decimal,
    min_directional_weight: float,
) -> TradeDirection:
    """Resolve provisional trade direction from weighted evidence."""
    threshold = Decimal(str(min_directional_weight))
    if bullish_weight > bearish_weight and bullish_weight >= threshold:
        return TradeDirection.BUY
    if bearish_weight > bullish_weight and bearish_weight >= threshold:
        return TradeDirection.SELL
    return TradeDirection.NONE
