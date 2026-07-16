"""Integration tests for Market Data → Market Structure → Liquidity pipeline."""

from backend.engines.market_liquidity import LiquidityEngine, MarketLiquidityConfig
from backend.engines.market_structure import MarketStructureConfig, MarketStructureEngine
from tests.unit.engines.conftest import build_bullish_structure_candles


def test_pipeline_candles_structure_to_liquidity() -> None:
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
        equal_high_tolerance=5.0,
        equal_low_tolerance=5.0,
        minimum_cluster_size=2,
        lookback=30,
        min_candles=10,
    )

    structure = MarketStructureEngine(config=structure_config).analyze(candles, timeframe="H1")
    liquidity = LiquidityEngine(config=liquidity_config).analyze(candles, structure, timeframe="H1")

    assert liquidity.symbol == structure.symbol
    assert liquidity.timeframe == "H1"
    assert len(liquidity.external_liquidity) > 0


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

    assert liquidity.symbol == candles[0].symbol
    assert liquidity.timeframe == candles[0].timeframe
