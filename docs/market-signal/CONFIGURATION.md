# Signal Engine — Configuration

**Engine ID:** `market_signal`  
**Sprint:** 11.1 (Architecture specification)  
**Status:** Not implemented

---

## Configuration Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Constructor injection | Tests and custom wiring |
| 2 | `config/settings.yaml` → `market_signal` | Primary runtime config |
| 3 | `engines.market_signal` toggle | Enable/disable flag |
| 4 | Pydantic model defaults | Code fallbacks |

Secrets remain in `.env` only (Constitution rule). No credentials in YAML.

---

## Configuration Hierarchy

```
config/settings.yaml
├── engines.market_signal                  # Global enable toggle
└── market_signal                          # Engine parameters
    ├── enabled
    ├── symbol
    ├── timeframe
    ├── pip_size
    ├── auto_activate
    ├── signal_validity_minutes
    ├── max_decision_age_seconds
    ├── debounce_seconds
    ├── raise_on_error                     # Testing only
    ├── validation.*
    │   ├── min_confidence
    │   ├── min_decision_quality
    │   ├── require_evidence_summary
    │   └── require_risk_summary
    ├── duplicate.*
    │   ├── enabled
    │   ├── window_minutes
    │   └── entry_tolerance_pips
    ├── session.*
    │   ├── enabled
    │   └── blocked_sessions.*
    ├── risk.*
    │   ├── min_risk_reward
    │   ├── max_risk_reward
    │   ├── require_min_rr_met
    │   ├── require_spread_acceptable
    │   └── require_stop_size_acceptable
    ├── entry.*
    │   ├── zone_resolution
    │   └── buy_zone_edge / sell_zone_edge
    ├── take_profit.*
    │   └── max_targets
    ├── quality.*
    │   ├── min_signal_quality
    │   ├── weights.*
    │   └── adjustments.*
    ├── lifecycle.*
    │   ├── break_even.*
    │   ├── trailing.*
    │   └── partial_fill.*
    ├── events.*
    │   └── publish_rejections
    └── persistence.*
```

Nested keys are flattened into `MarketSignalConfig` fields in Sprint 11.2.

---

## YAML Schema (Planned)

```yaml
# Signal Engine configuration (Sprint 11.2+)
market_signal:
  enabled: true
  symbol: GOLD.i#
  timeframe: M15
  pip_size: 0.1

  # Signal lifecycle
  auto_activate: true
  signal_validity_minutes: 60
  max_decision_age_seconds: 300
  debounce_seconds: 3
  raise_on_error: false

  # ── Validation ────────────────────────────────────────────────────
  validation:
    min_confidence: 65                  # 0–100; below → rejection (LOW_CONFIDENCE)
    min_decision_quality: 60            # Optional; 0–100 decision quality floor
    require_evidence_summary: true      # Reject when evidence_summary empty
    require_risk_summary: true          # Reject when risk_summary missing

  # ── Duplicate Detection ─────────────────────────────────────────
  duplicate:
    enabled: true
    window_minutes: 60                  # Lookback for active signal comparison
    entry_tolerance_pips: 5.0           # Entry proximity threshold
    reject_same_decision_id: true       # Reject if decision_id already converted

  # ── Session Validation (decision-derived) ───────────────────────
  session:
    enabled: true
    blocked_sessions: []                # e.g. ["sydney_close"] — reject if decision session matches
    require_session_allowed: true       # risk_summary.session_allowed must be true

  # ── Risk Validation (decision-derived) ────────────────────────────
  risk:
    min_risk_reward: 2.0
    max_risk_reward: 8.0
    require_min_rr_met: true            # risk_summary.min_rr_met
    require_max_rr_met: true            # risk_summary.max_rr_met
    require_spread_acceptable: true     # risk_summary.spread_acceptable
    require_stop_size_acceptable: true  # risk_summary.stop_size_acceptable
    require_confidence_acceptable: true # risk_summary.confidence_acceptable

  # ── Entry Normalization ───────────────────────────────────────────
  entry:
    zone_resolution: midpoint           # midpoint | aggressive | conservative
    buy_zone_edge: zone_low             # Used when zone_resolution=aggressive for BUY
    sell_zone_edge: zone_high           # Used when zone_resolution=aggressive for SELL

  # ── Take Profit Mapping ───────────────────────────────────────────
  take_profit:
    max_targets: 3                      # Map up to 3 decision TPs
    require_minimum_one: true

  # ── Signal Quality Scoring ────────────────────────────────────────
  quality:
    min_signal_quality: 0               # 0 = disabled; e.g. 60 to reject low-quality signals

    weights:
      decision_confidence: 0.25
      decision_quality: 0.20
      risk_clarity: 0.15
      entry_precision: 0.10
      target_structure: 0.10
      evidence_completeness: 0.10
      explainability: 0.10
      # Must sum to 1.0

    adjustments:
      duplicate_proximity_penalty: 10   # When near-duplicate allowed via override
      stale_decision_penalty_max: 15    # Max penalty for aged decisions
      warning_penalty_per_item: 2       # Per decision warning
      warning_penalty_max: 10
      multi_tp_bonus: 5                 # When 3 TPs mapped

    tiers:
      high: 80
      medium: 60

    entry_precision_scores:
      point: 100
      ote: 85
      zone: 70

    target_structure_scores:
      one_tp: 60
      two_tp: 80
      three_tp: 100

  # ── Lifecycle Management ─────────────────────────────────────────
  lifecycle:
    enabled: true

    break_even:
      enabled: true
      trigger_after: TP1_HIT            # State after which break-even applies
      offset_pips: 1.0                  # Stop offset above/below entry

    trailing:
      enabled: false
      trigger_after: TP1_HIT
      trail_distance_pips: 15.0
      step_pips: 5.0

    partial_fill:
      enabled: false                    # Manual fill tracking in v1.0
      default_fill_pct: 50

    entry_trigger:
      mode: touch                       # touch | close — how entry is confirmed
      tolerance_pips: 1.0               # Entry trigger tolerance

    tp_trigger:
      mode: touch
      tolerance_pips: 0.5

    sl_trigger:
      mode: touch
      tolerance_pips: 0.5

  # ── Events ────────────────────────────────────────────────────────
  events:
    publish_rejections: false           # Emit SignalRejected audit events
    publish_lifecycle_events: true

  # ── Persistence ───────────────────────────────────────────────────
  persistence:
    enabled: true
    sqlite_table: signals
    retain_days: 90
    store_rejections: false
```

---

## Global Engine Toggle

```yaml
engines:
  market_signal:
    enabled: true
```

When `enabled: false`, `create_signal()` returns immediately with no signal and no events.

---

## Field Reference

### Core Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Engine master toggle |
| `symbol` | `str` | `GOLD.i#` | Supported instrument |
| `timeframe` | `str` | `M15` | Default signal timeframe |
| `pip_size` | `Decimal` | `0.1` | Pip size for XAUUSD |
| `auto_activate` | `bool` | `true` | Auto-transition `CREATED` → `ACTIVE` |
| `signal_validity_minutes` | `int` | `60` | Signal expiry when decision has no `valid_until_utc` |
| `max_decision_age_seconds` | `int` | `300` | Max age of decision at signal creation |
| `debounce_seconds` | `int` | `3` | Min interval between signal creations per symbol |
| `raise_on_error` | `bool` | `false` | Raise exceptions instead of returning rejections (testing) |

### Validation Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `validation.min_confidence` | `int` | `65` | Minimum decision confidence |
| `validation.min_decision_quality` | `int` | `60` | Minimum decision quality (0 = disabled) |
| `validation.require_evidence_summary` | `bool` | `true` | Require non-empty evidence summary |
| `validation.require_risk_summary` | `bool` | `true` | Require risk summary object |

### Duplicate Detection Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `duplicate.enabled` | `bool` | `true` | Enable duplicate detection |
| `duplicate.window_minutes` | `int` | `60` | Active signal lookback window |
| `duplicate.entry_tolerance_pips` | `Decimal` | `5.0` | Entry proximity for duplicate match |
| `duplicate.reject_same_decision_id` | `bool` | `true` | Reject re-processing same decision |

### Session Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `session.enabled` | `bool` | `true` | Enable session re-validation |
| `session.blocked_sessions` | `list[str]` | `[]` | Session names that block signal creation |
| `session.require_session_allowed` | `bool` | `true` | Require `risk_summary.session_allowed` |

### Risk Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `risk.min_risk_reward` | `Decimal` | `2.0` | Minimum R:R at signal layer |
| `risk.max_risk_reward` | `Decimal` | `8.0` | Maximum R:R at signal layer |
| `risk.require_min_rr_met` | `bool` | `true` | Require decision `min_rr_met` |
| `risk.require_max_rr_met` | `bool` | `true` | Require decision `max_rr_met` |
| `risk.require_spread_acceptable` | `bool` | `true` | Require spread check passed |
| `risk.require_stop_size_acceptable` | `bool` | `true` | Require stop size check passed |
| `risk.require_confidence_acceptable` | `bool` | `true` | Require confidence check passed |

### Entry Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `entry.zone_resolution` | `str` | `midpoint` | `midpoint`, `aggressive`, `conservative` |
| `entry.buy_zone_edge` | `str` | `zone_low` | Zone edge for aggressive BUY |
| `entry.sell_zone_edge` | `str` | `zone_high` | Zone edge for aggressive SELL |

### Take Profit Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `take_profit.max_targets` | `int` | `3` | Maximum TPs to map |
| `take_profit.require_minimum_one` | `bool` | `true` | Require at least one TP |

### Quality Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `quality.min_signal_quality` | `int` | `0` | Minimum signal quality (0 = disabled) |
| `quality.weights.*` | `Decimal` | See YAML | Dimension weights (sum to 1.0) |
| `quality.adjustments.*` | various | See YAML | Score adjustments |
| `quality.tiers.high` | `int` | `80` | High tier threshold |
| `quality.tiers.medium` | `int` | `60` | Medium tier threshold |

### Lifecycle Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `lifecycle.enabled` | `bool` | `true` | Enable lifecycle management |
| `lifecycle.break_even.enabled` | `bool` | `true` | Enable break-even stop move |
| `lifecycle.break_even.trigger_after` | `str` | `TP1_HIT` | State trigger for break-even |
| `lifecycle.break_even.offset_pips` | `Decimal` | `1.0` | Stop offset from entry |
| `lifecycle.trailing.enabled` | `bool` | `false` | Enable trailing stop |
| `lifecycle.trailing.trail_distance_pips` | `Decimal` | `15.0` | Trailing distance |
| `lifecycle.entry_trigger.mode` | `str` | `touch` | Entry confirmation mode |
| `lifecycle.entry_trigger.tolerance_pips` | `Decimal` | `1.0` | Entry trigger tolerance |

### Event Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `events.publish_rejections` | `bool` | `false` | Publish `SignalRejected` audit events |
| `events.publish_lifecycle_events` | `bool` | `true` | Publish trigger/close/expiry events |

### Persistence Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `persistence.enabled` | `bool` | `true` | SQLite persistence |
| `persistence.sqlite_table` | `str` | `signals` | Table name |
| `persistence.retain_days` | `int` | `90` | Retention period |
| `persistence.store_rejections` | `bool` | `false` | Persist rejection records |

---

## Quality Weight Validation Rules

| Rule | Constraint |
|------|------------|
| Weight sum | `quality.weights.*` must sum to `1.0` (±0.001) |
| Weight range | Each weight ∈ [0.0, 1.0] |
| Tier ordering | `high` > `medium` > 0 |
| Min quality | `min_signal_quality` ∈ [0, 100] |

Configuration load failure → engine returns rejection with `SIGNAL_VALIDATION_FAILED`.

---

## Configuration Validation Rules

| Rule | Constraint |
|------|------------|
| Symbol | Must be `XAUUSD` or `GOLD.i#` |
| Timeframe | Must be in approved list: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1` |
| Pip size | Must be > 0 |
| Confidence | `min_confidence` ∈ [0, 100] |
| R:R bounds | `min_risk_reward` > 0; `max_risk_reward` >= `min_risk_reward` |
| Duplicate window | `window_minutes` > 0 |
| Signal validity | `signal_validity_minutes` > 0 |

---

## Environment Variables

No Signal Engine secrets required. All runtime parameters in YAML.

| Variable | Used By | Notes |
|----------|---------|-------|
| — | — | Signal Engine has no `.env` dependencies |

---

## Configuration Reload

On `system.config.updated` event:

1. Reload `market_signal` section from `config/settings.yaml`
2. Validate new configuration
3. Apply to subsequent `create_signal()` calls
4. Active signals retain creation-time config snapshot in metadata
5. Lifecycle rules use active config unless `lifecycle.apply_retroactive: true` (default `false`)

---

## Example: Strict Signal Profile

```yaml
market_signal:
  validation:
    min_confidence: 75
    min_decision_quality: 70
  duplicate:
    window_minutes: 120
    entry_tolerance_pips: 3.0
  quality:
    min_signal_quality: 70
  risk:
    min_risk_reward: 2.5
```

---

## Example: Permissive Signal Profile

```yaml
market_signal:
  validation:
    min_confidence: 60
    min_decision_quality: 0
  duplicate:
    enabled: false
  quality:
    min_signal_quality: 0
  events:
    publish_rejections: true
```

---

## Relationship to Decision Engine Config

| Decision Config | Signal Config | Relationship |
|-----------------|---------------|--------------|
| `market_decision.confidence.min_confidence` | `market_signal.validation.min_confidence` | Signal may equal or exceed decision threshold |
| `market_decision.risk.min_risk_reward` | `market_signal.risk.min_risk_reward` | Signal re-validates; may be stricter |
| `market_decision.decision_validity_minutes` | `market_signal.signal_validity_minutes` | Signal expiry defaults to decision validity |

Signal Engine configuration is independent. Stricter signal thresholds filter decisions without modifying Decision Engine behavior.

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Decision Engine Config | [../market-decision/CONFIGURATION.md](../market-decision/CONFIGURATION.md) |
| Constitution | [../CONSTITUTION.md](../CONSTITUTION.md) |
