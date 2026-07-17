"""Integration tests for full upstream pipeline through Market Sessions Engine."""

from backend.engines.market_breaker import BreakerBlockConfig, BreakerBlockEngine
from backend.engines.market_fvg import FairValueGapConfig, FairValueGapEngine
from backend.engines.market_liquidity import LiquidityEngine, MarketLiquidityConfig
from backend.engines.market_mitigation import MitigationBlockConfig, MitigationBlockEngine
from backend.engines.market_order_block import OrderBlockEngine, OrderBlockConfig
from backend.engines.market_order_block.schemas import OrderBlockStatus
from backend.engines.market_premium_discount import PremiumDiscountEngine
from backend.engines.market_sessions import MarketSessionsEngine
from backend.engines.market_structure import MarketStructureConfig, MarketStructureEngine
from tests.unit.engines.conftest import build_bullish_structure_candles
from tests.unit.engines.market_sessions_conftest import london_open_timestamp, market_sessions_config
from tests.unit.engines.premium_discount_conftest import premium_config


def _sessions_config(**overrides):
    defaults = {
        "min_candles": 10,
        "lookback": 30,
        "timeframes": ["H1"],
    }
    defaults.update(overrides)
    return market_sessions_config(**defaults)


def _run_full_upstream_chain(candles, timeframe: str = "H1"):
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
    fvg_analysis = FairValueGapEngine(
        config=FairValueGapConfig(
            enabled=True,
            timeframes=[timeframe],
            min_candles=10,
            lookback=30,
            pip_size=0.1,
            min_gap_size_pips=1.0,
            min_quality_score=0.3,
            require_impulse_candle=False,
            mtf_timeframe_hierarchy=[timeframe],
        ),
    ).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_block_state=order_blocks.state,
        timeframe=timeframe,
    )
    invalidated_blocks = [
        block for block in order_blocks.order_blocks if block.status is OrderBlockStatus.INVALIDATED
    ]
    breaker_analysis = BreakerBlockEngine(
        config=BreakerBlockConfig(
            enabled=True,
            timeframes=[timeframe],
            min_candles=10,
            lookback=30,
            pip_size=0.1,
            min_zone_size_pips=1.0,
            min_quality_score=0.3,
        ),
    ).analyze(
        candles,
        structure,
        invalidated_order_blocks=invalidated_blocks,
        liquidity_state=liquidity.state,
        fair_value_gap_state=fvg_analysis.state,
        timeframe=timeframe,
    )
    mitigation_analysis = MitigationBlockEngine(
        config=MitigationBlockConfig(
            enabled=True,
            timeframes=[timeframe],
            min_candles=10,
            lookback=30,
            pip_size=0.1,
            min_displacement_pips=5.0,
            min_zone_size_pips=1.5,
            min_quality_score=0.3,
        ),
    ).analyze(
        candles,
        structure,
        order_blocks=order_blocks.order_blocks,
        liquidity_state=liquidity.state,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        timeframe=timeframe,
    )
    premium_discount = PremiumDiscountEngine(config=premium_config(timeframes=[timeframe])).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        mitigation_blocks=mitigation_analysis.mitigation_blocks,
        timeframe=timeframe,
    )
    return (
        structure,
        liquidity,
        order_blocks,
        fvg_analysis,
        breaker_analysis,
        mitigation_analysis,
        premium_discount,
    )


def test_pipeline_full_chain_to_market_sessions() -> None:
    candles = build_bullish_structure_candles(30)
    (
        structure,
        liquidity,
        order_blocks,
        fvg_analysis,
        breaker_analysis,
        mitigation_analysis,
        premium_discount,
    ) = _run_full_upstream_chain(candles)
    engine = MarketSessionsEngine(config=_sessions_config())
    analysis = engine.analyze(
        candles,
        timestamp_utc=london_open_timestamp(),
        structure=structure,
        liquidity_state=liquidity.state,
        premium_discount=premium_discount,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        mitigation_blocks=mitigation_analysis.mitigation_blocks,
        timeframe="H1",
    )

    assert analysis.symbol == structure.symbol
    assert analysis.timeframe == "H1"
    assert analysis.state.bar_count >= 10
    assert analysis.quality.value in {"high", "medium", "low"}


def test_pipeline_without_upstream_context() -> None:
    candles = build_bullish_structure_candles(30)
    engine = MarketSessionsEngine(config=_sessions_config())
    analysis = engine.analyze(
        candles,
        timestamp_utc=london_open_timestamp(),
        timeframe="H1",
    )

    assert analysis.symbol == candles[0].symbol
    assert any("Market structure unavailable" in item for item in analysis.evidence)


def test_pipeline_preserves_symbol_and_timeframe() -> None:
    candles = build_bullish_structure_candles(30)
    structure, liquidity, order_blocks, fvg_analysis, breaker_analysis, mitigation_analysis, premium_discount = (
        _run_full_upstream_chain(candles)
    )
    engine = MarketSessionsEngine(config=_sessions_config())
    analysis = engine.analyze(
        candles,
        timestamp_utc=london_open_timestamp(),
        structure=structure,
        liquidity_state=liquidity.state,
        premium_discount=premium_discount,
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
    structure, liquidity, order_blocks, _, _, _, premium_discount = _run_full_upstream_chain(candles)

    assert structure.symbol == candles[0].symbol
    assert liquidity.symbol == candles[0].symbol
    assert order_blocks.symbol == candles[0].symbol
    assert premium_discount.symbol == candles[0].symbol
