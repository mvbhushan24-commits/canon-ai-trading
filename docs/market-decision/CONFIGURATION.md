# Decision Engine — Configuration

**Engine ID:** `market_decision`  
**Sprint:** 10.1 (Architecture specification)  
**Status:** Not implemented

---

## Configuration Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Constructor injection | Tests and custom wiring |
| 2 | `config/settings.yaml` → `market_decision` | Primary runtime config |
| 3 | `engines.market_decision` toggle | Enable/disable flag |
| 4 | Pydantic model defaults | Code fallbacks |

Secrets remain in `.env` only (Constitution rule). No credentials in YAML.

---

## Configuration Hierarchy

```
config/settings.yaml
├── engines.market_decision              # Global enable toggle
└── market_decision                      # Engine parameters
    ├── enabled
    ├── symbol
    ├── timeframes
    ├── pip_size
    ├── decision_validity_minutes
    ├── debounce_seconds
    ├── wait_timeout_seconds
    ├── raise_on_error                   # Testing only
    ├── evidence.*
    │   ├── min_required_engines
    │   ├── max_evidence_age_seconds.*
    │   └── stale_weight_factor
    ├── weights.*                          # Per-engine evidence weights
    ├── confidence.*
    ├── conflict.*
    ├── gates.*
    │   ├── session.*
    │   ├── structure.*
    │   ├── liquidity.*
    │   ├── premium_discount.*
    │   └── zones.*
    ├── entry.*
    ├── stop_loss.*
    ├── take_profit.*
    ├── risk.*
    │   ├── min_risk_reward
    │   ├── max_risk_reward
    │   ├── max_spread_pips
    │   ├── max_stop_size_pips
    │   ├── min_confidence
    │   └── session_restrictions.*
    ├── news_restriction.*
    ├── quality.*
    └── persistence.*
```

Nested keys are flattened into `MarketDecisionConfig` fields in Sprint 10.2.

---

## YAML Schema (Planned)

```yaml
# Decision Engine configuration (Sprint 10.2+)
market_decision:
  enabled: true
  symbol: GOLD.i#
  timeframes:
    - M5
    - M15
    - H1
  pip_size: 0.1

  # Decision lifecycle
  decision_validity_minutes: 60
  debounce_seconds: 5
  wait_timeout_seconds: 120
  raise_on_error: false

  # ── Evidence Collection ───────────────────────────────────────────
  evidence:
    min_required_engines: 5          # Of 8 evidence engines
    stale_weight_factor: 0.5           # Weight multiplier for stale evidence

    max_evidence_age_seconds:
      market_structure: 300
      market_liquidity: 300
      order_block: 300
      fair_value_gap: 300
      market_breaker: 300
      market_mitigation: 300
      market_premium_discount: 300
      market_sessions: 60
      current_price: 30

  # ── Evidence Weights (must sum to 1.0) ────────────────────────────
  weights:
    market_structure: 0.20
    market_liquidity: 0.15
    order_block: 0.12
    fair_value_gap: 0.10
    market_breaker: 0.08
    market_mitigation: 0.08
    market_premium_discount: 0.17
    market_sessions: 0.10

  # ── Confidence Scoring ────────────────────────────────────────────
  confidence:
    min_confidence: 65               # 0–100; below → NO_TRADE
    min_directional_weight: 0.35       # Minimum weighted sum for direction
    conflict_penalty:
      none: 0
      low: 5
      medium: 15
      high: 30
    stale_penalty_per_engine: 3        # Per stale engine
    confluence_bonus_per_zone: 5       # Per aligned zone (max 20)
    max_confluence_bonus: 20

  # ── Conflict Detection ────────────────────────────────────────────
  conflict:
    warn_threshold: 0.35               # conflict_ratio → warning
    reject_threshold: 0.55               # conflict_ratio → NO_TRADE

  # ── Validation Gates ────────────────────────────────────────────────
  gates:
    session:
      enabled: true
      require_kill_zone: false         # When true, active kill zone required
      min_kill_zone_quality: medium    # low | medium | high
      allow_equilibrium_trades: true   # Allow at equilibrium when other gates pass

    structure:
      enabled: true
      require_trend_alignment: true
      require_recent_bos: false        # When true, BOS within lookback required
      bos_lookback_bars: 20
      allow_range_trades: false        # Range trend → NO_TRADE

    liquidity:
      enabled: true
      require_sweep_or_grab: true
      liquidity_lookback_bars: 30
      min_sweep_quality: low           # low | medium | high

    premium_discount:
      enabled: true
      require_ote_for_entry: false     # When true, OTE zone required
      allow_equilibrium: true
      require_mtf_alignment: false

    zones:
      enabled: true
      gate_mode: grouped               # grouped | individual
      min_zone_confluence: 2           # Min aligned zones (OB/FVG/breaker/mitigation)
      max_zone_distance_pips: 15.0
      individual_requirements:
        order_block: false             # When gate_mode=individual
        fair_value_gap: false
        market_breaker: false
        market_mitigation: false

  # ── Entry ───────────────────────────────────────────────────────────
  entry:
    max_entry_distance_pips: 10.0
    prefer_ote: true
    zone_midpoint_entry: true          # Use zone midpoint vs boundary

  # ── Stop Loss ───────────────────────────────────────────────────────
  stop_loss:
    buffer_pips: 2.0
    prefer_structure_invalidation: true
    fallback_atr_multiplier: 1.5       # When no invalidation found

  # ── Take Profit ─────────────────────────────────────────────────────
  take_profit:
    max_targets: 3
    prefer_liquidity_pools: true
    min_target_distance_pips: 5.0
    rr_fallback_multiplier: 2.0        # TP = entry ± risk × multiplier

  # ── Risk Rules ──────────────────────────────────────────────────────
  risk:
    min_risk_reward: 2.0
    max_risk_reward: 8.0
    max_spread_pips: 3.0
    max_stop_size_pips: 50.0
    min_confidence: 65                 # Duplicate of confidence.min_confidence for risk gate

    session_restrictions:
      enabled: true
      blocked_availability:
        - closed
        - pre_open
      blocked_session_phases: []       # e.g. ["midday_lull"]
      allowed_kill_zones: []           # Empty = all enabled kill zones allowed
      blocked_kill_zones: []           # e.g. ["asian"] to exclude

  # ── News Restriction Hook ─────────────────────────────────────────
  news_restriction:
    enabled: false
    hook_path: null                    # Dotted path to callable; null = no block
    default_blocked: false

  # ── Decision Quality Model ──────────────────────────────────────────
  quality:
    enabled: true
    min_quality_score: 0               # 0 = informational only; >0 → NO_TRADE
    dimension_weights:
      evidence_completeness: 0.20
      zone_confluence: 0.20
      structure_clarity: 0.15
      liquidity_confirmation: 0.15
      premium_discount_alignment: 0.15
      session_quality: 0.15
    tier_thresholds:
      high: 80
      medium: 60

  # ── Persistence ─────────────────────────────────────────────────────
  persistence:
    enabled: true
    sqlite_table: decisions
    retain_days: 90
```

---

## Evidence Weights Reference

Weights must sum to `1.0` (±0.001 tolerance). Validation fails at startup if sum diverges.

| Engine | Config Key | Default | Rationale |
|--------|------------|---------|-----------|
| Market Structure | `weights.market_structure` | 0.20 | Primary directional framework |
| Market Liquidity | `weights.market_liquidity` | 0.15 | Sweep/grab confirmation |
| Order Block | `weights.order_block` | 0.12 | Institutional entry zones |
| Fair Value Gap | `weights.fair_value_gap` | 0.10 | Imbalance entry zones |
| Breaker Block | `weights.market_breaker` | 0.08 | Invalidation reversal zones |
| Mitigation Block | `weights.market_mitigation` | 0.08 | Retracement entry zones |
| Premium / Discount | `weights.market_premium_discount` | 0.17 | Institutional pricing context |
| Market Sessions | `weights.market_sessions` | 0.10 | Temporal quality filter |

### Weight Tuning Guidelines

| Scenario | Adjustment |
|----------|------------|
| Increase structure authority | Raise `market_structure` to 0.25; reduce zone weights proportionally |
| Stricter session filtering | Raise `market_sessions` to 0.15; enable `require_kill_zone` |
| Zone-heavy strategy | Raise `order_block` + `fair_value_gap` to 0.15 each; reduce `market_liquidity` |
| Conservative (fewer trades) | Raise `min_confidence` to 75; raise `min_zone_confluence` to 3 |

---

## Confidence Scoring Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_confidence` | 65 | Minimum 0–100 score for `BUY`/`SELL` |
| `min_directional_weight` | 0.35 | Minimum weighted directional sum |
| `conflict_penalty.high` | 30 | Confidence reduction for high conflict |
| `stale_penalty_per_engine` | 3 | Per stale engine penalty |
| `confluence_bonus_per_zone` | 5 | Per aligned institutional zone |
| `max_confluence_bonus` | 20 | Cap on confluence bonus |

### Confidence Formula

```
base = (Σ weighted_contributions / Σ active_weights) × 100
confidence = clamp(base - conflict_penalty - stale_penalty + confluence_bonus, 0, 100)
```

---

## Risk Rules Reference

| Rule | Config Key | Default | Failure Code |
|------|------------|---------|--------------|
| Minimum R:R | `risk.min_risk_reward` | 2.0 | `INVALID_RISK` |
| Maximum R:R | `risk.max_risk_reward` | 8.0 | `INVALID_RISK` |
| Maximum spread | `risk.max_spread_pips` | 3.0 | `INVALID_RISK` |
| Maximum stop size | `risk.max_stop_size_pips` | 50.0 | `INVALID_RISK` |
| Minimum confidence | `risk.min_confidence` | 65 | `LOW_CONFIDENCE` |
| Session restrictions | `risk.session_restrictions.*` | See YAML | `INVALID_SESSION` |
| News restriction hook | `news_restriction.*` | Disabled | Blocking reason only |

### Session Restrictions

| Key | Description |
|-----|-------------|
| `blocked_availability` | Market availability states that block trading |
| `blocked_session_phases` | Session phases that block trading |
| `allowed_kill_zones` | Whitelist (empty = all) |
| `blocked_kill_zones` | Blacklist |

### News Restriction Hook

External callable invoked before final decision:

```python
def news_restriction_hook(symbol: str, timestamp_utc: datetime) -> NewsRestrictionResult:
    return NewsRestrictionResult(blocked=False)
```

When `news_restriction.enabled: true` and hook returns `blocked=True` → `NO_TRADE` with reason in `risk_summary.news_block_reason`.

Future News & Macro Engine integration replaces the default hook without configuration schema changes.

---

## Decision Quality Model

Separate from confidence. Measures decision craftsmanship.

| Dimension | Weight | Scoring Method |
|-----------|--------|----------------|
| Evidence completeness | 0.20 | `available_engines / 8` |
| Zone confluence | 0.20 | `aligned_zones / 4` (OB, FVG, breaker, mitigation) |
| Structure clarity | 0.15 | Trend strength × BOS recency |
| Liquidity confirmation | 0.15 | Sweep/grab quality and recency |
| Premium/Discount alignment | 0.15 | OTE presence + MTF alignment score |
| Session quality | 0.15 | Kill zone quality tier mapping |

### Quality Tiers

| Tier | Threshold | Description |
|------|-----------|-------------|
| `high` | ≥ 80 | Strong institutional confluence |
| `medium` | ≥ 60 | Acceptable confluence |
| `low` | < 60 | Weak confluence; informational |

When `quality.min_quality_score > 0` and `quality_score < min_quality_score` → `NO_TRADE`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| — | — | No Decision Engine secrets in v1.0 |

All runtime parameters are in YAML per Constitution external configuration rule.

---

## Configuration Validation Rules

| Rule | Error |
|------|-------|
| `weights.*` sum to 1.0 (±0.001) | `MDE_CONFIG_INVALID` |
| `quality.dimension_weights.*` sum to 1.0 | `MDE_CONFIG_INVALID` |
| `min_risk_reward` < `max_risk_reward` | `MDE_CONFIG_INVALID` |
| `min_confidence` in 0–100 | `MDE_CONFIG_INVALID` |
| `min_required_engines` in 1–8 | `MDE_CONFIG_INVALID` |
| `pip_size` > 0 | `MDE_CONFIG_INVALID` |
| All `max_evidence_age_seconds` > 0 | `MDE_CONFIG_INVALID` |

---

## Example: Conservative Profile

```yaml
market_decision:
  confidence:
    min_confidence: 75
  conflict:
    reject_threshold: 0.45
  gates:
    session:
      require_kill_zone: true
      min_kill_zone_quality: medium
    zones:
      min_zone_confluence: 3
  risk:
    min_risk_reward: 2.5
    max_stop_size_pips: 35.0
  quality:
    min_quality_score: 70
```

---

## Example: Aggressive Profile

```yaml
market_decision:
  confidence:
    min_confidence: 55
  evidence:
    min_required_engines: 4
  gates:
    session:
      require_kill_zone: false
    zones:
      min_zone_confluence: 1
  risk:
    min_risk_reward: 1.5
    max_stop_size_pips: 60.0
  quality:
    min_quality_score: 0
```

---

## Loading Configuration (Planned)

```python
from backend.engines.market_decision import (
    load_market_decision_config,
    MarketDecisionEngine,
)

config = load_market_decision_config()
engine = MarketDecisionEngine(config=config)
```

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Events | [EVENTS.md](./EVENTS.md) |
