# Breaker Block Engine — Configuration

**Engine ID:** `market_breaker`  
**Sprint:** 6.1 (Architecture specification)  
**Status:** Not implemented

---

## Configuration Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Constructor injection | Tests and custom wiring |
| 2 | `config/settings.yaml` → `market_breaker` | Primary runtime config |
| 3 | `engines.market_breaker` toggle | Enable/disable flag |
| 4 | Pydantic model defaults | Code fallbacks |

Secrets remain in `.env` only (Constitution rule). No credentials in YAML.

---

## YAML Schema (Planned)

```yaml
# Breaker Block Engine configuration (Sprint 6.2+)
market_breaker:
  enabled: true
  timeframes:
    - M15
    - H1
    - H4
  min_candles: 20
  lookback: 100
  pip_size: 0.1

  # Formation
  min_zone_size_pips: 2.0
  min_source_quality: medium          # high | medium | low
  fvg_breaker_enabled: false          # derive breakers from invalidated FVGs
  deduplicate_by_source: true         # one breaker per source_id

  # Confirmation
  confirmation_mode: wick_touch       # wick_touch | body_touch | close_inside | rejection
  min_bars_after_invalidation: 1
  max_bars_after_invalidation: 50
  require_displacement_after_invalidation: false
  rejection_wick_ratio: 0.5           # min wick-to-body ratio for rejection mode

  # Lifecycle
  max_breaker_age_bars: 150
  invalidation_mode: close            # close | body | wick
  mitigation_mode: wick               # wick | body | close | partial
  mitigation_percent: 50.0

  # Premium / discount
  dealing_range_mode: external        # external | internal
  equilibrium_tolerance_pips: 3.0

  # Confluence
  use_liquidity_confluence: true
  liquidity_proximity_pips: 5.0
  use_fvg_confluence: true
  fvg_ce_proximity_pips: 3.0
  fvg_overlap_min_percent: 10.0

  # Quality & filtering
  min_quality_score: 0.4
  require_structure_alignment: false
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
```

---

## Settings Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Engine enabled flag |
| `timeframes` | `list[str]` | `M15,H1,H4` | Allowed analysis timeframes |
| `min_candles` | `int` | `20` | Minimum closed candles required |
| `lookback` | `int` | `100` | Historical bars scanned for invalidations |
| `pip_size` | `float` | `0.1` | Pip-to-price conversion for GOLD |
| `min_zone_size_pips` | `float` | `2.0` | Minimum source zone size to qualify |
| `min_source_quality` | `str` | `medium` | Minimum source block/gap quality |
| `fvg_breaker_enabled` | `bool` | `false` | Enable FVG-derived breaker formation |
| `deduplicate_by_source` | `bool` | `true` | One breaker per source entity |
| `confirmation_mode` | `str` | `wick_touch` | Retest confirmation trigger |
| `min_bars_after_invalidation` | `int` | `1` | Minimum bars between invalidation and retest |
| `max_bars_after_invalidation` | `int` | `50` | Retest window before candidate expires |
| `require_displacement_after_invalidation` | `bool` | `false` | Require follow-through after invalidation |
| `rejection_wick_ratio` | `float` | `0.5` | Min wick/body ratio for rejection mode |
| `max_breaker_age_bars` | `int` | `150` | Auto-expire breakers beyond this age |
| `invalidation_mode` | `str` | `close` | Candle close vs body/wick for breaker invalidation |
| `mitigation_mode` | `str` | `wick` | Mitigation trigger mode |
| `mitigation_percent` | `float` | `50.0` | Zone traverse % for partial mitigation |
| `dealing_range_mode` | `str` | `external` | Swing range source for premium/discount |
| `equilibrium_tolerance_pips` | `float` | `3.0` | Tolerance around equilibrium |
| `use_liquidity_confluence` | `bool` | `true` | Score breakers near liquidity zones |
| `liquidity_proximity_pips` | `float` | `5.0` | Max distance to sweep for confluence |
| `use_fvg_confluence` | `bool` | `true` | Score breakers overlapping FVGs |
| `fvg_ce_proximity_pips` | `float` | `3.0` | Max distance to FVG CE for confluence |
| `fvg_overlap_min_percent` | `float` | `10.0` | Minimum zone overlap % for FVG confluence |
| `min_quality_score` | `float` | `0.4` | Minimum quality to include in output |
| `require_structure_alignment` | `bool` | `false` | Reject breakers against structure trend |
| `quality_weights.source_quality` | `float` | `0.20` | Source block quality weight |
| `quality_weights.invalidation_strength` | `float` | `0.15` | Invalidation displacement weight |
| `quality_weights.confirmation` | `float` | `0.20` | Confirmation quality weight |
| `quality_weights.structure` | `float` | `0.15` | Structure alignment weight |
| `quality_weights.liquidity` | `float` | `0.10` | Liquidity confluence weight |
| `quality_weights.fvg` | `float` | `0.10` | FVG confluence weight |
| `quality_weights.premium_discount` | `float` | `0.05` | Premium/discount placement weight |
| `quality_weights.freshness` | `float` | `0.05` | Post-confirmation freshness weight |

---

## Field Details

### `min_zone_size_pips`

Minimum absolute zone size in pips for the source order block or FVG. Sources smaller than this are rejected. For GOLD at `pip_size: 0.1`, a `2.0` pip minimum equals `0.20` price units.

### `min_source_quality`

Minimum quality tier of the source order block or FVG:

| Value | Accepts |
|-------|---------|
| `high` | Only `high` quality sources |
| `medium` | `high` and `medium` sources |
| `low` | All quality tiers |

### `confirmation_mode`

| Mode | Confirmation Trigger |
|------|---------------------|
| `wick_touch` | Wick enters breaker zone after invalidation bar |
| `body_touch` | Body enters breaker zone after invalidation bar |
| `close_inside` | Close inside breaker zone after invalidation bar |
| `rejection` | Wick beyond zone boundary + close outside in breaker direction; wick/body ratio >= `rejection_wick_ratio` |

### `min_bars_after_invalidation` / `max_bars_after_invalidation`

Retest must occur at least `min_bars_after_invalidation` bars after the source invalidation bar and within `max_bars_after_invalidation` bars. Candidates outside this window expire.

### `invalidation_mode`

| Mode | Breaker Invalidation Trigger |
|------|------------------------------|
| `close` | Close beyond far boundary |
| `body` | Body beyond far boundary |
| `wick` | Wick beyond far boundary |

| Breaker Direction | Far Boundary |
|-------------------|--------------|
| Bullish breaker | `low` |
| Bearish breaker | `high` |

### `mitigation_mode`

| Mode | Mitigation Trigger |
|------|-------------------|
| `wick` | Wick enters zone |
| `body` | Body enters zone |
| `close` | Close inside zone |
| `partial` | Zone traversed >= `mitigation_percent` |

### `dealing_range_mode`

| Mode | Range Source |
|------|-------------|
| `external` | External structure swing high/low |
| `internal` | Internal structure swing high/low |

Same model as Fair Value Gap Engine for cross-engine consistency.

### `liquidity_proximity_pips`

Maximum distance in pips between breaker zone midpoint and a recent sweep level to flag liquidity confluence when direct zone overlap is absent.

### `fvg_overlap_min_percent`

Minimum percentage overlap between breaker zone and FVG zone boundaries to flag FVG confluence:

```
overlap_percent = overlap_size / min(breaker_size, gap_size) * 100
```

---

## Validation Rules

Configuration validated at load time by `BreakerBlockConfig` Pydantic model.

| Rule | Constraint | On Failure |
|------|-----------|------------|
| `min_candles` | `>= 5` | Validation error |
| `lookback` | `>= min_candles` | Validation error |
| `pip_size` | `> 0` | Validation error |
| `min_zone_size_pips` | `>= 0` | Validation error |
| `min_source_quality` | One of `high`, `medium`, `low` | Validation error |
| `confirmation_mode` | One of allowed modes | Validation error |
| `min_bars_after_invalidation` | `>= 0` | Validation error |
| `max_bars_after_invalidation` | `> min_bars_after_invalidation` | Validation error |
| `rejection_wick_ratio` | `0.0–1.0` | Validation error |
| `max_breaker_age_bars` | `>= 1` | Validation error |
| `invalidation_mode` | One of `close`, `body`, `wick` | Validation error |
| `mitigation_mode` | One of `wick`, `body`, `close`, `partial` | Validation error |
| `mitigation_percent` | `0.0–100.0` | Validation error |
| `dealing_range_mode` | One of `external`, `internal` | Validation error |
| `equilibrium_tolerance_pips` | `>= 0` | Validation error |
| `liquidity_proximity_pips` | `>= 0` | Validation error |
| `fvg_ce_proximity_pips` | `>= 0` | Validation error |
| `fvg_overlap_min_percent` | `0.0–100.0` | Validation error |
| `min_quality_score` | `0.0–1.0` | Validation error |
| `timeframes` | Non-empty list | Validation error |
| `quality_weights.*` | Each `0.0–1.0` | Validation error |
| Quality weights sum | Must equal `1.0` (±0.01 tolerance) | Validation error |

---

## BreakerBlockConfig Model (Planned)

| Field | Python Type | Maps To |
|-------|-------------|---------|
| `enabled` | `bool` | `market_breaker.enabled` |
| `timeframes` | `list[str]` | `market_breaker.timeframes` |
| `min_candles` | `int` | `market_breaker.min_candles` |
| `lookback` | `int` | `market_breaker.lookback` |
| `pip_size` | `Decimal` | `market_breaker.pip_size` |
| `min_zone_size_pips` | `Decimal` | `market_breaker.min_zone_size_pips` |
| `min_source_quality` | `OrderBlockQuality` | `market_breaker.min_source_quality` |
| `fvg_breaker_enabled` | `bool` | `market_breaker.fvg_breaker_enabled` |
| `deduplicate_by_source` | `bool` | `market_breaker.deduplicate_by_source` |
| `confirmation_mode` | `ConfirmationMode` | `market_breaker.confirmation_mode` |
| `min_bars_after_invalidation` | `int` | `market_breaker.min_bars_after_invalidation` |
| `max_bars_after_invalidation` | `int` | `market_breaker.max_bars_after_invalidation` |
| `require_displacement_after_invalidation` | `bool` | `market_breaker.require_displacement_after_invalidation` |
| `rejection_wick_ratio` | `Decimal` | `market_breaker.rejection_wick_ratio` |
| `max_breaker_age_bars` | `int` | `market_breaker.max_breaker_age_bars` |
| `invalidation_mode` | `TouchMode` | `market_breaker.invalidation_mode` |
| `mitigation_mode` | `MitigationMode` | `market_breaker.mitigation_mode` |
| `mitigation_percent` | `Decimal` | `market_breaker.mitigation_percent` |
| `dealing_range_mode` | `DealingRangeMode` | `market_breaker.dealing_range_mode` |
| `equilibrium_tolerance_pips` | `Decimal` | `market_breaker.equilibrium_tolerance_pips` |
| `use_liquidity_confluence` | `bool` | `market_breaker.use_liquidity_confluence` |
| `liquidity_proximity_pips` | `Decimal` | `market_breaker.liquidity_proximity_pips` |
| `use_fvg_confluence` | `bool` | `market_breaker.use_fvg_confluence` |
| `fvg_ce_proximity_pips` | `Decimal` | `market_breaker.fvg_ce_proximity_pips` |
| `fvg_overlap_min_percent` | `Decimal` | `market_breaker.fvg_overlap_min_percent` |
| `min_quality_score` | `Decimal` | `market_breaker.min_quality_score` |
| `require_structure_alignment` | `bool` | `market_breaker.require_structure_alignment` |
| `quality_weights` | `QualityWeights` | `market_breaker.quality_weights` |

### Planned Internal Enums

#### `ConfirmationMode`

| Value |
|-------|
| `wick_touch` |
| `body_touch` |
| `close_inside` |
| `rejection` |

#### `MitigationMode`

| Value |
|-------|
| `wick` |
| `body` |
| `close` |
| `partial` |

#### `QualityWeights`

| Field | Default |
|-------|---------|
| `source_quality` | `0.20` |
| `invalidation_strength` | `0.15` |
| `confirmation` | `0.20` |
| `structure` | `0.15` |
| `liquidity` | `0.10` |
| `fvg` | `0.10` |
| `premium_discount` | `0.05` |
| `freshness` | `0.05` |

---

## Environment Variables

No engine-specific environment variables in Sprint 6.1. Engine toggle and parameters are YAML-only.

Global platform variables (MT5 credentials, log level) remain in `.env` per Constitution.

---

## Hot Reload

`BreakerBlockEngine.handle_config_updated(config)` accepts a new `BreakerBlockConfig` and rebuilds internal detector without resetting `prior_state`.

| Changed Parameter | Rebuild Required |
|-------------------|-----------------|
| Detection thresholds | Yes — re-run on next `analyze()` |
| Confirmation mode | Yes |
| Quality weights | Yes |
| `enabled` flag | Engine skips analysis when `false` |
| `timeframes` | Validator updated immediately |

---

## Example Minimal Configuration

```yaml
market_breaker:
  enabled: true
  timeframes: [H1]
  min_candles: 20
  lookback: 50
  pip_size: 0.1
  min_zone_size_pips: 2.0
  confirmation_mode: wick_touch
  min_quality_score: 0.4

engines:
  market_breaker: true
```

All omitted keys use Pydantic model defaults.

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)
- [EVENTS.md](./EVENTS.md)
