# Breaker Block Engine — Data Pipeline

**Engine ID:** `market_breaker`  
**Sprint:** 6.1 (Architecture specification)  
**Status:** Not implemented

---

## Pipeline Overview

```
NormalizedCandles (Market Data Engine)
        │
        ├──────────────────────────────────────────────────────────┐
        │                          │                               │
        ▼                          ▼                               ▼
MarketStructure          LiquidityState              invalidated_order_blocks
(Market Structure)       (Market Liquidity)          (Order Block Engine)
        │                          │                               │
        │                          │                               │
        │                  FairValueGapState                         │
        │                  (Fair Value Gap Engine)                   │
        │                          │                               │
        └──────────────────────────┼───────────────────────────────┘
                                   │
                                   ▼
                        Breaker Block Input Validator
                                   │
                                   ▼
                        Breaker Block Detector
                          ├── Formation Detection (from invalidated OBs/FVGs)
                          ├── Confirmation Validation
                          ├── Lifecycle Classification
                          ├── Mitigation Tracking
                          ├── Confluence Scoring (Liquidity + FVG)
                          └── Quality Scoring
                                   │
                                   ▼
                        BreakerBlockAnalysis
                                   │
                                   ▼
                        Breaker Block Event Publisher
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
| `open`, `high`, `low`, `close` | Confirmation, mitigation, and invalidation evaluation |
| `open_time_utc` | Breaker formation and confirmation timestamps |
| `is_closed` | Only closed candles used for detection |
| `symbol`, `timeframe` | Analysis scope validation |
| `volume` | Optional confirmation strength factor |

**Boundary rule:** Breaker Block Engine imports `NormalizedCandle` from `backend.engines.market_data` public API only. No MT5 or normalizer imports.

---

## Stage 2 — Market Structure Context

**Source:** `MarketStructureEngine.analyze(candles)` or `analysis.structure.completed` event

**Type:** `MarketStructure`

| Field Used | Purpose |
|------------|---------|
| `current_trend` | Breaker direction alignment scoring |
| `swing_highs`, `swing_lows` | Dealing range for premium/discount |
| `bos_events` | Confirm invalidation displacement |
| `choch_events` | Counter-trend breaker weighting |
| `internal_structure` | Minor breaker detection layer |
| `external_structure` | Major breaker detection layer |
| `confidence` | Propagate into breaker quality scoring |

**When missing:** Engine proceeds with reduced confidence; evidence notes `"Structure context unavailable"`.

---

## Stage 3 — Liquidity Context

**Source:** `LiquidityEngine.analyze(candles, structure)` or `analysis.liquidity.completed` event

**Type:** `LiquidityState` (extracted by caller — not full `LiquidityAnalysis`)

| Field Used | Purpose |
|------------|---------|
| `active_zones` | Zone overlap confluence |
| `recent_sweeps` | Post-sweep breaker confluence |
| `bar_count` | Consistency validation |

**When missing:** Engine proceeds without liquidity confluence scoring; `liquidity_confluence` defaults to `false`.

---

## Stage 4 — Invalidated Order Blocks

**Source:** `OrderBlockEngine.analyze(candles, structure, liquidity)` → extract `invalidated_blocks`

**Type:** `list[OrderBlock]`

| Field Used | Purpose |
|------------|---------|
| `block_id` | Source reference (`source_id`) |
| `direction` | Pre-flip direction for polarity mapping |
| `high`, `low` | Breaker zone boundaries |
| `invalidation_bar_index` | Formation anchor |
| `origin_time_utc` | Historical context |
| `strength`, `quality` | Source quality factor in scoring |
| `structure_alignment` | Inherited alignment evidence |
| `liquidity_confluence` | Inherited confluence evidence |

**Validation:** All blocks must have `status == invalidated`. Non-invalidated blocks in this input raise `MBE_INVALID_ORDER_BLOCKS`.

**When empty:** Engine returns empty breaker lists with `bias: undetermined` — valid outcome per Constitution.

---

## Stage 5 — Fair Value Gap Context (Optional)

**Source:** `FairValueGapEngine.analyze(...)` → extract `state` and optionally `invalidated_gaps`

**Types:** `FairValueGapState`, `list[FairValueGap]` (invalidated)

| Field Used | Purpose |
|------------|---------|
| `FairValueGapState.active_gaps` | FVG overlap confluence with open/partial gaps |
| `invalidated_fvgs` | Optional FVG-derived breaker formation when `fvg_breaker_enabled=true` |
| `bar_count` | Consistency validation |

**When missing:** Engine proceeds without FVG confluence; `fvg_confluence` defaults to `false`.

---

## Stage 6 — Validation

**Component:** `BreakerBlockInputValidator`

| Check | Action on Failure |
|-------|-------------------|
| Empty candle list | Raise `MBE_INSUFFICIENT_DATA` |
| Below `min_candles` | Raise `MBE_INSUFFICIENT_DATA` |
| Mixed symbols/timeframes | Raise `MBE_VALIDATION_FAILED` |
| Invalid OHLC | Raise `MBE_VALIDATION_FAILED` |
| Duplicate timestamps | Raise `MBE_VALIDATION_FAILED` |
| Structure symbol/timeframe mismatch | Raise `MBE_INVALID_STRUCTURE` |
| Liquidity state bar count mismatch | Raise `MBE_INVALID_LIQUIDITY_STATE` |
| Non-invalidated blocks in input | Raise `MBE_INVALID_ORDER_BLOCKS` |
| FVG state bar count mismatch | Raise `MBE_INVALID_FVG_STATE` |
| Unsupported timeframe | Raise `MBE_TIMEFRAME_UNSUPPORTED` |
| Duplicate breaker ID in prior state | Raise `MBE_DUPLICATE_BREAKER` |

---

## Stage 7 — Detection Pipeline

### 7.1 Formation Detection

Derive breaker candidates from invalidated source zones:

| Source | Polarity Flip Rule |
|--------|-------------------|
| **Invalidated bullish OB** | `direction` → `bearish` breaker (failed demand → supply) |
| **Invalidated bearish OB** | `direction` → `bullish` breaker (failed supply → demand) |
| **Invalidated bullish FVG** (optional) | `direction` → `bearish` breaker |
| **Invalidated bearish FVG** (optional) | `direction` → `bullish` breaker |

Zone bounds inherit from source `[low, high]`. One breaker per unique `source_id`.

### 7.2 Confirmation Validation

Evaluate whether price has retested the zone after invalidation:

| Direction | Retest Expectation |
|-----------|-------------------|
| Bullish breaker | Price returns down into zone from above |
| Bearish breaker | Price returns up into zone from below |

Confirmation mode and gates defined in [CONFIGURATION.md](./CONFIGURATION.md).

### 7.3 Lifecycle Classification

| Status | Condition (Conceptual) |
|--------|------------------------|
| **Candidate** | Registered from invalidated source; no retest yet |
| **Confirmed** | Retest validated per confirmation rules |
| **Mitigated** | Zone addressed per mitigation rules |
| **Invalidated** | Breaker role negated by opposing close |
| **Expired** | Age exceeds `max_breaker_age_bars` |

Lifecycle evaluated on each analysis cycle against latest closed candles and merged with `prior_state`.

### 7.4 Mitigation Tracking

Monitor confirmed breakers for zone interaction:

- Wick/body/close entry per `mitigation_mode`
- Partial traverse per `mitigation_percent`
- Distinct from invalidation — breaker played institutional role

### 7.5 Confluence Scoring

**Liquidity confluence** (`ConfluenceScorer.score_liquidity`):

- Overlap with `LiquidityState.active_zones`
- Proximity to `LiquidityState.recent_sweeps` within `liquidity_proximity_pips`

**FVG confluence** (`ConfluenceScorer.score_fvg`):

- Overlap with open/partial gaps from `FairValueGapState.active_gaps`
- CE proximity within `fvg_ce_proximity_pips`

### 7.6 Quality Scoring

Composite score (0.0–1.0) from configurable weights. See [ARCHITECTURE.md](./ARCHITECTURE.md) for factor table.

Breakers below `min_quality_score` excluded from partitioned output lists.

---

## Stage 8 — Output Assembly

**Type:** `BreakerBlockAnalysis`

Partitioned views:

```
breaker_blocks          → all breakers (any status)
candidate_breakers      → status == candidate
confirmed_breakers      → status == confirmed
mitigated_breakers      → status == mitigated
invalidated_breakers    → status == invalidated
expired_breakers        → status == expired
bullish_breakers        → direction == bullish
bearish_breakers        → direction == bearish
```

Timeline events appended to `events` list and published via publisher.

Continuity state updated in `state.active_breakers` (candidate + confirmed only).

---

## Stage 9 — Event Publishing

See [EVENTS.md](./EVENTS.md) for complete event catalog.

---

## ASCII Data Flow

```
 MT5 ──► MDE ──► NormalizedCandle[]
                    │
         ┌──────────┼──────────┬──────────────┐
         ▼          ▼          ▼              ▼
        MSE        LQE        OBE           FVE
         │          │          │              │
         ▼          ▼          ▼              ▼
  MarketStructure  LiquidityState  invalidated_blocks  FairValueGapState
         │          │          │              │
         └──────────┴──────────┴──────────────┘
                              │
                              ▼
                    Breaker Block Engine
                              │
                              ▼
                    BreakerBlockAnalysis
                              │
                              ▼
                         MBE Events
```

---

## Orchestration Pattern (Future)

```python
# Conceptual — not implemented in Sprint 6.1
candles = market_data_engine.load_historical_candles(timeframe="H1")
structure = structure_engine.analyze(candles, timeframe="H1")
liquidity_analysis = liquidity_engine.analyze(candles, structure, timeframe="H1")
ob_analysis = order_block_engine.analyze(candles, structure, liquidity_analysis, timeframe="H1")
fvg_analysis = fvg_engine.analyze(
    candles, structure,
    liquidity_state=liquidity_analysis.state,
    order_block_state=ob_analysis.state,
    timeframe="H1",
)
breaker_analysis = breaker_engine.analyze(
    candles,
    structure,
    invalidated_order_blocks=ob_analysis.invalidated_blocks,
    liquidity_state=liquidity_analysis.state,
    fair_value_gap_state=fvg_analysis.state,
    invalidated_fvgs=fvg_analysis.invalidated_gaps,
    timeframe="H1",
)
```

---

## State Merge Strategy

On each analysis cycle:

1. Load `prior_state.active_breakers` from previous invocation
2. Register new candidates from newly invalidated blocks not yet tracked
3. Update lifecycle status of existing breakers against latest candles
4. Remove mitigated, invalidated, and expired breakers from `active_breakers`
5. Persist updated `BreakerBlockState` in output

| Merge Rule | Behavior |
|------------|----------|
| Same `source_id` | Update existing breaker; do not duplicate |
| New invalidation | Create candidate if within lookback |
| Stale candidate | Expire if beyond `max_bars_after_invalidation` |
| Bar count | Increment `state.bar_count` by new closed candles |

---

## Data Retention

| Data | Retention |
|------|-----------|
| Active breakers | Held in `BreakerBlockState` across calls (candidate + confirmed) |
| Mitigated/invalidated/expired | Partitioned in analysis output; removed from active state |
| Event history | Published only — not persisted in Sprint 6.1 spec |

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [EVENTS.md](./EVENTS.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
