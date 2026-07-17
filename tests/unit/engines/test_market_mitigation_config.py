"""Unit tests for mitigation block configuration."""

from pathlib import Path

import pytest

from backend.engines.market_mitigation.config import (
    MitigationBlockConfig,
    QualityWeights,
    load_market_mitigation_config,
)


def test_load_market_mitigation_config(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
market_mitigation:
  enabled: true
  timeframes:
    - H1
    - H4
  min_candles: 15
  lookback: 80
  pip_size: 0.1
  min_displacement_pips: 6.0
  min_zone_size_pips: 2.0
  zone_bound_mode: wick
  require_bos_displacement: true
  deduplicate_by_origin: false
  mitigation_mode: body
  full_mitigation_percent: 80.0
  ce_mitigation_enabled: true
  min_bars_between_touches: 2
  min_bars_after_formation: 2
  confirmation_mode: body_touch
  min_touch_count: 2
  require_displacement_after_touch: true
  rejection_wick_ratio: 0.6
  require_structure_alignment: true
  max_block_age_bars: 120
  invalidation_mode: body
  invalidate_used_blocks: true
  invalidate_on_choch: true
  invalidate_on_parent_invalidated: false
  structure_scope_mode: internal
  dealing_range_mode: internal
  htf_overlap_min_percent: 30.0
  ltf_nesting_enabled: false
  nest_overlap_min_percent: 85.0
  confluence_formation_enabled: false
  equilibrium_tolerance_pips: 4.0
  use_liquidity_confluence: false
  liquidity_proximity_pips: 6.0
  use_order_block_confluence: false
  ob_overlap_min_percent: 20.0
  use_fvg_confluence: false
  fvg_ce_proximity_pips: 4.0
  fvg_overlap_min_percent: 12.0
  use_breaker_confluence: false
  breaker_overlap_min_percent: 20.0
  min_quality_score: 0.5
  quality_weights:
    displacement: 0.25
    structure: 0.15
    structure_scope: 0.10
    liquidity: 0.10
    order_block: 0.10
    fvg: 0.10
    breaker: 0.05
    htf_alignment: 0.05
    confirmation: 0.05
    freshness: 0.05
engines:
  market_mitigation: true
""",
        encoding="utf-8",
    )

    config = load_market_mitigation_config(yaml_path=yaml_file)

    assert config.enabled is True
    assert config.timeframes == ["H1", "H4"]
    assert config.min_candles == 15
    assert config.lookback == 80
    assert config.min_displacement_pips == 6.0
    assert config.min_zone_size_pips == 2.0
    assert config.zone_bound_mode == "wick"
    assert config.require_bos_displacement is True
    assert config.deduplicate_by_origin is False
    assert config.mitigation_mode == "body"
    assert config.full_mitigation_percent == 80.0
    assert config.ce_mitigation_enabled is True
    assert config.confirmation_mode == "body_touch"
    assert config.min_touch_count == 2
    assert config.max_block_age_bars == 120
    assert config.invalidation_mode == "body"
    assert config.structure_scope_mode == "internal"
    assert config.dealing_range_mode == "internal"
    assert config.min_quality_score == 0.5
    assert config.use_liquidity_confluence is False
    assert config.confluence_formation_enabled is False


def test_quality_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="quality_weights must sum to 1.0"):
        QualityWeights(
            displacement=0.5,
            structure=0.5,
            structure_scope=0.5,
            liquidity=0.5,
            order_block=0.5,
            fvg=0.5,
            breaker=0.5,
            htf_alignment=0.5,
            confirmation=0.5,
            freshness=0.5,
        )


def test_zone_bound_mode_validation() -> None:
    with pytest.raises(ValueError, match="zone_bound_mode"):
        MitigationBlockConfig(zone_bound_mode="invalid")


def test_mitigation_mode_validation() -> None:
    with pytest.raises(ValueError, match="mitigation_mode"):
        MitigationBlockConfig(mitigation_mode="invalid")


def test_confirmation_mode_validation() -> None:
    with pytest.raises(ValueError, match="confirmation_mode"):
        MitigationBlockConfig(confirmation_mode="invalid")


def test_invalidation_mode_validation() -> None:
    with pytest.raises(ValueError, match="invalidation_mode"):
        MitigationBlockConfig(invalidation_mode="invalid")


def test_structure_scope_mode_validation() -> None:
    with pytest.raises(ValueError, match="structure_scope_mode"):
        MitigationBlockConfig(structure_scope_mode="invalid")


def test_dealing_range_mode_validation() -> None:
    with pytest.raises(ValueError, match="dealing_range_mode"):
        MitigationBlockConfig(dealing_range_mode="invalid")


def test_min_quality_score_bounds() -> None:
    with pytest.raises(ValueError, match="Score and ratio"):
        MitigationBlockConfig(min_quality_score=1.5)


def test_lookback_must_exceed_min_candles() -> None:
    with pytest.raises(ValueError, match="lookback must be >= min_candles"):
        MitigationBlockConfig(min_candles=50, lookback=30)


def test_min_zone_size_price_property() -> None:
    config = MitigationBlockConfig(pip_size=0.1, min_zone_size_pips=2.0)
    assert float(config.min_zone_size_price) == pytest.approx(0.2)


def test_min_displacement_price_property() -> None:
    config = MitigationBlockConfig(pip_size=0.1, min_displacement_pips=5.0)
    assert float(config.min_displacement_price) == pytest.approx(0.5)


def test_timeframes_normalized_to_uppercase() -> None:
    config = MitigationBlockConfig(timeframes=["h1", " H4 "])
    assert config.timeframes == ["H1", "H4"]
