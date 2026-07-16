"""Unit tests for external liquidity detection."""

from backend.engines.market_liquidity.external import ExternalLiquidityDetector
from backend.engines.market_liquidity.schemas import LiquidityKind


def test_detect_external_liquidity(liquidity_config, liquidity_candles) -> None:
    detector = ExternalLiquidityDetector(liquidity_config)
    levels = detector.detect(liquidity_candles)

    kinds = {level.kind for level in levels}
    assert LiquidityKind.DAILY_HIGH in kinds
    assert LiquidityKind.DAILY_LOW in kinds
    assert LiquidityKind.PREVIOUS_HIGH in kinds
    assert LiquidityKind.PREVIOUS_LOW in kinds
    assert LiquidityKind.SESSION_HIGH in kinds
    assert LiquidityKind.SESSION_LOW in kinds
