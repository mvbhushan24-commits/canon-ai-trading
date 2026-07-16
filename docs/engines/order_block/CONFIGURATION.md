# Order Block Engine — Configuration

**Engine ID:** `order_block`  
**Sprint:** 4.1 (Architecture specification)  
**Status:** Not implemented

---

## Configuration Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Constructor injection | Tests and custom wiring |
| 2 | `config/settings.yaml` → `order_block` | Primary runtime config |
| 3 | `engines.order_block` toggle | Enable/disable flag |
| 4 | Pydantic model defaults | Code fallbacks |

Secrets remain in `.env` only (Constitution rule). No credentials in YAML.

---

## YAML Schema (Planned)

```yaml
# Order Block Engine configuration (Sprint 4.2+)
order_block:
  enabled: true
  timeframes:
    - M15
    - H1
    - H4
  min_candles: 20
  lookback: 100
  zone_mode: body              # body | wick | full
  min_displacement_pips: 5.0
  min_impulse_candles: 2
  pip_size: 0.1
  max_block_age_bars: 200
  min_quality_score: 0.4
  require_structure_alignment: false
  use_liquidity_confluence: true
  mitigation_touch_mode: wick  # wick | body | close
  invalidation_mode: close     # close | body
  quality_weights:
    displacement: 0.35
    structure: 0.30
    liquidity: 0.20
    freshness: 0.15

engines:
  order_block: true
```

---

## Settings Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Engine enabled flag |
| `timeframes` | `list[str]` | `M15,H1,H4` | Allowed analysis timeframes |
| `min_candles` | `int` | `20` | Minimum closed candles required |
| `lookback` | `int` | `100` | Historical bars scanned for blocks |
| `zone_mode` | `str` | `body` | Origin zone boundary rule |
| `min_displacement_pips` | `float` | `5.0` | Minimum displacement after origin |
| `min_impulse_candles` | `int` | `2` | Consecutive impulse candles required |
| `pip_size` | `float` | `0.1` | Pip-to-price conversion for GOLD |
| `max_block_age_bars` | `int` | `200` | Auto-expire blocks beyond this age |
| `min_quality_score` | `float` | `0.4` | Minimum quality to include in output |
| `require_structure_alignment` | `bool` | `false` | Reject blocks against structure trend |
| `use_liquidity_confluence` | `bool` | `true` | Score blocks near liquidity sweeps |
| `mitigation_touch_mode` | `str` | `wick` | What constitutes a mitigation touch |
| `invalidation_mode` | `str` | `close` | Candle close vs body for invalidation |
| `quality_weights.displacement` | `float` | `0.35` | Displacement factor weight |
| `quality_weights.structure` | `float` | `0.30` | Structure alignment weight |
| `quality_weights.liquidity` | `float` | `0.20` | Liquidity confluence weight |
| `quality_weights.freshness` | `float` | `0.15` | Block age/freshness weight |

---

## Field Details

### `zone_mode`

Defines how origin candle bounds map to the order block zone:

| Mode | Zone Bounds |
|------|-------------|
| `body` | `min(open, close)` to `max(open, close)` |
| `wick` | Full candle wick (`low` to `high`) |
| `full` | Extended wick with configurable buffer |

### `min_displacement_pips`

Minimum distance price must move away from the origin zone to confirm a valid order block. Prevents false blocks on minor moves.

### `mitigation_touch_mode`

| Mode | Mitigation Trigger |
|------|-------------------|
| `wick` | Wick enters zone |
| `body` | Body enters zone |
| `close` | Close enters zone |

### `invalidation_mode`

| Mode | Invalidation Trigger |
|------|---------------------|
| `close` | Close beyond far boundary |
| `body` | Body fully beyond far boundary |

### `require_structure_alignment`

When `true`, bullish blocks are suppressed in bearish structure (and vice versa) unless CHoCH evidence is present.

### `quality_weights`

Must sum to `1.0`. Validated at config load time.

---

## Config Model (Planned)

```python
class OrderBlockConfig(BaseModel):
    enabled: bool = False
    timeframes: list[str] = ["M15", "H1", "H4"]
    min_candles: int = 20
    lookback: int = 100
    zone_mode: str = "body"
    min_displacement_pips: float = 5.0
    min_impulse_candles: int = 2
    pip_size: float = 0.1
    max_block_age_bars: int = 200
    min_quality_score: float = 0.4
    require_structure_alignment: bool = False
    use_liquidity_confluence: bool = True
    mitigation_touch_mode: str = "wick"
    invalidation_mode: str = "close"
    quality_weights: QualityWeights = Field(default_factory=QualityWeights)
```

---

## Loader Function (Planned)

```python
def load_order_block_config(yaml_path: Path | None = None) -> OrderBlockConfig:
    """Load order block configuration from YAML."""
```

Follows the same pattern as `load_market_structure_config()` and `load_market_liquidity_config()`.

---

## Environment Variables

No engine-specific environment variables in Sprint 4.1 spec. Symbol and broker remain in Market Data config (`.env` / `market_data` YAML section).

---

## Example: Development Setup

```yaml
order_block:
  enabled: true
  timeframes:
    - H1
    - H4
  min_candles: 15
  lookback: 80
  zone_mode: wick
  min_displacement_pips: 3.0
  min_impulse_candles: 1
  min_quality_score: 0.3
  require_structure_alignment: false
  use_liquidity_confluence: true
```

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [../../SYSTEM_ARCHITECTURE.md](../../SYSTEM_ARCHITECTURE.md) — Configuration hierarchy
