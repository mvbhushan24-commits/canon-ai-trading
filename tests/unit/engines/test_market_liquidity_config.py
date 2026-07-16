"""Unit tests for market liquidity configuration."""

from pathlib import Path

from backend.engines.market_liquidity.config import load_market_liquidity_config


def test_load_market_liquidity_config(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
market_liquidity:
  enabled: true
  timeframes:
    - H1
  equal_high_tolerance: 5
  equal_low_tolerance: 4
  minimum_cluster_size: 3
  lookback: 80
  session_filter:
    - london
engines:
  market_liquidity: true
""",
        encoding="utf-8",
    )

    config = load_market_liquidity_config(yaml_path=yaml_file)

    assert config.enabled is True
    assert config.timeframes == ["H1"]
    assert config.equal_high_tolerance == 5.0
    assert config.minimum_cluster_size == 3
    assert config.lookback == 80
    assert config.session_filter == ["london"]
