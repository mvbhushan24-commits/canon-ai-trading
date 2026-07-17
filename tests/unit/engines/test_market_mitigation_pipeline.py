"""Unit tests for mitigation block detection pipeline orchestration."""

import pytest

pytest_plugins = ["tests.unit.engines.mitigation_conftest"]

from backend.engines.market_breaker import BreakerBlockConfig, BreakerBlockEngine
from backend.engines.market_fvg import FairValueGapConfig, FairValueGapEngine
from backend.engines.market_liquidity import LiquidityEngine, MarketLiquidityConfig
from backend.engines.market_mitigation import MitigationBlockConfig, MitigationBlockEngine
from backend.engines.market_mitigation.detector import MitigationBlockDetector
from backend.engines.market_mitigation.schemas import MitigationBlockStatus
from backend.engines.market_order_block import OrderBlockEngine, OrderBlockConfig
from backend.engines.market_order_block.schemas import OrderBlockStatus
from backend.engines.market_structure import MarketStructureConfig, MarketStructureEngine
from tests.unit.engines.conftest import build_bullish_structure_candles
from tests.unit.engines.mitigation_conftest import (
    build_bullish_mitigation_base_candles,
    build_bullish_mitigation_touch_candles,
    mitigation_config,
)


def _mitigation_pipeline_config(**overrides) -> MitigationBlockConfig:
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


def test_detector_full_pipeline() -> None:
    candles = build_bullish_mitigation_touch_candles()
    config = mitigation_config()
    detector = MitigationBlockDetector(config)
    analysis = detector.detect(candles)

    assert analysis.symbol == candles[0].symbol
    assert analysis.timeframe == candles[0].timeframe
    assert analysis.state.bar_count == len(candles)
    assert len(analysis.mitigation_blocks) == (
        len(analysis.fresh_blocks)
        + len(analysis.partial_blocks)
        + len(analysis.confirmed_blocks)
        + len(analysis.used_blocks)
        + len(analysis.invalidated_blocks)
        + len(analysis.expired_blocks)
    )


def test_pipeline_full_chain_to_mitigation_blocks() -> None:
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
    invalidated_blocks = [
        block for block in order_blocks.order_blocks if block.status is OrderBlockStatus.INVALIDATED
    ]
    breaker_analysis = BreakerBlockEngine(config=_breaker_config()).analyze(
        candles,
        structure,
        invalidated_order_blocks=invalidated_blocks,
        liquidity_state=liquidity.state,
        fair_value_gap_state=fvg_analysis.state,
        timeframe="H1",
    )
    mitigation_analysis = MitigationBlockEngine(config=_mitigation_pipeline_config()).analyze(
        candles,
        structure,
        order_blocks=order_blocks.order_blocks,
        liquidity_state=liquidity.state,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        timeframe="H1",
    )

    assert mitigation_analysis.symbol == structure.symbol
    assert mitigation_analysis.timeframe == "H1"
    assert mitigation_analysis.state.bar_count >= 10
    assert mitigation_analysis.bias.value in {"bullish", "bearish", "neutral", "undetermined"}


def test_pipeline_preserves_symbol_and_timeframe() -> None:
    candles = build_bullish_mitigation_base_candles(25)
    analysis = MitigationBlockEngine(config=_mitigation_pipeline_config()).analyze(
        candles,
        timeframe="H1",
    )

    assert analysis.symbol == candles[0].symbol
    assert analysis.timeframe == candles[0].timeframe


def test_pipeline_with_explicit_mitigation_candles() -> None:
    from tests.unit.engines.mitigation_conftest import build_bullish_mitigation_partial_candles

    candles = build_bullish_mitigation_partial_candles()
    analysis = MitigationBlockEngine(config=_mitigation_pipeline_config()).analyze(
        candles,
        timeframe="H1",
    )

    assert len(analysis.mitigation_blocks) > 0
    assert analysis.state.bar_count == len(candles)
    assert any(
        block.status is MitigationBlockStatus.PARTIAL or block.touch_count >= 1
        for block in analysis.mitigation_blocks
    )


def test_pipeline_regression_prior_sprints_unchanged() -> None:
    candles = build_bullish_mitigation_base_candles(25)
    structure = MarketStructureEngine(
        config=MarketStructureConfig(enabled=True, timeframes=["H1"], min_candles=10),
    ).analyze(candles, timeframe="H1")
    liquidity = LiquidityEngine(
        config=MarketLiquidityConfig(enabled=True, timeframes=["H1"], min_candles=10),
    ).analyze(candles, structure, timeframe="H1")
    order_blocks = OrderBlockEngine(
        config=OrderBlockConfig(enabled=True, timeframes=["H1"], min_candles=10),
    ).analyze(candles, structure, liquidity, timeframe="H1")

    assert structure.symbol == candles[0].symbol
    assert liquidity.symbol == candles[0].symbol
    assert order_blocks.symbol == candles[0].symbol


def test_timeline_events_emitted() -> None:
    candles = build_bullish_mitigation_touch_candles()
    config = mitigation_config()
    detector = MitigationBlockDetector(config)
    analysis = detector.detect(candles)

    assert analysis.events
    event_kinds = {event.kind.value for event in analysis.events}
    assert "MitigationBlockDetected" in event_kinds or "BullishMitigationBlockDetected" in event_kinds
