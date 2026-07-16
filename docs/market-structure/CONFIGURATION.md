# Market Structure Engine — Configuration Guide

---

## YAML (`config/settings.yaml`)

```yaml
market_structure:
  enabled: true
  timeframes:
    - M15
    - H1
    - H4
  swing_lookback: 5
  internal_swing_lookback: 2
  external_swing_lookback: 5
  min_confidence: 0.5
  min_candles: 10

engines:
  market_structure: true
```

---

## Settings Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Engine enabled flag |
| `timeframes` | list | `M15,H1,H4` | Allowed analysis timeframes |
| `swing_lookback` | int | `5` | Bars each side for primary swing detection |
| `internal_swing_lookback` | int | `2` | Minor/internal structure lookback |
| `external_swing_lookback` | int | `5` | Major/external structure lookback |
| `min_confidence` | float | `0.5` | Minimum confidence (0.0–1.0) |
| `min_candles` | int | `10` | Minimum closed candles required |

---

## Field Details

### `swing_lookback`

Number of bars on each side of a pivot required to confirm a swing high or low. Higher values produce fewer, more significant swings.

### `internal_swing_lookback` / `external_swing_lookback`

Dual-layer SMC structure:
- **Internal:** short-term swings within a price leg
- **External:** larger structural swings

### `min_candles`

Analysis rejected with `InsufficientDataError` if fewer closed candles are provided.

### `min_confidence`

When trend confidence falls below this value, evidence notes the threshold but analysis still completes.

### `timeframes`

Only listed timeframes are accepted in `analyze()`. Others raise `UnsupportedTimeframeError`.

---

## Loading Configuration

```python
from backend.engines.market_structure import load_market_structure_config, MarketStructureEngine

config = load_market_structure_config()
engine = MarketStructureEngine(config=config)
```

---

## Example: Development Setup

```yaml
market_structure:
  enabled: true
  timeframes:
    - H1
    - H4
  swing_lookback: 3
  internal_swing_lookback: 1
  external_swing_lookback: 3
  min_confidence: 0.4
  min_candles: 15
```

---

## Dependency on Market Data

Structure engine does not configure MT5 or symbols. Ensure Market Data Engine provides `NormalizedCandle` batches for configured timeframes.
