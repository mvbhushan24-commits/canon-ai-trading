# Fair Value Gap Engine — Configuration

**Engine ID:** `fair_value_gap`  
**Sprint:** 5.1 (Architecture specification)  
**Status:** Not implemented

---

## Configuration Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Constructor injection | Tests and custom wiring |
| 2 | `config/settings.yaml` → `fair_value_gap` | Primary runtime config |
| 3 | `engines.fair_value_gap` toggle | Enable/disable flag |
| 4 | Pydantic model defaults | Code fallbacks |

Secrets remain in `.env` only (Constitution rule). No credentials in YAML.

---

## YAML Schema (Planned)

```yaml
# Fair Value Gap Engine configuration (Sprint 5.2+)
fair_value_gap:
  enabled: true
  timeframes:
    - M15
    - H1
    - H4
  min_candles: 20
  lookback: 100
  pip_size: 0.1

  # Gap detection
  min_gap_size_pips: 2.0
  min_impulse_body_ratio: 0.5
  require_impulse_candle: true

  # Lifecycle
  max_gap_age_bars: 150
  entry_touch_mode: wick          # wick | body | close
  fill_mode: wick               # wick | body | close | ce
  invalidation_mode: close      # close | body
  mitigation_mode: ce           # ce | partial | full_fill
  mitigation_fill_percent: 50.0
  full_fill_percent: 100.0

  # Premium / discount
  dealing_range_mode: external    # external | internal
  equilibrium_tolerance_pips: 3.0

  # Multi-timeframe
  mtf_enabled: true
  mtf_timeframe_hierarchy:
    - H4
    - H1
    - M15
  min_mtf_alignment_score: 0.5

  # Nesting
  nesting_enabled: true

  # Quality & filtering
  min_quality_score: 0.4
  require_structure_alignment: false
  use_liquidity_confluence: true
  use_order_block_confluence: true
  quality_weights:
    impulse: 0.25
    gap_size: 0.15
    structure: 0.20
    bos: 0.10
    liquidity: 0.10
    order_block: 0.10
    premium_discount: 0.05
    mtf: 0.05

engines:
  fair_value_gap: true
```

---

## Settings Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Engine enabled flag |
| `timeframes` | `list[str]` | `M15,H1,H4` | Allowed analysis timeframes |
| `min_candles` | `int` | `20` | Minimum closed candles required |
| `lookback` | `int` | `100` | Historical bars scanned for gaps |
| `pip_size` | `float` | `0.1` | Pip-to-price conversion for GOLD |
| `min_gap_size_pips` | `float` | `2.0` | Minimum gap size to qualify |
| `min_impulse_body_ratio` | `float` | `0.5` | Middle candle body vs range ratio |
| `require_impulse_candle` | `bool` | `true` | Reject formations without impulse |
| `max_gap_age_bars` | `int` | `150` | Auto-expire gaps beyond this age |
| `entry_touch_mode` | `str` | `wick` | What constitutes gap entry |
| `fill_mode` | `str` | `wick` | What constitutes full fill |
| `invalidation_mode` | `str` | `close` | Candle close vs body for invalidation |
| `mitigation_mode` | `str` | `ce` | Mitigation trigger mode |
| `mitigation_fill_percent` | `float` | `50.0` | Fill % for partial mitigation |
| `full_fill_percent` | `float` | `100.0` | Fill % threshold for filled status |
| `dealing_range_mode` | `str` | `external` | Swing range source for premium/discount |
| `equilibrium_tolerance_pips` | `float` | `3.0` | Tolerance around equilibrium |
| `mtf_enabled` | `bool` | `true` | Enable MTF alignment scoring |
| `mtf_timeframe_hierarchy` | `list[str]` | `H4,H1,M15` | HTF → LTF processing order |
| `min_mtf_alignment_score` | `float` | `0.5` | Minimum score to flag MTF alignment |
| `nesting_enabled` | `bool` | `true` | Enable nested FVG resolution |
| `min_quality_score` | `float` | `0.4` | Minimum quality to include in output |
| `require_structure_alignment` | `bool` | `false` | Reject gaps against structure trend |
| `use_liquidity_confluence` | `bool` | `true` | Score gaps near liquidity zones |
| `use_order_block_confluence` | `bool` | `true` | Score gaps overlapping order blocks |
| `quality_weights.impulse` | `float` | `0.25` | Impulse candle strength weight |
| `quality_weights.gap_size` | `float` | `0.15` | Gap size weight |
| `quality_weights.structure` | `float` | `0.20` | Structure alignment weight |
| `quality_weights.bos` | `float` | `0.10` | BOS confirmation weight |
| `quality_weights.liquidity` | `float` | `0.10` | Liquidity confluence weight |
| `quality_weights.order_block` | `float` | `0.10` | Order block confluence weight |
| `quality_weights.premium_discount` | `float` | `0.05` | Premium/discount placement weight |
| `quality_weights.mtf` | `float` | `0.05` | MTF alignment weight |

---

## Field Details

### `min_gap_size_pips`

Minimum absolute gap size in pips. Gaps smaller than this are rejected as noise. For GOLD at `pip_size: 0.1`, a `2.0` pip minimum equals `0.20` price units.

### `min_impulse_body_ratio`

Ratio of middle candle (candle B) body size to total candle range. Values closer to `1.0` require strong displacement candles. Set to `0.0` to disable when `require_impulse_candle` is `false`.

### `entry_touch_mode`

| Mode | Entry Trigger |
|------|--------------|
| `wick` | Wick enters `[low, high]` zone |
| `body` | Body enters zone |
| `close` | Close enters zone |

### `fill_mode`

| Mode | Full Fill Trigger |
|------|-------------------|
| `wick` | Wick reaches far boundary |
| `body` | Body reaches far boundary |
| `close` | Close reaches or crosses far boundary |
| `ce` | Close reaches CE (classifies as mitigated, not filled) |

### `invalidation_mode`

| Mode | Invalidation Trigger |
|------|---------------------|
| `close` | Close beyond far boundary in opposing direction |
| `body` | Body fully beyond far boundary |

**Far boundary definition:**

| Direction | Far Boundary |
|-----------|-------------|
| Bullish FVG | `low` (candle A high) — invalidated when price closes below |
| Bearish FVG | `high` (candle A low) — invalidated when price closes above |

### `mitigation_mode`

| Mode | Mitigation Trigger |
|------|-------------------|
| `ce` | Price touches `ce_price` |
| `partial` | `fill_percent >= mitigation_fill_percent` |
| `full_fill` | Gap transitions to `filled` status |

### `dealing_range_mode`

| Mode | Range Source |
|------|-------------|
| `external` | `MarketStructure.external_structure` swing bounds |
| `internal` | `MarketStructure.internal_structure` swing bounds |

### `equilibrium_tolerance_pips`

Gap CE within this distance of dealing range equilibrium is classified as `equilibrium` rather than `premium` or `discount`.

### `mtf_timeframe_hierarchy`

Ordered list from highest to lowest timeframe. Orchestrator uses this to determine analysis order and which gaps to pass as `higher_timeframe_gaps`.

### `require_structure_alignment`

When `true`, bullish gaps are suppressed in bearish structure (and vice versa) unless CHoCH evidence is present in `MarketStructure.choch_events`.

### `use_liquidity_confluence`

When `true`, gaps overlapping `LiquidityState.active_zones` or forming after `recent_sweeps` receive confluence bonus.

### `use_order_block_confluence`

When `true`, gaps whose `[low, high]` intersects any `OrderBlockState.active_blocks` zone receive confluence bonus.

### `quality_weights`

Must sum to `1.0`. Validated at config load time.

---

## Config Model (Planned)

```python
class QualityWeights(BaseModel):
    impulse: float = 0.25
    gap_size: float = 0.15
    structure: float = 0.20
    bos: float = 0.10
    liquidity: float = 0.10
    order_block: float = 0.10
    premium_discount: float = 0.05
    mtf: float = 0.05


class FairValueGapConfig(BaseModel):
    enabled: bool = False
    timeframes: list[str] = ["M15", "H1", "H4"]
    min_candles: int = 20
    lookback: int = 100
    pip_size: float = 0.1
    min_gap_size_pips: float = 2.0
    min_impulse_body_ratio: float = 0.5
    require_impulse_candle: bool = True
    max_gap_age_bars: int = 150
    entry_touch_mode: str = "wick"
    fill_mode: str = "wick"
    invalidation_mode: str = "close"
    mitigation_mode: str = "ce"
    mitigation_fill_percent: float = 50.0
    full_fill_percent: float = 100.0
    dealing_range_mode: str = "external"
    equilibrium_tolerance_pips: float = 3.0
    mtf_enabled: bool = True
    mtf_timeframe_hierarchy: list[str] = ["H4", "H1", "M15"]
    min_mtf_alignment_score: float = 0.5
    nesting_enabled: bool = True
    min_quality_score: float = 0.4
    require_structure_alignment: bool = False
    use_liquidity_confluence: bool = True
    use_order_block_confluence: bool = True
    quality_weights: QualityWeights = Field(default_factory=QualityWeights)
```

---

## Loader Function (Planned)

```python
def load_fair_value_gap_config(yaml_path: Path | None = None) -> FairValueGapConfig:
    """Load fair value gap configuration from YAML."""
```

Follows the same pattern as `load_order_block_config()` and `load_market_liquidity_config()`.

---

## Environment Variables

No engine-specific environment variables in Sprint 5.1 spec. Symbol and broker remain in Market Data config (`.env` / `market_data` YAML section).

---

## Validation Rules (Config Load)

| Rule | Error |
|------|-------|
| `quality_weights` sum != 1.0 | `FVE_CONFIG_INVALID` |
| `min_gap_size_pips <= 0` | `FVE_CONFIG_INVALID` |
| `mitigation_fill_percent` not in (0, 100] | `FVE_CONFIG_INVALID` |
| `entry_touch_mode` not in allowed set | `FVE_CONFIG_INVALID` |
| `fill_mode` not in allowed set | `FVE_CONFIG_INVALID` |
| `mtf_timeframe_hierarchy` not subset of `timeframes` | `FVE_CONFIG_INVALID` |
| Empty `timeframes` list | `FVE_CONFIG_INVALID` |

---

## Example: Development Setup

```yaml
fair_value_gap:
  enabled: true
  timeframes:
    - H1
    - H4
  min_candles: 15
  lookback: 80
  min_gap_size_pips: 1.5
  min_impulse_body_ratio: 0.3
  min_quality_score: 0.3
  require_structure_alignment: false
  use_liquidity_confluence: true
  use_order_block_confluence: true
  mitigation_mode: ce
  mtf_enabled: true
```

---

## Example: Conservative / Institutional Setup

```yaml
fair_value_gap:
  enabled: true
  timeframes:
    - H1
    - H4
  min_gap_size_pips: 3.0
  min_impulse_body_ratio: 0.6
  require_structure_alignment: true
  require_impulse_candle: true
  min_quality_score: 0.6
  mitigation_mode: ce
  invalidation_mode: close
  max_gap_age_bars: 100
  mtf_enabled: true
  min_mtf_alignment_score: 0.7
```

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [../SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) — Configuration hierarchy
