"""Unit tests for premium / discount detection pipeline orchestration."""

import pytest

pytest_plugins = ["tests.unit.engines.premium_discount_conftest"]

from backend.engines.market_breaker import BreakerBlockConfig, BreakerBlockEngine
from backend.engines.market_fvg import FairValueGapConfig, FairValueGapEngine
from backend.engines.market_liquidity import LiquidityEngine, MarketLiquidityConfig
from backend.engines.market_mitigation import MitigationBlockConfig, MitigationBlockEngine
from backend.engines.market_order_block import OrderBlockEngine, OrderBlockConfig
from backend.engines.market_order_block.schemas import OrderBlockStatus
from backend.engines.market_premium_discount import PremiumDiscountEngine
from backend.engines.market_premium_discount.detector import PremiumDiscountDetector
from backend.engines.market_premium_discount.schemas import PremiumDiscountBias, PremiumDiscountEventKind
from backend.engines.market_structure import MarketStructureConfig, MarketStructureEngine
from tests.unit.engines.conftest import build_bullish_structure_candles
from tests.unit.engines.premium_discount_conftest import (
    build_premium_discount_candles,
    build_premium_discount_structure,
    premium_config,
    sample_htf_premium_discount_context,
)


def _premium_pipeline_config(**overrides):
    defaults = {
        "enabled": True,
        "timeframes": ["H1"],
        "min_candles": 10,
        "lookback": 30,
        "pip_size": 0.1,
        "min_range_size_pips": 5.0,
        "min_quality_score": 0.3,
        "min_swing_quality_score": 0.2,
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


def test_detector_full_pipeline() -> None:
    candles = build_premium_discount_candles(30)
    structure = build_premium_discount_structure()
    config = _premium_pipeline_config()
    detector = PremiumDiscountDetector(config)
    analysis = detector.detect(candles, structure)

    assert analysis.symbol == candles[0].symbol
    assert analysis.timeframe == candles[0].timeframe
    assert analysis.state.bar_count == len(candles)
    assert analysis.dealing_range.is_valid is True
    assert analysis.events


def test_pipeline_full_chain_to_premium_discount() -> None:
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
    mitigation_analysis = MitigationBlockEngine(config=_mitigation_config()).analyze(
        candles,
        structure,
        order_blocks=order_blocks.order_blocks,
        liquidity_state=liquidity.state,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        timeframe="H1",
    )
    pd_analysis = PremiumDiscountEngine(config=_premium_pipeline_config()).analyze(
        candles,
        structure,
        liquidity_state=liquidity.state,
        order_blocks=order_blocks.order_blocks,
        fair_value_gap_state=fvg_analysis.state,
        breaker_blocks=breaker_analysis.breaker_blocks,
        mitigation_blocks=mitigation_analysis.mitigation_blocks,
        timeframe="H1",
    )

    assert pd_analysis.symbol == structure.symbol
    assert pd_analysis.timeframe == "H1"
    assert pd_analysis.state.bar_count >= 10
    assert pd_analysis.bias.value in {
        "premium",
        "discount",
        "equilibrium",
        "neutral",
        "undetermined",
    }


def test_pipeline_preserves_symbol_and_timeframe() -> None:
    candles = build_premium_discount_candles(25)
    structure = build_premium_discount_structure()
    analysis = PremiumDiscountEngine(config=_premium_pipeline_config()).analyze(
        candles,
        structure,
        timeframe="H1",
    )

    assert analysis.symbol == candles[0].symbol
    assert analysis.timeframe == candles[0].timeframe


def test_pipeline_with_htf_context() -> None:
    candles = build_premium_discount_candles(25)
    structure = build_premium_discount_structure()
    htf = sample_htf_premium_discount_context()
    analysis = PremiumDiscountEngine(config=_premium_pipeline_config(mtf_alignment_min_score=0.3)).analyze(
        candles,
        structure,
        htf_premium_discount_context=htf,
        timeframe="H1",
    )

    assert analysis.evidence
    assert PremiumDiscountEventKind.MTF_DISCOUNT_ALIGNED.value in {event.kind.value for event in analysis.events} or analysis.mtf_discount_alignment is not None or analysis.mtf_premium_alignment is not None


def test_pipeline_missing_upstream_context() -> None:
    candles = build_premium_discount_candles(25)
    analysis = PremiumDiscountEngine(config=_premium_pipeline_config()).analyze(
        candles,
        structure=None,
        timeframe="H1",
    )

    assert analysis.bias is PremiumDiscountBias.UNDETERMINED
    assert any("Structure context unavailable" in item for item in analysis.evidence)


def test_pipeline_regression_prior_sprints_unchanged() -> None:
    candles = build_premium_discount_candles(25)
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
    candles = build_premium_discount_candles(30)
    structure = build_premium_discount_structure()
    config = _premium_pipeline_config()
    detector = PremiumDiscountDetector(config)
    analysis = detector.detect(candles, structure)

    event_kinds = {event.kind for event in analysis.events}
    assert PremiumDiscountEventKind.PREMIUM_DISCOUNT_UPDATED in event_kinds
    assert PremiumDiscountEventKind.FIBONACCI_RANGE_COMPUTED in event_kinds or not analysis.dealing_range.is_valid
