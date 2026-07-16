# Fair Value Gap Engine — Data Pipeline

**Engine ID:** `fair_value_gap`  
**Sprint:** 5.1 (Architecture specification)  
**Status:** Not implemented

---

## Pipeline Overview

```
NormalizedCandles (Market Data Engine)
        │
        ├──────────────────────────────────────────────────┐
        │                          │                       │
        ▼                          ▼                       ▼
MarketStructure          LiquidityState          OrderBlockState
(Market Structure)       (Market Liquidity)      (Order Block)
        │                          │                       │
        └──────────────┬───────────┴───────────────────────┘
                       │
                       ▼
              Fair Value Gap Input Validator
                       │
                       ▼
              Fair Value Gap Detector
                ├── Formation Detection (3-candle pattern)
                ├── Boundary & CE Computation
                ├── Validity Filtering
                ├── Lifecycle Classification
                ├── Fill Tracking (partial / full)
                ├── Mitigation Detection
                ├── Premium / Discount Classification
                ├── Nested FVG Resolution
                ├── MTF Alignment Scoring
                └── Quality Scoring
                       │
                       ▼
              FairValueGapAnalysis
                       │
                       ▼
              Fair Value Gap Event Publisher
                       │
                       ▼
              Future Engines (Breaker, Decision, Dashboard)
```

---

## Stage 1 — Market Data Input

**Source:** `MarketDataEngine.load_historical_candles()` or `market.candle.closed` event

**Type:** `list[NormalizedCandle]`

| Field Used | Purpose |
|------------|---------|
| `open`, `high`, `low`, `close` | Three-candle pattern boundaries |
| `open_time_utc` | Gap origin timestamp (middle candle) |
| `is_closed` | Only closed candles used for detection |
| `symbol`, `timeframe` | Analysis scope validation |
| `volume` | Optional impulse strength factor |

**Boundary rule:** Fair Value Gap Engine imports `NormalizedCandle` from `backend.engines.market_data` public API only. No MT5 or normalizer imports.

---

## Stage 2 — Market Structure Context

**Source:** `MarketStructureEngine.analyze(candles)` or `analysis.structure.completed` event

**Type:** `MarketStructure`

| Field Used | Purpose |
|------------|---------|
| `current_trend` | Bullish/bearish alignment scoring |
| `swing_highs`, `swing_lows` | Dealing range bounds for premium/discount |
| `higher_highs`, `higher_lows`, `lower_highs`, `lower_lows` | Range extremity selection |
| `bos_events` | Confirm displacement in gap direction |
| `choch_events` | Counter-trend gap weighting |
| `internal_structure`, `external_structure` | Range selection for premium/discount |
| `confidence` | Propagate into gap quality scoring |

**When missing:** Engine proceeds with reduced confidence; `premium_discount` defaults to `equilibrium`; evidence notes `"Structure context unavailable"`.

---

## Stage 3 — Liquidity State Context

**Source:** Extracted from `LiquidityAnalysis.state` or prior `LiquidityEngine` invocation

**Type:** `LiquidityState`

| Field Used | Purpose |
|------------|---------|
| `active_zones` | Confluence — gap near or overlapping liquidity zone |
| `recent_sweeps` | Confluence — gap formed after liquidity sweep |
| `bar_count` | Consistency validation with candle batch |

**When missing:** Engine proceeds without liquidity confluence scoring; `liquidity_confluence` defaults to `false`.

### Extraction Pattern (Orchestrator)

```python
# Conceptual — orchestrator responsibility, not FVG engine internals
liquidity_analysis = liquidity_engine.analyze(candles, structure, timeframe="H1")
liquidity_state = liquidity_analysis.state
```

The FVG Engine receives `LiquidityState` directly. It does not call the Liquidity Engine.

---

## Stage 4 — Order Block State Context

**Source:** Extracted from `OrderBlockAnalysis.state` or prior `OrderBlockEngine` invocation

**Type:** `OrderBlockState`

| Field Used | Purpose |
|------------|---------|
| `active_blocks` | Confluence — gap overlaps active order block zone |
| `last_analysis_utc` | Freshness check for confluence |
| `bar_count` | Consistency validation with candle batch |

**When missing:** Engine proceeds without order block confluence scoring; `order_block_confluence` defaults to `false`.

### Extraction Pattern (Orchestrator)

```python
# Conceptual — orchestrator responsibility
ob_analysis = order_block_engine.analyze(candles, structure, liquidity_analysis, timeframe="H1")
order_block_state = ob_analysis.state
```

The FVG Engine receives `OrderBlockState` directly. It does not call the Order Block Engine.

---

## Stage 5 — Validation

**Component:** `FairValueGapInputValidator`

| Check | Action on Failure |
|-------|-------------------|
| Empty candle list | Raise `FVE_INSUFFICIENT_DATA` |
| Below `min_candles` | Raise `FVE_INSUFFICIENT_DATA` |
| Mixed symbols/timeframes | Raise `FVE_VALIDATION_FAILED` |
| Invalid OHLC | Raise `FVE_VALIDATION_FAILED` |
| Duplicate timestamps | Raise `FVE_VALIDATION_FAILED` |
| Structure symbol/timeframe mismatch | Raise `FVE_INVALID_STRUCTURE` |
| Liquidity state bar count mismatch | Raise `FVE_INVALID_LIQUIDITY_STATE` |
| Order block state bar count mismatch | Raise `FVE_INVALID_ORDER_BLOCK_STATE` |
| Unsupported timeframe | Raise `FVE_TIMEFRAME_UNSUPPORTED` |

---

## Stage 6 — Detection Pipeline

### 6.1 Formation Detection

Identify three-candle imbalance patterns:

| Direction | Formation Rule (Conceptual) |
|-----------|----------------------------|
| **Bullish FVG** | Candle A high < Candle C low (gap between non-overlapping wicks) |
| **Bearish FVG** | Candle A low > Candle C high (gap between non-overlapping wicks) |

Candle B is the impulse (middle) candle. Formation indices stored as `candle_a_index`, `candle_b_index`, `candle_c_index`.

### 6.2 Boundary & CE Computation

| Output Field | Computation |
|--------------|-------------|
| `high`, `low` | Unfilled price range from formation candles |
| `ce_price` | `(high + low) / 2` |
| `gap_size` | `high - low` |
| `gap_size_pips` | `gap_size / pip_size` |

### 6.3 Validity Filtering

| Filter | Rejection Reason |
|--------|-----------------|
| `gap_size_pips < min_gap_size_pips` | Gap too small |
| Duplicate bar indices in active state | Already tracked |
| Middle candle fails impulse criteria | Insufficient displacement |
| Optional structure alignment gate | Counter-trend gap |

### 6.4 Lifecycle Classification

| Status | Condition (Conceptual) |
|--------|------------------------|
| **Open** | Price has not entered `[low, high]` since formation |
| **Partial** | Price entered gap; `fill_percent < full_fill_threshold` |
| **Filled** | Price traversed gap per `fill_mode` |
| **Mitigated** | CE touched or `mitigation_fill_percent` reached |
| **Invalidated** | Close beyond far boundary in opposing direction |
| **Expired** | Age exceeds `max_gap_age_bars` |

Lifecycle evaluated on each analysis cycle against latest closed candles.

### 6.5 Fill Tracking

| Phase | Trigger (Configurable) |
|-------|------------------------|
| Entry detection | Wick/body/close enters gap per `entry_touch_mode` |
| Fill percent update | Depth of penetration from entry side |
| CE encroachment | Price touches `ce_price` |
| Full fill | Far boundary reached per `fill_mode` |

### 6.6 Mitigation Detection

| Mode | Trigger |
|------|---------|
| `ce` | CE price touched |
| `partial` | `fill_percent >= mitigation_fill_percent` |
| `full_fill` | Status transitions to `filled` |

### 6.7 Premium / Discount Classification

```
dealing_range_high = latest relevant swing high (from MarketStructure)
dealing_range_low  = latest relevant swing low (from MarketStructure)
equilibrium        = (dealing_range_high + dealing_range_low) / 2

classify gap.ce_price relative to equilibrium ± equilibrium_tolerance_pips
```

### 6.8 Nested FVG Resolution

After primary detection, compare all active gaps:

```
if child.low >= parent.low and child.high <= parent.high
   and child.gap_id != parent.gap_id:
       child.nested_parent_gap_id = parent.gap_id
       parent.nested_child_gap_ids.append(child.gap_id)
```

Smaller gaps formed later on the same timeframe take child role when contained.

### 6.9 MTF Alignment Scoring

When `higher_timeframe_gaps` provided:

| Criterion | Weight |
|-----------|--------|
| Direction match | Required |
| Zone overlap (any intersection) | Required |
| HTF gap status is open or partial | Required |
| Alignment score | Proportional to overlap percentage |

### 6.10 Quality Scoring

Composite score (0.0–1.0) from configurable weights. See [CONFIGURATION.md](./CONFIGURATION.md) for weight defaults.

---

## Stage 7 — Output Assembly

**Type:** `FairValueGapAnalysis`

Partitioned views:

```
fair_value_gaps     → all gaps (any status)
open_gaps           → status == open
partial_gaps        → status == partial
filled_gaps         → status == filled
mitigated_gaps      → status == mitigated
invalidated_gaps    → status == invalidated
expired_gaps        → status == expired
bullish_gaps        → direction == bullish
bearish_gaps        → direction == bearish
```

Timeline events appended to `events` list and published via publisher.

Continuity state updated:

```
state.active_gaps   → gaps with status in (open, partial)
state.bar_count     → incremented by candles processed
```

---

## Stage 8 — Event Publishing

See [EVENTS.md](./EVENTS.md) for complete event catalog.

---

## Multi-Timeframe Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (Future)                     │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    H4 Analysis           H1 Analysis          M15 Analysis
    (no HTF input)    (higher_timeframe_gaps    (higher_timeframe_gaps
                         = H4 gaps)                = H1 + H4 gaps)
         │                    │                    │
         ▼                    ▼                    ▼
   H4 FVG Analysis      H1 FVG Analysis       M15 FVG Analysis
```

MTF alignment requires the orchestrator to run higher timeframes first and pass `higher_timeframe_gaps` into lower timeframe calls.

---

## ASCII Data Flow

```
 MT5 ──► MDE ──► NormalizedCandle[]
                    │
         ┌──────────┼──────────┬──────────┐
         ▼          ▼          ▼          ▼
        MSE    LiquidityState  OB State  (candles)
         │          │          │          │
         ▼          ▼          ▼          │
  MarketStructure   │          │          │
         │          │          │          │
         └────┬─────┴────┬─────┘          │
              ▼          ▼                │
         Fair Value Gap Engine ◄─────────┘
              │
              ▼
      FairValueGapAnalysis
              │
              ▼
         FVE Events
```

---

## Orchestration Pattern (Future)

```python
# Conceptual — not implemented in Sprint 5.1
candles = market_data_engine.load_historical_candles(timeframe="H1")
structure = structure_engine.analyze(candles, timeframe="H1")
liquidity_analysis = liquidity_engine.analyze(candles, structure, timeframe="H1")
ob_analysis = order_block_engine.analyze(
    candles, structure, liquidity_analysis, timeframe="H1"
)

# Extract state objects per Sprint 5.1 input contract
liquidity_state = liquidity_analysis.state
order_block_state = ob_analysis.state

# Optional MTF: run H4 first
h4_gaps = fvg_engine.analyze(h4_candles, h4_structure, timeframe="H4").fair_value_gaps

fvg_analysis = fvg_engine.analyze(
    candles,
    structure,
    liquidity_state=liquidity_state,
    order_block_state=order_block_state,
    timeframe="H1",
    higher_timeframe_gaps=h4_gaps,
)
```

---

## Data Retention

| Data | Retention |
|------|-----------|
| Active gaps | Held in `FairValueGapState.active_gaps` across calls |
| Filled/mitigated gaps | Removed from active state; retained in partitioned output lists |
| Invalidated/expired gaps | Configurable retention via `max_gap_age_bars` |
| Event history | Published only — not persisted in Sprint 5.1 spec |

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [EVENTS.md](./EVENTS.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
