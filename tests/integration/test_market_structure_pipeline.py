"""Integration tests — Market Data candles into Market Structure Engine."""

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure import MarketStructureEngine
from backend.engines.market_structure.config import MarketStructureConfig
from tests.unit.engines.conftest import build_bullish_structure_candles


def test_pipeline_normalized_candles_to_structure() -> None:
    """Verify structure engine consumes only NormalizedCandle from market data schema."""
    candles: list[NormalizedCandle] = build_bullish_structure_candles(25)
    assert all(isinstance(c, NormalizedCandle) for c in candles)

    config = MarketStructureConfig(
        enabled=True,
        timeframes=["H1"],
        swing_lookback=2,
        min_candles=10,
    )
    engine = MarketStructureEngine(config=config)

    structure = engine.analyze(candles)

    assert structure.swing_highs or structure.swing_lows
    assert structure.current_structure_state.trend.value in {
        "bullish",
        "bearish",
        "range",
        "undetermined",
    }
    assert structure.evidence is not None


def test_pipeline_preserves_symbol_and_timeframe() -> None:
    candles = build_bullish_structure_candles(20)
    config = MarketStructureConfig(enabled=True, timeframes=["H1"], min_candles=10)
    engine = MarketStructureEngine(config=config)

    structure = engine.analyze(candles)

    assert structure.symbol == candles[0].symbol
    assert structure.timeframe == candles[0].timeframe
