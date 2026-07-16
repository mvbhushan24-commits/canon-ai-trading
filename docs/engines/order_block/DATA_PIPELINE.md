# Order Block Engine — Data Pipeline

**Engine ID:** `order_block`  
**Sprint:** 4.1 (Architecture specification)  
**Status:** Not implemented

---

## Pipeline Overview

```
NormalizedCandles (Market Data Engine)
        │
        ├──────────────────────────────────┐
        │                                  │
        ▼                                  ▼
MarketStructure                    LiquidityAnalysis
(Market Structure Engine)          (Market Liquidity Engine)
        │                                  │
        └──────────────┬───────────────────┘
                       │
                       ▼
              Order Block Input Validator
                       │
                       ▼
              Order Block Detector
                ├── Origin Detection
                ├── Displacement Validation
                ├── Lifecycle Classification
                └── Quality Scoring
                       │
                       ▼
              OrderBlockAnalysis
                       │
                       ▼
              Order Block Event Publisher
                       │
                       ▼
              Future Engines (Decision, Dashboard)
```

---

## Stage 1 — Market Data Input

**Source:** `MarketDataEngine.load_historical_candles()` or `market.candle.closed` event

**Type:** `list[NormalizedCandle]`

| Field Used | Purpose |
|------------|---------|
| `open`, `high`, `low`, `close` | Origin candle body/wick boundaries |
| `open_time_utc` | Block origin timestamp |
| `is_closed` | Only closed candles used for detection |
| `symbol`, `timeframe` | Analysis scope validation |
| `volume` | Optional displacement strength factor |

**Boundary rule:** Order Block Engine imports `NormalizedCandle` from `backend.engines.market_data` public API only. No MT5 or normalizer imports.

---

## Stage 2 — Market Structure Context

**Source:** `MarketStructureEngine.analyze(candles)` or `analysis.structure.completed` event

**Type:** `MarketStructure`

| Field Used | Purpose |
|------------|---------|
| `current_trend` | Bullish/bearish alignment scoring |
| `swing_highs`, `swing_lows` | Displacement reference levels |
| `bos_events` | Confirm institutional displacement |
| `choch_events` | Counter-trend block weighting |
| `internal_structure` | Minor block detection layer |
| `external_structure` | Major block detection layer |
| `confidence` | Propagate into block quality scoring |

**When missing:** Engine proceeds with reduced confidence; evidence notes `"Structure context unavailable"`.

---

## Stage 3 — Liquidity Context

**Source:** `LiquidityEngine.analyze(candles, structure)` or `analysis.liquidity.completed` event

**Type:** `LiquidityAnalysis`

| Field Used | Purpose |
|------------|---------|
| `sweeps` | Confluence — block near swept liquidity |
| `buy_side_liquidity`, `sell_side_liquidity` | Zone alignment |
| `zones` | Overlap with order block boundaries |
| `bias` | Directional context for block prioritization |

**When missing:** Engine proceeds without liquidity confluence scoring.

---

## Stage 4 — Validation

**Component:** `OrderBlockInputValidator`

| Check | Action on Failure |
|-------|-------------------|
| Empty candle list | Raise `OBE_INSUFFICIENT_DATA` |
| Below `min_candles` | Raise `OBE_INSUFFICIENT_DATA` |
| Mixed symbols/timeframes | Raise `OBE_VALIDATION_FAILED` |
| Invalid OHLC | Raise `OBE_VALIDATION_FAILED` |
| Duplicate timestamps | Raise `OBE_VALIDATION_FAILED` |
| Structure symbol/timeframe mismatch | Raise `OBE_INVALID_STRUCTURE` |
| Liquidity symbol/timeframe mismatch | Raise `OBE_INVALID_LIQUIDITY` |
| Unsupported timeframe | Raise `OBE_TIMEFRAME_UNSUPPORTED` |

---

## Stage 5 — Detection Pipeline

### 5.1 Origin Detection

Identify the last opposing candle before a displacement move:

| Direction | Origin Rule (Conceptual) |
|-----------|-------------------------|
| **Bullish OB** | Last bearish (or down-close) candle before bullish displacement |
| **Bearish OB** | Last bullish (or up-close) candle before bearish displacement |

Origin zone bounds derived from origin candle body and/or wick per configuration (`zone_mode`: `body`, `wick`, `full`).

### 5.2 Displacement Validation

Confirm the move after the origin candle meets displacement criteria:

- Minimum pip/body size (`min_displacement_pips`)
- Minimum consecutive impulse candles (`min_impulse_candles`)
- Optional structure break confirmation (BOS in displacement direction)

### 5.3 Lifecycle Classification

| Status | Condition (Conceptual) |
|--------|------------------------|
| **Fresh** | Price has not returned to the block zone since formation |
| **Mitigated** | Price re-entered the zone but did not close beyond invalidation boundary |
| **Invalidated** | Price closed beyond the far boundary of the block in the opposing direction |

Lifecycle evaluated on each analysis cycle against latest closed candles.

### 5.4 Quality Scoring

Composite score (0.0–1.0) from:

| Factor | Weight (Configurable) |
|--------|----------------------|
| Displacement magnitude | High |
| Structure trend alignment | High |
| BOS confirmation | Medium |
| Liquidity sweep confluence | Medium |
| Block age / freshness | Low |

---

## Stage 6 — Output Assembly

**Type:** `OrderBlockAnalysis`

Partitioned views:

```
order_blocks          → all blocks (any status)
fresh_blocks          → status == fresh
mitigated_blocks      → status == mitigated
invalidated_blocks    → status == invalidated
```

Timeline events appended to `events` list and published via publisher.

---

## Stage 7 — Event Publishing

See [EVENTS.md](./EVENTS.md) for complete event catalog.

---

## ASCII Data Flow

```
 MT5 ──► MDE ──► NormalizedCandle[]
                    │
         ┌──────────┼──────────┐
         ▼          ▼          ▼
        MSE        LQE      (candles)
         │          │          │
         ▼          ▼          │
  MarketStructure  LiquidityAnalysis
         │          │          │
         └────┬─────┘          │
              ▼                │
         Order Block Engine ◄──┘
              │
              ▼
      OrderBlockAnalysis
              │
              ▼
         OBE Events
```

---

## Orchestration Pattern (Future)

```python
# Conceptual — not implemented in Sprint 4.1
candles = market_data_engine.load_historical_candles(timeframe="H1")
structure = structure_engine.analyze(candles, timeframe="H1")
liquidity = liquidity_engine.analyze(candles, structure, timeframe="H1")
ob_analysis = order_block_engine.analyze(candles, structure, liquidity, timeframe="H1")
```

---

## Data Retention

| Data | Retention |
|------|-----------|
| Active blocks | Held in `OrderBlockState` across calls |
| Invalidated blocks | Configurable expiry (`max_block_age_bars`) |
| Event history | Published only — not persisted in Sprint 4.1 spec |

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [EVENTS.md](./EVENTS.md)
