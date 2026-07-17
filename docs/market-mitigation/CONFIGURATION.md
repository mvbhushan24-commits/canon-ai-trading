# Mitigation Block Engine — Configuration

**Engine ID:** `market_mitigation`  
**Sprint:** 7.1 (Architecture specification)  
**Status:** Not implemented

---

## Configuration Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Constructor injection | Tests and custom wiring |
| 2 | `config/settings.yaml` → `market_mitigation` | Primary runtime config |
| 3 | `engines.market_mitigation` toggle | Enable/disable flag |
| 4 | Pydantic model defaults | Code fallbacks |

Secrets remain in `.env` only (Constitution rule). No credentials in YAML.

---

## Configuration Hierarchy

```
config/settings.yaml
├── engines.market_mitigation          # Global enable toggle
└── market_mitigation                    # Engine parameters
    ├── enabled
    ├── timeframes
    ├── min_candles
    ├── formation.*                      # Displacement and zone bounds
    ├── touch.*                          # Multi-touch and partial mitigation
    ├── confirmation.*                   # Confirmation rules
    ├── lifecycle.*                      # Age, invalidation, expiration
    ├── structure.*                      # Internal/external scope
    ├── mtf.*                            # HTF/LTF alignment
    ├── confluence.*                     # Upstream zone overlap
    ├── premium_discount.*               # Dealing range
    └── quality.*                        # Scoring weights and thresholds
```

Nested keys are flattened into `MitigationBlockConfig` fields in Sprint 7.2. The hierarchy above is logical grouping for documentation; YAML may use flat or nested structure per loader implementation.

---

## YAML Schema (Planned)

```yaml
# Mitigation Block Engine configuration (Sprint 7.2+)
market_mitigation:
  enabled: true
  timeframes:
    - M15
    - H1
    - H4
  min_candles: 20
  lookback: 100
  pip_size: 0.1

  # Formation
  min_displacement_pips: 5.0
  min_zone_size_pips: 1.5
  zone_bound_mode: body                 # body | wick | full_candle
  require_bos_displacement: false       # require BOS event for displacement validation
  deduplicate_by_origin: true           # one block per origin bar + direction

  # Touch / mitigation
  mitigation_mode: wick                 # wick | body | close | partial
  full_mitigation_percent: 75.0         # percent traverse for full mitigation
  ce_mitigation_enabled: false          # midpoint touch counts as full mitigation
  min_bars_between_touches: 1
  min_bars_after_formation: 1

  # Confirmation
  confirmation_mode: wick_touch         # wick_touch | body_touch | close_inside | rejection | displacement_after
  min_touch_count: 1                    # minimum touches before confirmation
  require_displacement_after_touch: false
  rejection_wick_ratio: 0.5
  require_structure_alignment: false

  # Lifecycle
  max_block_age_bars: 150
  invalidation_mode: close              # close | body | wick
  invalidate_used_blocks: false         # re-invalidate fully used blocks
  invalidate_on_choch: false            # invalidate on counter-trend CHoCH
  invalidate_on_parent_invalidated: true

  # Structure scope
  structure_scope_mode: both            # internal | external | both
  dealing_range_mode: external          # external | internal

  # MTF
  htf_overlap_min_percent: 25.0
  ltf_nesting_enabled: true

  # Nesting
  nest_overlap_min_percent: 80.0        # containment threshold for nesting
  confluence_formation_enabled: true    # form blocks from upstream zone overlap

  # Premium / discount
  equilibrium_tolerance_pips: 3.0

  # Confluence
  use_liquidity_confluence: true
  liquidity_proximity_pips: 5.0
  use_order_block_confluence: true
  ob_overlap_min_percent: 15.0
  use_fvg_confluence: true
  fvg_ce_proximity_pips: 3.0
  fvg_overlap_min_percent: 10.0
  use_breaker_confluence: true
  breaker_overlap_min_percent: 15.0

  # Quality & filtering
  min_quality_score: 0.4
  quality_weights:
    displacement: 0.20
    structure: 0.15
    structure_scope: 0.10
    liquidity: 0.10
    order_block: 0.10
    fvg: 0.10
    breaker: 0.05
    htf_alignment: 0.10
    confirmation: 0.05
    freshness: 0.05

engines:
  market_mitigation: true
```

---

## Settings Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Engine enabled flag |
| `timeframes` | `list[str]` | `M15,H1,H4` | Allowed analysis timeframes |
| `min_candles` | `int` | `20` | Minimum closed candles required |
| `lookback` | `int` | `100` | Historical bars scanned for displacement |
| `pip_size` | `float` | `0.1` | Pip-to-price conversion for GOLD |
| `min_displacement_pips` | `float` | `5.0` | Minimum displacement leg size |
| `min_zone_size_pips` | `float` | `1.5` | Minimum block zone size |
| `zone_bound_mode` | `str` | `body` | Opposing candle zone derivation |
| `require_bos_displacement` | `bool` | `false` | Require BOS for displacement validation |
| `deduplicate_by_origin` | `bool` | `true` | One block per origin bar + direction |
| `mitigation_mode` | `str` | `wick` | Touch trigger mode |
| `full_mitigation_percent` | `float` | `75.0` | Traverse % for full mitigation |
| `ce_mitigation_enabled` | `bool` | `false` | CE touch counts as full mitigation |
| `min_bars_between_touches` | `int` | `1` | Minimum bars between distinct touches |
| `min_bars_after_formation` | `int` | `1` | Minimum bars before first valid touch |
| `confirmation_mode` | `str` | `wick_touch` | Mitigation confirmation trigger |
| `min_touch_count` | `int` | `1` | Minimum touches before confirmation |
| `require_displacement_after_touch` | `bool` | `false` | Require follow-through after touch |
| `rejection_wick_ratio` | `float` | `0.5` | Min wick/body ratio for rejection mode |
| `require_structure_alignment` | `bool` | `false` | Reject blocks against structure trend |
| `max_block_age_bars` | `int` | `150` | Auto-expire blocks beyond this age |
| `invalidation_mode` | `str` | `close` | Candle close vs body/wick for invalidation |
| `invalidate_used_blocks` | `bool` | `false` | Re-invalidate fully used blocks |
| `invalidate_on_choch` | `bool` | `false` | Invalidate on counter-trend CHoCH |
| `invalidate_on_parent_invalidated` | `bool` | `true` | Invalidate when parent zone invalidated |
| `structure_scope_mode` | `str` | `both` | Which structure ranges to evaluate |
| `dealing_range_mode` | `str` | `external` | Swing range source for premium/discount |
| `htf_overlap_min_percent` | `float` | `25.0` | Minimum HTF overlap for alignment |
| `ltf_nesting_enabled` | `bool` | `true` | Detect LTF blocks nested within zone |
| `nest_overlap_min_percent` | `float` | `80.0` | Containment threshold for nesting |
| `confluence_formation_enabled` | `bool` | `true` | Form blocks from upstream zone overlap |
| `equilibrium_tolerance_pips` | `float` | `3.0` | Tolerance around equilibrium |
| `use_liquidity_confluence` | `bool` | `true` | Score blocks near liquidity zones |
| `liquidity_proximity_pips` | `float` | `5.0` | Max distance to sweep for confluence |
| `use_order_block_confluence` | `bool` | `true` | Score blocks overlapping OBs |
| `ob_overlap_min_percent` | `float` | `15.0` | Minimum OB overlap % |
| `use_fvg_confluence` | `bool` | `true` | Score blocks overlapping FVGs |
| `fvg_ce_proximity_pips` | `float` | `3.0` | Max distance to FVG CE |
| `fvg_overlap_min_percent` | `float` | `10.0` | Minimum FVG overlap % |
| `use_breaker_confluence` | `bool` | `true` | Score blocks overlapping breakers |
| `breaker_overlap_min_percent` | `float` | `15.0` | Minimum breaker overlap % |
| `min_quality_score` | `float` | `0.4` | Minimum quality to include in output |
| `quality_weights.displacement` | `float` | `0.20` | Displacement strength weight |
| `quality_weights.structure` | `float` | `0.15` | Structure alignment weight |
| `quality_weights.structure_scope` | `float` | `0.10` | Internal/external scope weight |
| `quality_weights.liquidity` | `float` | `0.10` | Liquidity confluence weight |
| `quality_weights.order_block` | `float` | `0.10` | OB confluence weight |
| `quality_weights.fvg` | `float` | `0.10` | FVG confluence weight |
| `quality_weights.breaker` | `float` | `0.05` | Breaker confluence weight |
| `quality_weights.htf_alignment` | `float` | `0.10` | HTF alignment weight |
| `quality_weights.confirmation` | `float` | `0.05` | Confirmation quality weight |
| `quality_weights.freshness` | `float` | `0.05` | Post-formation freshness weight |

---

## Field Details

### `zone_bound_mode`

| Mode | Zone Bounds |
|------|-------------|
| `body` | Opposing candle open to close |
| `wick` | Opposing candle high to low |
| `full_candle` | Full range with body emphasis in quality scoring |

### `min_displacement_pips`

Minimum absolute displacement leg size in pips. Legs smaller than this do not produce mitigation block candidates. For GOLD at `pip_size: 0.1`, a `5.0` pip minimum equals `0.50` price units.

### `mitigation_mode`

| Mode | Touch Trigger |
|------|---------------|
| `wick` | Wick enters zone |
| `body` | Body enters zone |
| `close` | Close inside zone |
| `partial` | Zone traverse tracked incrementally |

### `full_mitigation_percent`

Percentage of zone traversed (0.0–100.0) required for full mitigation / `used` status:

```
traverse_percent = penetrated_range / zone_size * 100
```

When `ce_mitigation_enabled: true`, reaching the zone midpoint (CE) satisfies full mitigation regardless of traverse percent.

### `confirmation_mode`

| Mode | Confirmation Trigger |
|------|---------------------|
| `wick_touch` | Wick enters zone after formation |
| `body_touch` | Body enters zone after formation |
| `close_inside` | Close inside zone after formation |
| `rejection` | Wick beyond zone + close outside in block direction; wick/body ratio >= `rejection_wick_ratio` |
| `displacement_after` | Follow-through displacement after touch in block direction |

### `min_touch_count`

Minimum distinct touches (separated by `min_bars_between_touches`) before a block may transition to `confirmed`.

### `invalidation_mode`

| Mode | Invalidation Trigger |
|------|---------------------|
| `close` | Close beyond far boundary |
| `body` | Body beyond far boundary |
| `wick` | Wick beyond far boundary |

| Block Direction | Far Boundary |
|-----------------|--------------|
| Bullish mitigation block | `low` |
| Bearish mitigation block | `high` |

### `structure_scope_mode`

| Mode | Behavior |
|------|----------|
| `internal` | Classify internal scope only |
| `external` | Classify external scope only |
| `both` | Evaluate both; prefer external when both match |

### `nest_overlap_min_percent`

Minimum containment percentage for nesting classification:

```
containment_percent = intersection_size / block_size * 100
```

Block is nested when `containment_percent >= nest_overlap_min_percent`.

### `htf_overlap_min_percent`

Minimum overlap between LTF and HTF block zones for HTF alignment:

```
overlap_percent = overlap_size / min(ltf_size, htf_size) * 100
```

### `dealing_range_mode`

| Mode | Range Source |
|------|-------------|
| `external` | External structure swing high/low |
| `internal` | Internal structure swing high/low |

Same model as Fair Value Gap and Breaker Block engines for cross-engine consistency.

---

## Validation Rules

Configuration validated at load time by `MitigationBlockConfig` Pydantic model.

| Rule | Constraint | On Failure |
|------|-----------|------------|
| `min_candles` | `>= 5` | Validation error |
| `lookback` | `>= min_candles` | Validation error |
| `pip_size` | `> 0` | Validation error |
| `min_displacement_pips` | `>= 0` | Validation error |
| `min_zone_size_pips` | `>= 0` | Validation error |
| `zone_bound_mode` | One of `body`, `wick`, `full_candle` | Validation error |
| `mitigation_mode` | One of `wick`, `body`, `close`, `partial` | Validation error |
| `full_mitigation_percent` | `0.0–100.0` | Validation error |
| `min_bars_between_touches` | `>= 0` | Validation error |
| `min_bars_after_formation` | `>= 0` | Validation error |
| `confirmation_mode` | One of allowed modes | Validation error |
| `min_touch_count` | `>= 1` | Validation error |
| `rejection_wick_ratio` | `0.0–1.0` | Validation error |
| `max_block_age_bars` | `>= 1` | Validation error |
| `invalidation_mode` | One of `close`, `body`, `wick` | Validation error |
| `structure_scope_mode` | One of `internal`, `external`, `both` | Validation error |
| `dealing_range_mode` | One of `external`, `internal` | Validation error |
| `htf_overlap_min_percent` | `0.0–100.0` | Validation error |
| `nest_overlap_min_percent` | `0.0–100.0` | Validation error |
| Overlap min percents | `0.0–100.0` each | Validation error |
| `equilibrium_tolerance_pips` | `>= 0` | Validation error |
| `liquidity_proximity_pips` | `>= 0` | Validation error |
| `min_quality_score` | `0.0–1.0` | Validation error |
| `timeframes` | Non-empty list | Validation error |
| `quality_weights.*` | Each `0.0–1.0` | Validation error |
| Quality weights sum | Must equal `1.0` (±0.01 tolerance) | Validation error |

---

## MitigationBlockConfig Model (Planned)

| Field | Python Type | Maps To |
|-------|-------------|---------|
| `enabled` | `bool` | `market_mitigation.enabled` |
| `timeframes` | `list[str]` | `market_mitigation.timeframes` |
| `min_candles` | `int` | `market_mitigation.min_candles` |
| `lookback` | `int` | `market_mitigation.lookback` |
| `pip_size` | `Decimal` | `market_mitigation.pip_size` |
| `min_displacement_pips` | `Decimal` | `market_mitigation.min_displacement_pips` |
| `min_zone_size_pips` | `Decimal` | `market_mitigation.min_zone_size_pips` |
| `zone_bound_mode` | `ZoneBoundMode` | `market_mitigation.zone_bound_mode` |
| `require_bos_displacement` | `bool` | `market_mitigation.require_bos_displacement` |
| `deduplicate_by_origin` | `bool` | `market_mitigation.deduplicate_by_origin` |
| `mitigation_mode` | `MitigationMode` | `market_mitigation.mitigation_mode` |
| `full_mitigation_percent` | `Decimal` | `market_mitigation.full_mitigation_percent` |
| `ce_mitigation_enabled` | `bool` | `market_mitigation.ce_mitigation_enabled` |
| `min_bars_between_touches` | `int` | `market_mitigation.min_bars_between_touches` |
| `min_bars_after_formation` | `int` | `market_mitigation.min_bars_after_formation` |
| `confirmation_mode` | `ConfirmationMode` | `market_mitigation.confirmation_mode` |
| `min_touch_count` | `int` | `market_mitigation.min_touch_count` |
| `require_displacement_after_touch` | `bool` | `market_mitigation.require_displacement_after_touch` |
| `rejection_wick_ratio` | `Decimal` | `market_mitigation.rejection_wick_ratio` |
| `require_structure_alignment` | `bool` | `market_mitigation.require_structure_alignment` |
| `max_block_age_bars` | `int` | `market_mitigation.max_block_age_bars` |
| `invalidation_mode` | `TouchMode` | `market_mitigation.invalidation_mode` |
| `invalidate_used_blocks` | `bool` | `market_mitigation.invalidate_used_blocks` |
| `invalidate_on_choch` | `bool` | `market_mitigation.invalidate_on_choch` |
| `invalidate_on_parent_invalidated` | `bool` | `market_mitigation.invalidate_on_parent_invalidated` |
| `structure_scope_mode` | `StructureScopeMode` | `market_mitigation.structure_scope_mode` |
| `dealing_range_mode` | `DealingRangeMode` | `market_mitigation.dealing_range_mode` |
| `htf_overlap_min_percent` | `Decimal` | `market_mitigation.htf_overlap_min_percent` |
| `ltf_nesting_enabled` | `bool` | `market_mitigation.ltf_nesting_enabled` |
| `nest_overlap_min_percent` | `Decimal` | `market_mitigation.nest_overlap_min_percent` |
| `confluence_formation_enabled` | `bool` | `market_mitigation.confluence_formation_enabled` |
| `equilibrium_tolerance_pips` | `Decimal` | `market_mitigation.equilibrium_tolerance_pips` |
| `use_liquidity_confluence` | `bool` | `market_mitigation.use_liquidity_confluence` |
| `liquidity_proximity_pips` | `Decimal` | `market_mitigation.liquidity_proximity_pips` |
| `use_order_block_confluence` | `bool` | `market_mitigation.use_order_block_confluence` |
| `ob_overlap_min_percent` | `Decimal` | `market_mitigation.ob_overlap_min_percent` |
| `use_fvg_confluence` | `bool` | `market_mitigation.use_fvg_confluence` |
| `fvg_ce_proximity_pips` | `Decimal` | `market_mitigation.fvg_ce_proximity_pips` |
| `fvg_overlap_min_percent` | `Decimal` | `market_mitigation.fvg_overlap_min_percent` |
| `use_breaker_confluence` | `bool` | `market_mitigation.use_breaker_confluence` |
| `breaker_overlap_min_percent` | `Decimal` | `market_mitigation.breaker_overlap_min_percent` |
| `min_quality_score` | `Decimal` | `market_mitigation.min_quality_score` |
| `quality_weights` | `QualityWeights` | `market_mitigation.quality_weights` |

### Planned Internal Enums

#### `ZoneBoundMode`

| Value |
|-------|
| `body` |
| `wick` |
| `full_candle` |

#### `MitigationMode`

| Value |
|-------|
| `wick` |
| `body` |
| `close` |
| `partial` |

#### `ConfirmationMode`

| Value |
|-------|
| `wick_touch` |
| `body_touch` |
| `close_inside` |
| `rejection` |
| `displacement_after` |

#### `StructureScopeMode`

| Value |
|-------|
| `internal` |
| `external` |
| `both` |

#### `QualityWeights`

| Field | Default |
|-------|---------|
| `displacement` | `0.20` |
| `structure` | `0.15` |
| `structure_scope` | `0.10` |
| `liquidity` | `0.10` |
| `order_block` | `0.10` |
| `fvg` | `0.10` |
| `breaker` | `0.05` |
| `htf_alignment` | `0.10` |
| `confirmation` | `0.05` |
| `freshness` | `0.05` |

---

## Environment Variables

No engine-specific environment variables in Sprint 7.1. Engine toggle and parameters are YAML-only.

Global platform variables (MT5 credentials, log level) remain in `.env` per Constitution.

---

## Hot Reload

`MitigationBlockEngine.handle_config_updated(config)` accepts a new `MitigationBlockConfig` and rebuilds internal detector without resetting `prior_state`.

| Changed Parameter | Rebuild Required |
|-------------------|-----------------|
| Detection thresholds | Yes — re-run on next `analyze()` |
| Confirmation mode | Yes |
| Quality weights | Yes |
| Touch/mitigation modes | Yes |
| `enabled` flag | Engine skips analysis when `false` |
| `timeframes` | Validator updated immediately |

---

## Example Minimal Configuration

```yaml
market_mitigation:
  enabled: true
  timeframes: [H1]
  min_candles: 20
  lookback: 50
  pip_size: 0.1
  min_displacement_pips: 5.0
  zone_bound_mode: body
  confirmation_mode: wick_touch
  full_mitigation_percent: 75.0
  min_quality_score: 0.4

engines:
  market_mitigation: true
```

All omitted keys use Pydantic model defaults.

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)
- [EVENTS.md](./EVENTS.md)
