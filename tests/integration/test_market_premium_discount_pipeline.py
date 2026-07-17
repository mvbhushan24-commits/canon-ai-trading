"""Integration tests for Market Data → Structure → Liquidity → Order Block → FVG → Breaker → Mitigation → Premium / Discount pipeline."""

from backend.engines.market_breaker import BreakerBlockConfig, BreakerBlockEngine
from backend.engines.market_fvg import FairValueGapConfig, FairValueGapEngine
from backend.engines.market_liquidity import LiquidityEngine, MarketLiquidityConfig
from backend.engines.market_mitigation import MitigationBlockConfig, MitigationBlockEngine
from backend.engines.market_order_block import OrderBlockEngine, OrderBlockConfig
from backend.engines.market_order_block.schemas import OrderBlockStatus
from backend.engines.market_premium_discount import PremiumDiscountEngine
from backend.engines.market_premium_discount.schemas import PremiumDiscountContext, PremiumDiscountZone
from backend.engines.market_structure import MarketStructureConfig, MarketStructureEngine
from tests.unit.engines.conftest import build_bullish_structure_candles
from tests.unit.engines.premium_discount_conftest import premium_config


def _premium_config(**overrides):
    defaults = {
        "enabled": True,
        "timeframes": ["H1", "H4"],
        "min_candles": 10,
        "lookback": 30,
        "pip_size": 0.1,
        "min_range_size_pips": 5.0,
        "min_quality_score": 0.3,
        "min_swing_quality_score": 0.2,
        "mtf_alignment_min_score": 0.3,
    }
    defaults.update(overrides)
    return premium_config(**defaults)


def _mitigation_config(**overrides) -> MitigationBlockConfig:
    defaults = {
        "enabled": True,
        "timeframes": ["H1"],
        "min_candles": 10,
        "lookback": 30,
        "pip_size": 0.1,
        "min_displacement_pips": 5.0,
        "min_zone_size_pips": 1.5,
        "min_quality_score": 0.3,
    }
    defaults.update(overrides)
    return MitigationBlockConfig(**defaults)


def _breaker_config(**overrides) -> BreakerBlockConfig:
    defaults = {
        "enabled": True,
        "timeframes": ["H1"],
        "min_candles": 10,
        "lookback": 30,
        "pip_size": 0.1,
        "min_zone_size_pips": 1.0,
        "min_quality_score": 0.3,
        "min_bars_after_invalidation": 1,
        "max_bars_after_invalidation": 50,
    }
    defaults.update(overrides)
    return BreakerBlockConfig(**defaults)


def _fvg_config(**overrides) -> FairValueGapConfig:
    defaults = {
        "enabled": True,
        "timeframes": ["H1"],
        "min_candles": 10,
        "lookback": 30,
        "pip_size": 0.1,
        "min_gap_size_pips": 1.0,
        "min_quality_score": 0.3,
        "require_impulse_candle": False,
        "mtf_timeframe_hierarchy": ["H1"],
    }
    defaults.update(overrides)
    return FairValueGapConfig(**defaults)


def _run_upstream_chain(candles, timeframe: str = "H1"):
    structure = MarketStructureEngine(
        config=MarketStructureConfig(
            enabled=True,
            timeframes=[timeframe],
            swing_lookback=2,
            internal_swing_lookback=1,
            external_swing_lookback=2,
            min_confidence=0.3,
            min_candles=10,
        ),
    ).analyze(candles, timeframe=timeframe)
    liquidity = LiquidityEngine(
        config=MarketLiquidityConfig(
            enabled=True,
            timeframes=[timeframe],
            equal_high_tolerance=10.0,
            equal_low_tolerance=10.0,
            minimum_cluster_size=2,
            lookback=30,
            min_candles=10,
        ),
    ).analyze(candles, structure, timeframe=timeframe)
    order_blocks = OrderBlockEngine(
        config=OrderBlockConfig(
            enabled=True,
            timeframes=[timeframe],
            min_candles=10,
            lookback=30,
            min_displacement_pips=5.0,
            min_impulse_candles=2,
            pip_size=0.1,
            min_quality_score=0.4,
        ),
    ).analyze(candles, structure, liquidity, timeframe=timeframe)
    fvg_analysis = FairValueGapEngine(config=_fvg_config(timeframes=[timeframe])).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_block_state=order_blocks.state,
        timeframe=timeframe,
    )
    invalidated_blocks = [
        block for block in order_blocks.order_blocks if block.status is OrderBlockStatus.INVALIDATED
    ]
    breaker_analysis = BreakerBlockEngine(config=_breaker_config(timeframes=[timeframe])).analyze(
        candles,
        structure,
        invalidated_order_blocks=invalidated_blocks,
        liquidity_state=liquidity.state,
        fair_value_gap_state=fvg_analysis.state,
        timeframe=timeframe,
    )
    mitigation_analysis = MitigationBlockEngine(config=_mitigation_config(timeframes=[timeframe])).analyze(
        candles,
        structure,
        order_blocks=order_blocks.order_blocks,
        liquidity_state=liquidity.state,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        timeframe=timeframe,
    )
    return structure, liquidity, order_blocks, fvg_analysis, breaker_analysis, mitigation_analysis


def test_pipeline_full_chain_to_premium_discount() -> None:
    candles = build_bullish_structure_candles(30)
    structure, liquidity, order_blocks, fvg_analysis, breaker_analysis, mitigation_analysis = _run_upstream_chain(
        candles,
    )
    analysis = PremiumDiscountEngine(config=_premium_config()).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        mitigation_blocks=mitigation_analysis.mitigation_blocks,
        timeframe="H1",
    )

    assert analysis.symbol == structure.symbol
    assert analysis.timeframe == "H1"
    assert analysis.state.bar_count >= 10
    assert analysis.bias.value in {"premium", "discount", "equilibrium", "neutral", "undetermined"}


def test_pipeline_with_htf_alignment_context() -> None:
    candles = build_bullish_structure_candles(30)
    structure, liquidity, order_blocks, fvg_analysis, breaker_analysis, mitigation_analysis = _run_upstream_chain(
        candles,
    )
    htf_analysis = PremiumDiscountEngine(config=_premium_config(timeframes=["H1"])).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        mitigation_blocks=mitigation_analysis.mitigation_blocks,
        timeframe="H1",
    )
    htf_context = PremiumDiscountContext(
        timeframe="H4",
        dealing_range=htf_analysis.dealing_range,
        price_location=htf_analysis.price_location,
        premium_arrays=htf_analysis.premium_arrays,
        discount_arrays=htf_analysis.discount_arrays,
        equilibrium=htf_analysis.equilibrium.price,
    )
    ltf_analysis = PremiumDiscountEngine(config=_premium_config()).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        mitigation_blocks=mitigation_analysis.mitigation_blocks,
        htf_premium_discount_context=htf_context,
        timeframe="H1",
    )

    assert ltf_analysis.institutional_context is not None
    assert ltf_analysis.price_location in PremiumDiscountZone


def test_pipeline_preserves_symbol_and_timeframe() -> None:
    candles = build_bullish_structure_candles(30)
    structure, liquidity, order_blocks, fvg_analysis, breaker_analysis, mitigation_analysis = _run_upstream_chain(
        candles,
    )
    analysis = PremiumDiscountEngine(config=_premium_config()).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        mitigation_blocks=mitigation_analysis.mitigation_blocks,
        timeframe="H1",
    )

    assert analysis.symbol == candles[0].symbol
    assert analysis.timeframe == candles[0].timeframe


def test_pipeline_regression_prior_sprints_unchanged() -> None:
    candles = build_bullish_structure_candles(30)
    structure, liquidity, order_blocks, _, _, _ = _run_upstream_chain(candles)

    assert structure.symbol == candles[0].symbol
    assert liquidity.symbol == candles[0].symbol
    assert order_blocks.symbol == candles[0].symbol
