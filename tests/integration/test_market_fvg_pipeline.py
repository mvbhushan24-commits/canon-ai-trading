"""Integration tests for Market Data → Structure → Liquidity → Order Block → FVG pipeline."""

from decimal import Decimal

from backend.engines.market_fvg import FairValueGapConfig, FairValueGapEngine
from backend.engines.market_liquidity import LiquidityEngine, MarketLiquidityConfig
from backend.engines.market_order_block import OrderBlockEngine, OrderBlockConfig
from backend.engines.market_structure import MarketStructureConfig, MarketStructureEngine
from tests.unit.engines.conftest import build_bullish_structure_candles
from tests.unit.engines.fvg_conftest import build_bullish_fvg_candles
from tests.unit.engines.liquidity_conftest import build_sample_structure


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


def test_pipeline_full_chain_to_fair_value_gaps() -> None:
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
    fvg_analysis = FairValueGapEngine(config=_fvg_config()).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_block_state=order_blocks.state,
        timeframe="H1",
    )

    assert fvg_analysis.symbol == structure.symbol
    assert fvg_analysis.timeframe == "H1"
    assert fvg_analysis.state.bar_count >= 10
    assert fvg_analysis.bias.value in {"bullish", "bearish", "neutral", "undetermined"}


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
    order_blocks = OrderBlockEngine(
        config=OrderBlockConfig(enabled=True, timeframes=["H1"], min_candles=10),
    ).analyze(candles, structure, liquidity, timeframe="H1")
    analysis = FairValueGapEngine(
        config=_fvg_config(min_quality_score=0.3),
    ).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_block_state=order_blocks.state,
        timeframe="H1",
    )

    assert analysis.symbol == candles[0].symbol
    assert analysis.timeframe == candles[0].timeframe


def test_pipeline_with_explicit_fvg_candles() -> None:
    """Verify FVG detection on explicit three-candle gap candles with structure context."""
    fvg_candles = build_bullish_fvg_candles(25)
    structure = build_sample_structure()

    analysis = FairValueGapEngine(
        config=_fvg_config(min_quality_score=0.3),
    ).analyze(
        fvg_candles,
        structure,
        timeframe="H1",
    )

    assert len(analysis.fair_value_gaps) > 0
    assert analysis.state.bar_count == len(fvg_candles)
    assert any(gap.high == Decimal("2305") and gap.low == Decimal("2300") for gap in analysis.fair_value_gaps)
