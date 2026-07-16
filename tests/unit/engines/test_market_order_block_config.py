"""Unit tests for order block configuration."""

from pathlib import Path

import pytest

from backend.engines.market_order_block.config import OrderBlockConfig, QualityWeights, load_order_block_config


def test_load_order_block_config(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
order_block:
  enabled: true
  timeframes:
    - H1
    - H4
  min_candles: 15
  lookback: 80
  zone_mode: wick
  min_displacement_pips: 8.0
  min_impulse_candles: 3
  pip_size: 0.1
  max_block_age_bars: 150
  min_quality_score: 0.5
  require_structure_alignment: true
  use_liquidity_confluence: false
  mitigation_touch_mode: body
  invalidation_mode: body
  quality_weights:
    displacement: 0.40
    structure: 0.30
    liquidity: 0.15
    freshness: 0.15
engines:
  order_block: true
""",
        encoding="utf-8",
    )

    config = load_order_block_config(yaml_path=yaml_file)

    assert config.enabled is True
    assert config.timeframes == ["H1", "H4"]
    assert config.min_candles == 15
    assert config.lookback == 80
    assert config.zone_mode == "wick"
    assert config.min_displacement_pips == 8.0
    assert config.min_impulse_candles == 3
    assert config.min_quality_score == 0.5
    assert config.require_structure_alignment is True
    assert config.use_liquidity_confluence is False
    assert config.mitigation_touch_mode == "body"
    assert config.invalidation_mode == "body"
    assert config.quality_weights.displacement == 0.40


def test_quality_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="quality_weights must sum to 1.0"):
        QualityWeights(displacement=0.5, structure=0.5, liquidity=0.5, freshness=0.5)


def test_zone_mode_validation() -> None:
    with pytest.raises(ValueError, match="zone_mode"):
        OrderBlockConfig(zone_mode="invalid")


def test_min_quality_score_bounds() -> None:
    with pytest.raises(ValueError, match="min_quality_score"):
        OrderBlockConfig(min_quality_score=1.5)


def test_min_displacement_price_property(order_block_config) -> None:
    assert order_block_config.min_displacement_price == pytest.approx(0.5)
