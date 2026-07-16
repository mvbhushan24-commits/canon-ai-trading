"""Unit tests for order block quality scoring."""

from decimal import Decimal

from backend.engines.market_order_block.engine import OrderBlockEngine
from backend.engines.market_order_block.quality import QualityScorer
from backend.engines.market_order_block.schemas import OrderBlockQuality, OrderBlockStatus
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.order_block_conftest import build_bullish_order_block_candles


def test_passes_minimum(order_block_config) -> None:
    scorer = QualityScorer(order_block_config)
    engine = OrderBlockEngine(config=order_block_config)
    candles = build_bullish_order_block_candles()
    blocks = engine.detect_bullish_blocks(candles, build_sample_structure())

    assert blocks
    assert scorer.passes_minimum(blocks[0].strength)


def test_structure_alignment_scoring(order_block_config) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    candles = build_bullish_order_block_candles()
    structure = build_sample_structure()

    with_structure = engine.detect_bullish_blocks(candles, structure)
    without_structure = engine.detect_bullish_blocks(candles)

    assert with_structure
    assert without_structure
    assert with_structure[0].structure_alignment is True
    assert without_structure[0].structure_alignment is False


def test_quality_tier_classification(order_block_config) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    candles = build_bullish_order_block_candles()
    blocks = engine.detect_bullish_blocks(candles, build_sample_structure())

    assert blocks
    assert blocks[0].quality in {
        OrderBlockQuality.HIGH,
        OrderBlockQuality.MEDIUM,
        OrderBlockQuality.LOW,
    }
    assert blocks[0].strength >= Decimal(str(order_block_config.min_quality_score))
