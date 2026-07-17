"""Unit tests for Market Decision Engine configuration."""

from decimal import Decimal
from pathlib import Path

import pytest

from backend.engines.market_decision.config import (
    EvidenceWeights,
    MarketDecisionConfig,
    QualityDimensionWeights,
    load_market_decision_config,
)
from tests.unit.engines.decision_conftest import decision_config


def test_default_config_enabled_flag() -> None:
    config = decision_config()
    assert config.enabled is True
    assert config.symbol == "XAUUSD"


def test_evidence_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="evidence weights must sum to 1.0"):
        EvidenceWeights(
            market_structure=0.5,
            market_liquidity=0.5,
            order_block=0.5,
            fair_value_gap=0.0,
            market_breaker=0.0,
            market_mitigation=0.0,
            market_premium_discount=0.0,
            market_sessions=0.0,
        )


def test_quality_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="quality dimension_weights must sum to 1.0"):
        QualityDimensionWeights(
            evidence_completeness=0.5,
            zone_confluence=0.5,
            structure_clarity=0.5,
            liquidity_confirmation=0.0,
            premium_discount_alignment=0.0,
            session_quality=0.0,
        )


def test_pip_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="pip_size must be positive"):
        MarketDecisionConfig(enabled=True, pip_size=0)


def test_risk_bounds_validation() -> None:
    with pytest.raises(ValueError, match="risk.min_risk_reward must be less"):
        MarketDecisionConfig(
            enabled=True,
            risk={"min_risk_reward": 8.0, "max_risk_reward": 2.0},
        )


def test_min_required_engines_bounds() -> None:
    with pytest.raises(ValueError, match="evidence.min_required_engines"):
        MarketDecisionConfig(enabled=True, evidence={"min_required_engines": 9})


def test_pip_size_decimal_property() -> None:
    config = decision_config(pip_size=0.1)
    assert config.pip_size_decimal == Decimal("0.1")


def test_default_news_hook_not_blocked() -> None:
    config = decision_config()
    result = config.default_news_hook("XAUUSD", None)
    assert result.blocked is False


def test_load_market_decision_config_from_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
market_decision:
  enabled: true
  symbol: GOLD.i#
  pip_size: 0.1
  decision_validity_minutes: 45
  evidence:
    min_required_engines: 6
    stale_weight_factor: 0.4
  confidence:
    min_confidence: 70
    min_directional_weight: 0.4
  conflict:
    warn_threshold: 0.30
    reject_threshold: 0.50
  risk:
    min_risk_reward: 2.5
    max_risk_reward: 6.0
    max_spread_pips: 2.5
  quality:
    min_quality_score: 55
engines:
  market_decision: true
""",
        encoding="utf-8",
    )

    config = load_market_decision_config(yaml_path=yaml_file)

    assert config.enabled is True
    assert config.symbol == "GOLD.i#"
    assert config.evidence.min_required_engines == 6
    assert config.evidence.stale_weight_factor == 0.4
    assert config.confidence.min_confidence == 70
    assert config.conflict.reject_threshold == 0.50
    assert config.risk.min_risk_reward == 2.5
    assert config.quality.min_quality_score == 55


def test_load_market_decision_config_engines_toggle(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
engines:
  market_decision: true
""",
        encoding="utf-8",
    )

    config = load_market_decision_config(yaml_path=yaml_file)
    assert config.enabled is True
