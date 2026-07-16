"""Unit tests for breaker block configuration."""

from pathlib import Path

import pytest

from backend.engines.market_breaker.config import (
    BreakerBlockConfig,
    QualityWeights,
    load_market_breaker_config,
)


def test_load_market_breaker_config(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
market_breaker:
  enabled: true
  timeframes:
    - H1
    - H4
  min_candles: 15
  lookback: 80
  pip_size: 0.1
  min_zone_size_pips: 3.0
  min_source_quality: high
  fvg_breaker_enabled: true
  deduplicate_by_source: false
  confirmation_mode: body_touch
  min_bars_after_invalidation: 2
  max_bars_after_invalidation: 40
  require_displacement_after_invalidation: true
  rejection_wick_ratio: 0.6
  max_breaker_age_bars: 120
  invalidation_mode: body
  mitigation_mode: partial
  mitigation_percent: 60.0
  dealing_range_mode: internal
  equilibrium_tolerance_pips: 5.0
  use_liquidity_confluence: false
  liquidity_proximity_pips: 8.0
  use_fvg_confluence: false
  fvg_ce_proximity_pips: 4.0
  fvg_overlap_min_percent: 15.0
  min_quality_score: 0.5
  require_structure_alignment: true
  quality_weights:
    source_quality: 0.20
    invalidation_strength: 0.15
    confirmation: 0.20
    structure: 0.15
    liquidity: 0.10
    fvg: 0.10
    premium_discount: 0.05
    freshness: 0.05
engines:
  market_breaker: true
""",
        encoding="utf-8",
    )

    config = load_market_breaker_config(yaml_path=yaml_file)

    assert config.enabled is True
    assert config.timeframes == ["H1", "H4"]
    assert config.min_candles == 15
    assert config.lookback == 80
    assert config.min_zone_size_pips == 3.0
    assert config.min_source_quality == "high"
    assert config.fvg_breaker_enabled is True
    assert config.deduplicate_by_source is False
    assert config.confirmation_mode == "body_touch"
    assert config.min_bars_after_invalidation == 2
    assert config.max_bars_after_invalidation == 40
    assert config.require_displacement_after_invalidation is True
    assert config.rejection_wick_ratio == 0.6
    assert config.max_breaker_age_bars == 120
    assert config.invalidation_mode == "body"
    assert config.mitigation_mode == "partial"
    assert config.mitigation_percent == 60.0
    assert config.dealing_range_mode == "internal"
    assert config.equilibrium_tolerance_pips == 5.0
    assert config.use_liquidity_confluence is False
    assert config.liquidity_proximity_pips == 8.0
    assert config.use_fvg_confluence is False
    assert config.min_quality_score == 0.5
    assert config.require_structure_alignment is True


def test_quality_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="quality_weights must sum to 1.0"):
        QualityWeights(
            source_quality=0.5,
            invalidation_strength=0.5,
            confirmation=0.5,
            structure=0.5,
            liquidity=0.5,
            fvg=0.5,
            premium_discount=0.5,
            freshness=0.5,
        )


def test_confirmation_mode_validation() -> None:
    with pytest.raises(ValueError, match="confirmation_mode"):
        BreakerBlockConfig(confirmation_mode="invalid")


def test_invalidation_mode_validation() -> None:
    with pytest.raises(ValueError, match="invalidation_mode"):
        BreakerBlockConfig(invalidation_mode="invalid")


def test_mitigation_mode_validation() -> None:
    with pytest.raises(ValueError, match="mitigation_mode"):
        BreakerBlockConfig(mitigation_mode="invalid")


def test_dealing_range_mode_validation() -> None:
    with pytest.raises(ValueError, match="dealing_range_mode"):
        BreakerBlockConfig(dealing_range_mode="invalid")


def test_min_quality_score_bounds() -> None:
    with pytest.raises(ValueError, match="Score and ratio"):
        BreakerBlockConfig(min_quality_score=1.5)


def test_lookback_must_exceed_min_candles() -> None:
    with pytest.raises(ValueError, match="lookback must be >= min_candles"):
        BreakerBlockConfig(min_candles=50, lookback=30)


def test_retest_window_validation() -> None:
    with pytest.raises(ValueError, match="max_bars_after_invalidation"):
        BreakerBlockConfig(min_bars_after_invalidation=10, max_bars_after_invalidation=10)


def test_min_zone_size_price_property() -> None:
    config = BreakerBlockConfig(pip_size=0.1, min_zone_size_pips=2.0)
    assert float(config.min_zone_size_price) == pytest.approx(0.2)


def test_timeframes_normalized_to_uppercase() -> None:
    config = BreakerBlockConfig(timeframes=["h1", " H4 "])
    assert config.timeframes == ["H1", "H4"]
