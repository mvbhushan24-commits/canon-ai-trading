"""Unit tests for fair value gap configuration."""

from pathlib import Path

import pytest

from backend.engines.market_fvg.config import FairValueGapConfig, QualityWeights, load_fair_value_gap_config


def test_load_fair_value_gap_config(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
fair_value_gap:
  enabled: true
  timeframes:
    - H1
    - H4
  min_candles: 15
  lookback: 80
  pip_size: 0.1
  min_gap_size_pips: 3.0
  min_impulse_body_ratio: 0.6
  require_impulse_candle: false
  max_gap_age_bars: 120
  entry_touch_mode: body
  fill_mode: close
  invalidation_mode: body
  mitigation_mode: partial
  mitigation_fill_percent: 60.0
  full_fill_percent: 100.0
  dealing_range_mode: internal
  equilibrium_tolerance_pips: 5.0
  mtf_enabled: true
  mtf_timeframe_hierarchy:
    - H4
    - H1
  min_mtf_alignment_score: 0.6
  nesting_enabled: false
  min_quality_score: 0.5
  require_structure_alignment: true
  use_liquidity_confluence: false
  use_order_block_confluence: false
  quality_weights:
    impulse: 0.30
    gap_size: 0.15
    structure: 0.20
    bos: 0.10
    liquidity: 0.10
    order_block: 0.05
    premium_discount: 0.05
    mtf: 0.05
engines:
  fair_value_gap: true
""",
        encoding="utf-8",
    )

    config = load_fair_value_gap_config(yaml_path=yaml_file)

    assert config.enabled is True
    assert config.timeframes == ["H1", "H4"]
    assert config.min_candles == 15
    assert config.lookback == 80
    assert config.min_gap_size_pips == 3.0
    assert config.min_impulse_body_ratio == 0.6
    assert config.require_impulse_candle is False
    assert config.max_gap_age_bars == 120
    assert config.entry_touch_mode == "body"
    assert config.fill_mode == "close"
    assert config.invalidation_mode == "body"
    assert config.mitigation_mode == "partial"
    assert config.mitigation_fill_percent == 60.0
    assert config.dealing_range_mode == "internal"
    assert config.equilibrium_tolerance_pips == 5.0
    assert config.min_mtf_alignment_score == 0.6
    assert config.nesting_enabled is False
    assert config.min_quality_score == 0.5
    assert config.require_structure_alignment is True
    assert config.use_liquidity_confluence is False
    assert config.use_order_block_confluence is False
    assert config.quality_weights.impulse == 0.30


def test_quality_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="quality_weights must sum to 1.0"):
        QualityWeights(
            impulse=0.5,
            gap_size=0.5,
            structure=0.5,
            bos=0.5,
            liquidity=0.5,
            order_block=0.5,
            premium_discount=0.5,
            mtf=0.5,
        )


def test_entry_touch_mode_validation() -> None:
    with pytest.raises(ValueError, match="entry_touch_mode"):
        FairValueGapConfig(entry_touch_mode="invalid")


def test_fill_mode_validation() -> None:
    with pytest.raises(ValueError, match="fill_mode"):
        FairValueGapConfig(fill_mode="invalid")


def test_mitigation_mode_validation() -> None:
    with pytest.raises(ValueError, match="mitigation_mode"):
        FairValueGapConfig(mitigation_mode="invalid")


def test_min_quality_score_bounds() -> None:
    with pytest.raises(ValueError, match="Score thresholds"):
        FairValueGapConfig(min_quality_score=1.5)


def test_mtf_hierarchy_must_be_subset_of_timeframes() -> None:
    with pytest.raises(ValueError, match="mtf_timeframe_hierarchy"):
        FairValueGapConfig(
            timeframes=["H1"],
            mtf_timeframe_hierarchy=["H4", "H1"],
        )


def test_min_gap_size_price_property(fvg_config) -> None:
    assert fvg_config.min_gap_size_price == pytest.approx(0.2)


def test_equilibrium_tolerance_price_property(fvg_config) -> None:
    assert fvg_config.equilibrium_tolerance_price == pytest.approx(0.3)


def test_load_fair_value_gap_config_from_project() -> None:
    config = load_fair_value_gap_config()
    assert config.timeframes
    assert config.min_candles >= 1
