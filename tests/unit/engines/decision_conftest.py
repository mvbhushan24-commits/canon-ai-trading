"""Shared helpers for Market Decision Engine verification tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.engines.market_decision.config import (
    ConfidenceConfig,
    EntryConfig,
    EvidenceConfig,
    GatesConfig,
    MarketDecisionConfig,
    RiskConfig,
    ZonesGateConfig,
)
from backend.engines.market_decision.publisher import DecisionEventPublisher
from backend.engines.market_decision.schemas import NewsRestrictionResult
from backend.engines.market_liquidity.schemas import (
    LiquiditySide,
    LiquiditySweep,
    SweepDirection,
    SweepQuality,
)
from backend.engines.market_order_block.schemas import OrderBlockDirection
from backend.engines.market_premium_discount import PremiumDiscountEngine
from backend.engines.market_premium_discount.schemas import PremiumDiscountBias, PremiumDiscountZone
from backend.engines.market_sessions.schemas import (
    CalendarContext,
    FilterMode,
    LiquidityAvailability,
    MarketAvailability,
    MarketSessionsState,
    SessionAnalysis,
    SessionPhase,
    SessionQualityTier,
    TimeOfDayFilter,
    TradingSessionId,
    VolatilityProfile,
)
from backend.engines.market_structure.schemas import TrendDirection
from tests.integration.test_market_premium_discount_pipeline import _premium_config, _run_upstream_chain
from tests.unit.engines.conftest import build_bullish_structure_candles
from tests.unit.engines.market_sessions_conftest import london_open_timestamp


def decision_config(**overrides) -> MarketDecisionConfig:
    """Build a test MarketDecisionConfig with engine enabled."""
    defaults = {
        "enabled": True,
        "symbol": "XAUUSD",
        "pip_size": 0.1,
        "evidence": EvidenceConfig(min_required_engines=5),
    }
    defaults.update(overrides)
    return MarketDecisionConfig(**defaults)


def relaxed_decision_config(**overrides) -> MarketDecisionConfig:
    """Config relaxed enough for synthetic BUY/SELL pipeline success tests."""
    defaults = {
        "enabled": True,
        "confidence": ConfidenceConfig(min_confidence=30, min_directional_weight=0.15),
        "risk": RiskConfig(min_confidence=30),
        "gates": GatesGateConfig(),
        "entry": EntryConfig(max_entry_distance_pips=35.0),
    }
    defaults.update(overrides)
    return decision_config(**defaults)


def GatesGateConfig() -> GatesConfig:
    return GatesConfig(zones=ZonesGateConfig(min_zone_confluence=1))


def sample_session_analysis(
    *,
    timestamp_utc: datetime | None = None,
    is_allowed: bool = True,
) -> SessionAnalysis:
    """Synthetic session envelope for decision gate tests."""
    ts = timestamp_utc or london_open_timestamp()
    return SessionAnalysis(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp_utc=ts,
        broker_timezone="UTC",
        market_availability=MarketAvailability.OPEN,
        active_sessions=[],
        primary_session=TradingSessionId.LONDON,
        session_phase=SessionPhase.OPENING,
        kill_zones=[],
        active_kill_zones=[],
        overlaps=[],
        next_transition=None,
        recent_transitions=[],
        daily_open=None,
        weekly_open=None,
        monthly_open=None,
        session_extremes=[],
        opening_range=None,
        initial_balance=None,
        time_of_day_filter=TimeOfDayFilter(
            filter_mode=FilterMode.KILL_ZONE_ONLY,
            is_allowed=is_allowed,
            blocked_reasons=["Outside kill zone"] if not is_allowed else [],
        ),
        calendar_context=CalendarContext(
            is_weekend=False,
            is_holiday=False,
            is_dst_transition=False,
            dst_offset_minutes=0,
            trading_day_id="2026-01-14",
            week_id="2026-W03",
            month_id="2026-01",
        ),
        volatility_profile=VolatilityProfile.MODERATE,
        liquidity_availability=LiquidityAvailability.MODERATE,
        quality=SessionQualityTier.HIGH,
        confidence=Decimal("0.9"),
        strength=Decimal("0.85"),
        state=MarketSessionsState(bar_count=20),
        events=[],
        evidence=["synthetic-session"],
    )


def _boost_confidence(analysis, **updates):
    base = {"confidence": Decimal("0.95")}
    base.update(updates)
    return analysis.model_copy(update=base)


def build_bullish_upstream_evidence(
    *,
    timestamp_utc: datetime | None = None,
    current_price: Decimal = Decimal("2321"),
):
    """Return upstream envelopes aligned for institutional BUY synthesis."""
    ts = timestamp_utc or london_open_timestamp()
    candles = build_bullish_structure_candles(30)
    structure, liquidity, order_blocks, fvg, breaker, mitigation = _run_upstream_chain(candles)
    premium_discount = PremiumDiscountEngine(config=_premium_config()).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg.state,
        breaker_blocks=breaker.breaker_blocks,
        mitigation_blocks=mitigation.mitigation_blocks,
        timeframe="H1",
    )

    bullish_sweep = LiquiditySweep(
        direction=SweepDirection.BULLISH,
        swept_level=Decimal("2300"),
        sweep_price=Decimal("2298"),
        reclaim_price=Decimal("2305"),
        timestamp_utc=ts,
        bar_index=20,
        timeframe="H1",
        quality=SweepQuality.STRONG,
    )
    liquidity = _boost_confidence(
        liquidity,
        sweeps=[bullish_sweep],
        bias=LiquiditySide.SELL_SIDE,
    )
    premium_discount = premium_discount.model_copy(
        update={
            "price_location": PremiumDiscountZone.DISCOUNT,
            "bias": PremiumDiscountBias.DISCOUNT,
            "confidence": Decimal("0.95"),
            "strength": Decimal("0.9"),
        },
    )
    structure = _boost_confidence(structure)
    close_blocks = [block for block in order_blocks.fresh_blocks if block.low >= Decimal("2310")]
    order_blocks = _boost_confidence(order_blocks, fresh_blocks=close_blocks)
    fvg = _boost_confidence(fvg)
    breaker = _boost_confidence(breaker)
    mitigation = _boost_confidence(mitigation)
    sessions = sample_session_analysis(timestamp_utc=ts)

    return {
        "timestamp_utc": ts,
        "current_price": current_price,
        "spread": Decimal("0.2"),
        "structure": structure,
        "liquidity": liquidity,
        "order_blocks": order_blocks,
        "fair_value_gaps": fvg,
        "breaker_blocks": breaker,
        "mitigation_blocks": mitigation,
        "premium_discount": premium_discount,
        "sessions": sessions,
    }


def build_bearish_upstream_evidence(
    *,
    timestamp_utc: datetime | None = None,
    current_price: Decimal = Decimal("2325"),
):
    """Return upstream envelopes aligned for institutional SELL synthesis."""
    evidence = build_bullish_upstream_evidence(
        timestamp_utc=timestamp_utc,
        current_price=current_price,
    )
    ts = evidence["timestamp_utc"]

    structure = evidence["structure"].model_copy(
        update={"current_trend": TrendDirection.BEARISH, "confidence": Decimal("0.95")},
    )
    bearish_sweep = LiquiditySweep(
        direction=SweepDirection.BEARISH,
        swept_level=Decimal("2340"),
        sweep_price=Decimal("2342"),
        reclaim_price=Decimal("2335"),
        timestamp_utc=ts,
        bar_index=20,
        timeframe="H1",
        quality=SweepQuality.STRONG,
    )
    liquidity = evidence["liquidity"].model_copy(
        update={
            "sweeps": [bearish_sweep],
            "bias": LiquiditySide.BUY_SIDE,
            "confidence": Decimal("0.95"),
        },
    )
    premium_discount = evidence["premium_discount"].model_copy(
        update={
            "price_location": PremiumDiscountZone.PREMIUM,
            "bias": PremiumDiscountBias.PREMIUM,
            "confidence": Decimal("0.95"),
            "strength": Decimal("0.9"),
        },
    )
    bearish_blocks = [
        block.model_copy(
            update={
                "direction": OrderBlockDirection.BEARISH,
                "high": Decimal("2330"),
                "low": Decimal("2326"),
            },
        )
        for block in evidence["order_blocks"].fresh_blocks[:1]
    ]
    order_blocks = evidence["order_blocks"].model_copy(update={"fresh_blocks": bearish_blocks})

    from backend.engines.market_fvg.schemas import FairValueGapBias, FairValueGapDirection

    fvg = evidence["fair_value_gaps"].model_copy(update={"bias": FairValueGapBias.BEARISH})
    if fvg.open_gaps:
        gap = fvg.open_gaps[0].model_copy(
            update={
                "direction": FairValueGapDirection.BEARISH,
                "high": Decimal("2332"),
                "low": Decimal("2328"),
            },
        )
        fvg = fvg.model_copy(update={"open_gaps": [gap]})

    breaker = evidence["breaker_blocks"]
    if breaker.confirmed_breakers:
        block = breaker.confirmed_breakers[0]
        breaker = breaker.model_copy(
            update={
                "confirmed_breakers": [
                    block.model_copy(
                        update={
                            "high": Decimal("2334"),
                            "low": Decimal("2330"),
                        },
                    ),
                ],
            },
        )

    return {
        **evidence,
        "structure": structure,
        "liquidity": liquidity,
        "order_blocks": order_blocks,
        "fair_value_gaps": fvg,
        "breaker_blocks": breaker,
        "premium_discount": premium_discount,
        "current_price": current_price,
    }


def blocking_news_hook(symbol: str, timestamp_utc) -> NewsRestrictionResult:
    return NewsRestrictionResult(blocked=True, reason="High-impact news window")


@pytest.fixture
def decision_config_fixture() -> MarketDecisionConfig:
    return decision_config()


@pytest.fixture
def relaxed_decision_config_fixture() -> MarketDecisionConfig:
    return relaxed_decision_config()


@pytest.fixture
def decision_publisher() -> DecisionEventPublisher:
    return DecisionEventPublisher()


@pytest.fixture
def decision_timestamp() -> datetime:
    return london_open_timestamp()


@pytest.fixture
def bullish_evidence() -> dict:
    return build_bullish_upstream_evidence()


@pytest.fixture
def bearish_evidence() -> dict:
    return build_bearish_upstream_evidence()
