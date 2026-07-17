# Premium / Discount Engine — Configuration

**Engine ID:** `market_premium_discount`  
**Sprint:** 8.1 (Architecture specification)  
**Status:** Not implemented

---

## Configuration Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Constructor injection | Tests and custom wiring |
| 2 | `config/settings.yaml` → `market_premium_discount` | Primary runtime config |
| 3 | `engines.market_premium_discount` toggle | Enable/disable flag |
| 4 | Pydantic model defaults | Code fallbacks |

Secrets remain in `.env` only (Constitution rule). No credentials in YAML.

---

## Configuration Hierarchy

```
config/settings.yaml
├── engines.market_premium_discount       # Global enable toggle
└── market_premium_discount               # Engine parameters
    ├── enabled
    ├── timeframes
    ├── min_candles
    ├── dealing_range.*                   # Range construction
    ├── swing_anchor.*                    # Swing selection
    ├── classification.*                  # Premium/discount/equilibrium
    ├── arrays.*                          # Premium/discount arrays
    ├── internal_range.*                  # Internal premium/discount
    ├── mtf.*                             # HTF and MTF alignment
    ├── nesting.*                         # Nested zone detection
    ├── fibonacci.*                       # Fibonacci dealing range
    ├── ote.*                             # Optimal trade entry zone
    ├── institutional.*                   # Context assembly
    ├── zone_filters.*                    # Upstream zone status filters
    └── quality.*                         # Scoring weights and thresholds
```

Nested keys are flattened into `PremiumDiscountConfig` fields in Sprint 8.2.

---

## YAML Schema (Planned)

```yaml
# Premium / Discount Engine configuration (Sprint 8.2+)
market_premium_discount:
  enabled: true
  timeframes:
    - M15
    - H1
    - H4
  min_candles: 20
  lookback: 100
  pip_size: 0.1

  # Dealing range
  primary_range_mode: external           # external | internal | auto
  min_range_size_pips: 10.0
  max_range_age_bars: 200
  allow_same_bar_range: false
  invalidate_on_bos: true
  invalidate_on_choch: false
  swing_replacement_mode: latest         # latest | confirmed_only

  # Swing anchor selection
  swing_selection_mode: latest_confirmed # latest_confirmed | range_extreme | structure_state
  swing_lookback_bars: 100
  min_swing_quality_score: 0.3
  prefer_labeled_swings: true            # prefer HH/HL/LH/LL over unlabeled

  # Classification
  equilibrium_tolerance_pips: 3.0
  price_reference: close                 # close | mid | hlc3

  # Arrays
  array_cluster_pips: 8.0
  min_array_entries: 2
  max_arrays_per_territory: 5
  include_liquidity_zones: true

  # Internal range
  compute_internal_bands: true

  # MTF
  mtf_alignment_min_score: 0.5
  htf_range_overlap_min_percent: 20.0
  htf_array_overlap_min_percent: 15.0

  # Nesting
  nest_overlap_min_percent: 80.0
  nesting_enabled: true

  # Fibonacci
  fibonacci:
    enabled: true
    direction_mode: structure_trend      # structure_trend | bullish | bearish | auto
    levels:
      - 0.0
      - 0.236
      - 0.382
      - 0.5
      - 0.618
      - 0.705
      - 0.79
      - 1.0

  # OTE (Optimal Trade Entry)
  ote:
    enabled: true
    fib_low: 0.62
    fib_high: 0.79
    default_direction: bullish           # bullish | bearish — when trend undetermined
    require_zone_overlap: false
    min_overlapping_zones: 1

  # Institutional context
  institutional:
    max_narrative_lines: 12
    include_htf_in_narrative: true
    include_ote_in_narrative: true

  # Zone status filters (upstream)
  zone_filters:
    order_block_statuses:
      - fresh
      - mitigated
    fvg_statuses:
      - open
      - partial
    breaker_statuses:
      - confirmed
      - candidate
    mitigation_statuses:
      - fresh
      - partial
      - confirmed

  # Quality & filtering
  min_quality_score: 0.4
  quality_weights:
    swing_quality: 0.15
    structure_quality: 0.15
    liquidity_confirmation: 0.10
    htf_alignment: 0.15
    fvg_alignment: 0.08
    order_block_alignment: 0.08
    breaker_alignment: 0.07
    mitigation_alignment: 0.07
    freshness: 0.05
    distance_from_equilibrium: 0.10

engines:
  market_premium_discount: true
```

---

## Settings Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Engine enabled flag |
| `timeframes` | `list[str]` | `M15,H1,H4` | Allowed analysis timeframes |
| `min_candles` | `int` | `20` | Minimum closed candles required |
| `lookback` | `int` | `100` | Historical bars scanned for swings |
| `pip_size` | `float` | `0.1` | Pip-to-price conversion for GOLD |
| `primary_range_mode` | `str` | `external` | Primary dealing range source |
| `min_range_size_pips` | `float` | `10.0` | Minimum valid range size |
| `max_range_age_bars` | `int` | `200` | Auto-invalidate stale ranges |
| `allow_same_bar_range` | `bool` | `false` | Allow high/low from same bar |
| `invalidate_on_bos` | `bool` | `true` | Invalidate range on opposing BOS |
| `invalidate_on_choch` | `bool` | `false` | Invalidate range on counter CHoCH |
| `swing_replacement_mode` | `str` | `latest` | How new swings replace anchors |
| `swing_selection_mode` | `str` | `latest_confirmed` | Swing anchor selection algorithm |
| `swing_lookback_bars` | `int` | `100` | Bars scanned for swing selection |
| `min_swing_quality_score` | `float` | `0.3` | Minimum swing quality to anchor range |
| `prefer_labeled_swings` | `bool` | `true` | Prefer HH/HL/LH/LL swings |
| `equilibrium_tolerance_pips` | `float` | `3.0` | Tolerance around 50% equilibrium |
| `price_reference` | `str` | `close` | Price used for territory classification |
| `array_cluster_pips` | `float` | `8.0` | Max distance to cluster array entries |
| `min_array_entries` | `int` | `2` | Minimum zones to form an array |
| `max_arrays_per_territory` | `int` | `5` | Cap arrays per premium/discount |
| `include_liquidity_zones` | `bool` | `true` | Include liquidity zones in arrays |
| `compute_internal_bands` | `bool` | `true` | Compute internal premium/discount |
| `mtf_alignment_min_score` | `float` | `0.5` | Minimum score for MTF alignment event |
| `htf_range_overlap_min_percent` | `float` | `20.0` | HTF/LTF range overlap threshold |
| `htf_array_overlap_min_percent` | `float` | `15.0` | HTF/LTF array overlap threshold |
| `nest_overlap_min_percent` | `float` | `80.0` | Nesting containment threshold |
| `nesting_enabled` | `bool` | `true` | Enable nested zone detection |
| `fibonacci.enabled` | `bool` | `true` | Compute Fibonacci dealing range |
| `fibonacci.direction_mode` | `str` | `structure_trend` | Fib projection direction |
| `fibonacci.levels` | `list[float]` | See YAML | Fibonacci ratios to project |
| `ote.enabled` | `bool` | `true` | Derive OTE zone |
| `ote.fib_low` | `float` | `0.62` | OTE lower Fib ratio |
| `ote.fib_high` | `float` | `0.79` | OTE upper Fib ratio |
| `ote.default_direction` | `str` | `bullish` | OTE direction when trend undetermined |
| `ote.require_zone_overlap` | `bool` | `false` | Require institutional zone in OTE |
| `ote.min_overlapping_zones` | `int` | `1` | Minimum overlapping zones for OTE |
| `institutional.max_narrative_lines` | `int` | `12` | Max narrative statements |
| `institutional.include_htf_in_narrative` | `bool` | `true` | Include HTF in narrative |
| `institutional.include_ote_in_narrative` | `bool` | `true` | Include OTE in narrative |
| `zone_filters.order_block_statuses` | `list[str]` | `fresh,mitigated` | OB statuses included in arrays |
| `zone_filters.fvg_statuses` | `list[str]` | `open,partial` | FVG statuses included |
| `zone_filters.breaker_statuses` | `list[str]` | `confirmed,candidate` | Breaker statuses included |
| `zone_filters.mitigation_statuses` | `list[str]` | `fresh,partial,confirmed` | Mitigation statuses included |
| `min_quality_score` | `float` | `0.4` | Minimum quality for high-confidence context |
| `quality_weights.swing_quality` | `float` | `0.15` | Swing quality weight |
| `quality_weights.structure_quality` | `float` | `0.15` | Structure quality weight |
| `quality_weights.liquidity_confirmation` | `float` | `0.10` | Liquidity confirmation weight |
| `quality_weights.htf_alignment` | `float` | `0.15` | HTF alignment weight |
| `quality_weights.fvg_alignment` | `float` | `0.08` | FVG alignment weight |
| `quality_weights.order_block_alignment` | `float` | `0.08` | OB alignment weight |
| `quality_weights.breaker_alignment` | `float` | `0.07` | Breaker alignment weight |
| `quality_weights.mitigation_alignment` | `float` | `0.07` | Mitigation alignment weight |
| `quality_weights.freshness` | `float` | `0.05` | Range freshness weight |
| `quality_weights.distance_from_equilibrium` | `float` | `0.10` | Equilibrium distance weight |

---

## Field Details

### `primary_range_mode`

| Mode | Behavior |
|------|----------|
| `external` | External dealing range drives classification, arrays, Fib, OTE |
| `internal` | Internal dealing range drives all primary outputs |
| `auto` | Select range with higher quality score; tie-break external |

### `swing_selection_mode`

| Mode | High Selection | Low Selection |
|------|----------------|---------------|
| `latest_confirmed` | Most recent swing high in lookback | Most recent swing low in lookback |
| `range_extreme` | Highest price in lookback | Lowest price in lookback |
| `structure_state` | `StructureState.last_swing_high` | `StructureState.last_swing_low` |

### `swing_replacement_mode`

| Mode | Behavior |
|------|----------|
| `latest` | New swing immediately replaces anchor if quality sufficient |
| `confirmed_only` | Replace only when new swing has equal or higher quality score |

### `price_reference`

| Mode | Price Used |
|------|------------|
| `close` | Latest closed candle close |
| `mid` | `(high + low) / 2` of latest candle |
| `hlc3` | `(high + low + close) / 3` of latest candle |

### `equilibrium_tolerance_pips`

Price or zone midpoint within this distance of dealing range equilibrium is classified as `equilibrium` rather than `premium` or `discount`.

```
tolerance_price = equilibrium_tolerance_pips * pip_size
```

For GOLD at `pip_size: 0.1`, `3.0` pips = `0.30` price units.

### `array_cluster_pips`

Maximum price distance between zone midpoints to merge into a single institutional array:

```
if abs(midpoint_a - midpoint_b) <= array_cluster_pips * pip_size:
    merge into same array cluster
```

### `fibonacci.direction_mode`

| Mode | Fib Projection |
|------|----------------|
| `structure_trend` | Bullish fib from low when trend bullish/range; bearish from high when bearish |
| `bullish` | Always measure from range low toward high |
| `bearish` | Always measure from range high toward low |
| `auto` | Infer from most recent BOS direction |

### `ote.fib_low` / `ote.fib_high`

Fibonacci retracement band within the dealing range defining the Optimal Trade Entry zone. Defaults follow ICT convention (62%–79%).

### `min_range_size_pips`

Minimum absolute range size in pips. Ranges smaller than this are invalid:

```
range_size_pips = (range_high - range_low) / pip_size
```

For GOLD at `pip_size: 0.1`, `10.0` pips = `1.0` price units minimum range.

### `distance_from_equilibrium` quality factor

Scores how clearly price sits in premium or discount vs equilibrium ambiguity:

| Distance (pips from EQ) | Score |
|-------------------------|-------|
| ≥ `equilibrium_tolerance_pips * 2` | 1.0 (clear territory) |
| Within tolerance band | 0.3 (ambiguous) |
| Between | Linear interpolation |

---

## Validation Rules

Configuration validated at load time by `PremiumDiscountConfig` Pydantic model.

| Rule | Constraint | On Failure |
|------|-----------|------------|
| `min_candles` | `>= 5` | Validation error |
| `lookback` | `>= min_candles` | Validation error |
| `pip_size` | `> 0` | Validation error |
| `primary_range_mode` | One of `external`, `internal`, `auto` | Validation error |
| `min_range_size_pips` | `>= 0` | Validation error |
| `max_range_age_bars` | `>= 1` | Validation error |
| `swing_selection_mode` | One of allowed modes | Validation error |
| `swing_replacement_mode` | One of `latest`, `confirmed_only` | Validation error |
| `swing_lookback_bars` | `>= 1` | Validation error |
| `min_swing_quality_score` | `0.0–1.0` | Validation error |
| `equilibrium_tolerance_pips` | `>= 0` | Validation error |
| `price_reference` | One of `close`, `mid`, `hlc3` | Validation error |
| `array_cluster_pips` | `>= 0` | Validation error |
| `min_array_entries` | `>= 1` | Validation error |
| `max_arrays_per_territory` | `>= 1` | Validation error |
| `mtf_alignment_min_score` | `0.0–1.0` | Validation error |
| HTF overlap percents | `0.0–100.0` each | Validation error |
| `nest_overlap_min_percent` | `0.0–100.0` | Validation error |
| `fibonacci.levels` | Each `0.0–1.0`; must include `0.5` | Validation error |
| `ote.fib_low` | `0.0–1.0` | Validation error |
| `ote.fib_high` | `0.0–1.0` | Validation error |
| `ote.fib_low` vs `ote.fib_high` | `fib_low < fib_high` | Validation error |
| `ote.default_direction` | One of `bullish`, `bearish` | Validation error |
| `min_quality_score` | `0.0–1.0` | Validation error |
| `timeframes` | Non-empty list | Validation error |
| `quality_weights.*` | Each `0.0–1.0` | Validation error |
| Quality weights sum | Must equal `1.0` (±0.01 tolerance) | Validation error |
| Zone filter lists | Non-empty when arrays enabled | Validation error |

---

## PremiumDiscountConfig Model (Planned)

| Field | Python Type | Maps To |
|-------|-------------|---------|
| `enabled` | `bool` | `market_premium_discount.enabled` |
| `timeframes` | `list[str]` | `market_premium_discount.timeframes` |
| `min_candles` | `int` | `market_premium_discount.min_candles` |
| `lookback` | `int` | `market_premium_discount.lookback` |
| `pip_size` | `Decimal` | `market_premium_discount.pip_size` |
| `primary_range_mode` | `PrimaryRangeMode` | `market_premium_discount.primary_range_mode` |
| `min_range_size_pips` | `Decimal` | `market_premium_discount.min_range_size_pips` |
| `max_range_age_bars` | `int` | `market_premium_discount.max_range_age_bars` |
| `allow_same_bar_range` | `bool` | `market_premium_discount.allow_same_bar_range` |
| `invalidate_on_bos` | `bool` | `market_premium_discount.invalidate_on_bos` |
| `invalidate_on_choch` | `bool` | `market_premium_discount.invalidate_on_choch` |
| `swing_replacement_mode` | `SwingReplacementMode` | `market_premium_discount.swing_replacement_mode` |
| `swing_selection_mode` | `SwingSelectionMode` | `market_premium_discount.swing_selection_mode` |
| `swing_lookback_bars` | `int` | `market_premium_discount.swing_lookback_bars` |
| `min_swing_quality_score` | `Decimal` | `market_premium_discount.min_swing_quality_score` |
| `prefer_labeled_swings` | `bool` | `market_premium_discount.prefer_labeled_swings` |
| `equilibrium_tolerance_pips` | `Decimal` | `market_premium_discount.equilibrium_tolerance_pips` |
| `price_reference` | `PriceReferenceMode` | `market_premium_discount.price_reference` |
| `array_cluster_pips` | `Decimal` | `market_premium_discount.array_cluster_pips` |
| `min_array_entries` | `int` | `market_premium_discount.min_array_entries` |
| `max_arrays_per_territory` | `int` | `market_premium_discount.max_arrays_per_territory` |
| `include_liquidity_zones` | `bool` | `market_premium_discount.include_liquidity_zones` |
| `compute_internal_bands` | `bool` | `market_premium_discount.compute_internal_bands` |
| `mtf_alignment_min_score` | `Decimal` | `market_premium_discount.mtf_alignment_min_score` |
| `htf_range_overlap_min_percent` | `Decimal` | `market_premium_discount.htf_range_overlap_min_percent` |
| `htf_array_overlap_min_percent` | `Decimal` | `market_premium_discount.htf_array_overlap_min_percent` |
| `nest_overlap_min_percent` | `Decimal` | `market_premium_discount.nest_overlap_min_percent` |
| `nesting_enabled` | `bool` | `market_premium_discount.nesting_enabled` |
| `fibonacci_enabled` | `bool` | `market_premium_discount.fibonacci.enabled` |
| `fibonacci_direction_mode` | `FibDirectionMode` | `market_premium_discount.fibonacci.direction_mode` |
| `fibonacci_levels` | `list[Decimal]` | `market_premium_discount.fibonacci.levels` |
| `ote_enabled` | `bool` | `market_premium_discount.ote.enabled` |
| `ote_fib_low` | `Decimal` | `market_premium_discount.ote.fib_low` |
| `ote_fib_high` | `Decimal` | `market_premium_discount.ote.fib_high` |
| `ote_default_direction` | `FibDirection` | `market_premium_discount.ote.default_direction` |
| `ote_require_zone_overlap` | `bool` | `market_premium_discount.ote.require_zone_overlap` |
| `ote_min_overlapping_zones` | `int` | `market_premium_discount.ote.min_overlapping_zones` |
| `min_quality_score` | `Decimal` | `market_premium_discount.min_quality_score` |
| `quality_weights` | `PremiumDiscountQualityWeights` | `market_premium_discount.quality_weights` |
| `zone_filters` | `ZoneStatusFilters` | `market_premium_discount.zone_filters` |

### Computed Properties (Planned)

| Property | Derivation |
|----------|------------|
| `equilibrium_tolerance_price` | `equilibrium_tolerance_pips * pip_size` |
| `array_cluster_price` | `array_cluster_pips * pip_size` |
| `min_range_size_price` | `min_range_size_pips * pip_size` |

---

## Environment Variables

No engine-specific environment variables. All parameters externalized via YAML per Constitution rule.

Global platform variables (`LOG_LEVEL`, etc.) apply via core configuration.

---

## Example: Minimal Configuration

```yaml
market_premium_discount:
  enabled: true
  timeframes: [H1]
  min_candles: 20
  primary_range_mode: external
  equilibrium_tolerance_pips: 3.0

engines:
  market_premium_discount: true
```

---

## Example: Full MTF + OTE Configuration

```yaml
market_premium_discount:
  enabled: true
  timeframes: [M15, H1, H4]
  min_candles: 30
  lookback: 150
  primary_range_mode: auto
  swing_selection_mode: latest_confirmed
  equilibrium_tolerance_pips: 2.5
  array_cluster_pips: 6.0
  min_array_entries: 2
  mtf_alignment_min_score: 0.6
  fibonacci:
    enabled: true
    direction_mode: structure_trend
  ote:
    enabled: true
    fib_low: 0.62
    fib_high: 0.79
    require_zone_overlap: true
    min_overlapping_zones: 2
  quality_weights:
    swing_quality: 0.15
    structure_quality: 0.15
    liquidity_confirmation: 0.10
    htf_alignment: 0.15
    fvg_alignment: 0.08
    order_block_alignment: 0.08
    breaker_alignment: 0.07
    mitigation_alignment: 0.07
    freshness: 0.05
    distance_from_equilibrium: 0.10
```

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Events | [EVENTS.md](./EVENTS.md) |
