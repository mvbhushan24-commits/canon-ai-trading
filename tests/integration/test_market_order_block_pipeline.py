"""Integration tests for Market Data → Structure → Liquidity → Order Block pipeline."""

from backend.engines.market_liquidity import LiquidityEngine, MarketLiquidityConfig
from backend.engines.market_order_block import OrderBlockEngine, OrderBlockConfig
from backend.engines.market_structure import MarketStructureConfig, MarketStructureEngine
from tests.unit.engines.conftest import build_bullish_structure_candles


def test_pipeline_candles_structure_liquidity_to_order_blocks() -> None:
    candles = build_bullish_structure_candles(30)
    structure_config = MarketStructureConfig(
        enabled=True,
        timeframes=["H1"],
        swing_lookback=2,
        internal_swing_lookback=1,
        external_swing_lookback=2,
        min_confidence=0.3,
        min_candles=10,
    )
    liquidity_config = MarketLiquidityConfig(
        enabled=True,
        timeframes=["H1"],
        equal_high_tolerance=10.0,
        equal_low_tolerance=10.0,
        minimum_cluster_size=2,
        lookback=30,
        min_candles=10,
    )
    order_block_config = OrderBlockConfig(
        enabled=True,
        timeframes=["H1"],
        min_candles=10,
        lookback=30,
        min_displacement_pips=5.0,
        min_impulse_candles=2,
        pip_size=0.1,
        min_quality_score=0.4,
    )

    structure = MarketStructureEngine(config=structure_config).analyze(candles, timeframe="H1")
    liquidity = LiquidityEngine(config=liquidity_config).analyze(candles, structure, timeframe="H1")
    order_blocks = OrderBlockEngine(config=order_block_config).analyze(
        candles,
        structure,
        liquidity,
        timeframe="H1",
    )

    assert order_blocks.symbol == structure.symbol
    assert order_blocks.timeframe == "H1"
    assert len(order_blocks.order_blocks) > 0
    assert order_blocks.state.bar_count >= 10


def test_pipeline_preserves_symbol_and_timeframe() -> None:
    candles = build_bullish_structure_candles(30)
    structure = MarketStructureEngine(
        config=MarketStructureConfig(
            enabled=True,
            timeframes=["H1"],
            swing_lookback=2,
            internal_swing_lookback=1,
            external_swing_lookback=2,
            min_candles=10,
        ),
    ).analyze(candles, timeframe="H1")
    liquidity = LiquidityEngine(
        config=MarketLiquidityConfig(enabled=True, timeframes=["H1"], min_candles=10),
    ).analyze(candles, structure, timeframe="H1")
    analysis = OrderBlockEngine(
        config=OrderBlockConfig(enabled=True, timeframes=["H1"], min_candles=10),
    ).analyze(candles, structure, liquidity, timeframe="H1")

    assert analysis.symbol == candles[0].symbol
    assert analysis.timeframe == candles[0].timeframe
