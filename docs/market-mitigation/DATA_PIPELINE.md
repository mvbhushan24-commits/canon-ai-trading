# Mitigation Block Engine — Data Pipeline

**Engine ID:** `market_mitigation`  
**Sprint:** 7.1 (Architecture specification)  
**Status:** Not implemented

---

## Pipeline Overview

```
NormalizedCandles (Market Data Engine)
        │
        ├──────────────────────────────────────────────────────────────────┐
        │              │              │              │                     │
        ▼              ▼              ▼              ▼                     ▼
MarketStructure  LiquidityState  order_blocks  FairValueGapState  breaker_blocks
(Market Structure) (Market Liquidity) (Order Block) (Fair Value Gap) (Breaker Block)
        │              │              │              │                     │
        │              │              │              │                     │
        │              │              │              │              htf_mitigation_blocks
        │              │              │              │              (optional HTF context)
        └──────────────┴──────────────┴──────────────┴─────────────────────┘
                                   │
                                   ▼
                        Mitigation Block Input Validator
                                   │
                                   ▼
                        Mitigation Block Detector
                          ├── Formation Detection (displacement + confluence)
                          ├── Touch Tracking (partial / full / multi-touch)
                          ├── Confirmation Validation
                          ├── Lifecycle Classification
                          ├── Nesting Detection
                          ├── Structure Scope Classification
                          ├── MTF Alignment (HTF / LTF)
                          ├── Confluence Scoring (Liquidity + OB + FVG + Breaker)
                          └── Quality Scoring
                                   │
                                   ▼
                        MitigationBlockAnalysis
                                   │
                                   ▼
                        Mitigation Block Event Publisher
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
| `open`, `high`, `low`, `close` | Displacement detection, opposing candle identification, touch evaluation |
| `open_time_utc` | Block formation and touch timestamps |
| `is_closed` | Only closed candles used for detection |
| `symbol`, `timeframe` | Analysis scope validation |
| `volume` | Optional displacement strength factor |

**Boundary rule:** Mitigation Block Engine imports `NormalizedCandle` from `backend.engines.market_data` public API only. No MT5 or normalizer imports.

---

## Stage 2 — Market Structure Context

**Source:** `MarketStructureEngine.analyze(candles)` or `analysis.structure.completed` event

**Type:** `MarketStructure`

| Field Used | Purpose |
|------------|---------|
| `current_trend` | Block direction alignment scoring |
| `swing_highs`, `swing_lows` | Dealing range for premium/discount |
| `internal_structure` | Internal scope classification |
| `external_structure` | External scope classification |
| `bos_events` | Displacement validation anchor |
| `choch_events` | Optional invalidation trigger |
| `confidence` | Propagate into block quality scoring |

**When missing:** Engine proceeds with reduced confidence; `structure_scope` defaults to `undetermined`; evidence notes `"Structure context unavailable"`.

---

## Stage 3 — Liquidity Context

**Source:** `LiquidityEngine.analyze(candles, structure)` or `analysis.liquidity.completed` event

**Type:** `LiquidityState` (extracted by caller — not full `LiquidityAnalysis`)

| Field Used | Purpose |
|------------|---------|
| `active_zones` | Zone overlap confluence |
| `recent_sweeps` | Post-sweep mitigation confluence |
| `bar_count` | Consistency validation |

**When missing:** Engine proceeds without liquidity confluence scoring; `liquidity_confluence` defaults to `false`.

---

## Stage 4 — Order Block Context

**Source:** `OrderBlockEngine.analyze(candles, structure, liquidity)` → extract `order_blocks` or partitioned lists

**Type:** `list[OrderBlock]`

| Field Used | Purpose |
|------------|---------|
| `block_id` | Confluence reference and nesting parent ID |
| `direction` | Confluence direction alignment |
| `high`, `low` | Nesting containment and overlap scoring |
| `status` | Prefer `fresh` blocks for confluence; include `mitigated` for nesting context |
| `strength`, `quality` | Confluence quality factor |
| `origin_bar_index` | Temporal proximity to displacement |

**When missing:** Engine proceeds without order block confluence; standalone displacement blocks still detected.

---

## Stage 5 — Fair Value Gap Context (Optional)

**Source:** `FairValueGapEngine.analyze(...)` → extract `state`

**Type:** `FairValueGapState`

| Field Used | Purpose |
|------------|---------|
| `active_gaps` | FVG overlap confluence with open/partial gaps |
| `bar_count` | Consistency validation |

**When missing:** Engine proceeds without FVG confluence; `fvg_confluence` defaults to `false`.

---

## Stage 6 — Breaker Block Context (Optional)

**Source:** `BreakerBlockEngine.analyze(...)` → extract `breaker_blocks` or confirmed partition

**Type:** `list[BreakerBlock]`

| Field Used | Purpose |
|------------|---------|
| `breaker_id` | Confluence reference and nesting parent ID |
| `direction` | Confluence direction alignment |
| `high`, `low` | Nesting containment and overlap scoring |
| `status` | Prefer `confirmed` and `candidate` for confluence |
| `strength`, `quality` | Confluence quality factor |
| `source_id` | Upstream lineage for evidence |

**When missing:** Engine proceeds without breaker confluence; `breaker_confluence` defaults to `false`.

---

## Stage 7 — HTF Mitigation Context (Optional)

**Source:** Caller-provided higher-timeframe `MitigationBlockAnalysis` from prior HTF analysis cycle

**Type:** `list[MitigationBlock]`

| Field Used | Purpose |
|------------|---------|
| `block_id` | HTF alignment reference |
| `direction` | Direction match validation |
| `high`, `low` | Overlap scoring |
| `status` | Prefer `fresh`, `partial`, `confirmed` HTF blocks |
| `strength` | HTF alignment weight in quality scoring |

**When missing:** Engine proceeds without HTF alignment; `htf_aligned` defaults to `false`.

---

## Stage 8 — Validation

**Component:** `MitigationBlockInputValidator`

| Check | Action on Failure |
|-------|-------------------|
| Empty candle list | Raise `MMBE_INSUFFICIENT_DATA` |
| Below `min_candles` | Raise `MMBE_INSUFFICIENT_DATA` |
| Mixed symbols/timeframes | Raise `MMBE_VALIDATION_FAILED` |
| Invalid OHLC | Raise `MMBE_VALIDATION_FAILED` |
| Duplicate timestamps | Raise `MMBE_VALIDATION_FAILED` |
| Structure symbol/timeframe mismatch | Raise `MMBE_INVALID_STRUCTURE` |
| Liquidity state bar count mismatch | Raise `MMBE_INVALID_LIQUIDITY_STATE` |
| Order blocks scope mismatch | Raise `MMBE_INVALID_ORDER_BLOCKS` |
| FVG state bar count mismatch | Raise `MMBE_INVALID_FVG_STATE` |
| Breaker blocks scope mismatch | Raise `MMBE_INVALID_BREAKER_BLOCKS` |
| HTF blocks invalid bounds | Raise `MMBE_INVALID_HTF_BLOCKS` |
| Unsupported timeframe | Raise `MMBE_TIMEFRAME_UNSUPPORTED` |
| Duplicate block ID in prior state | Raise `MMBE_DUPLICATE_BLOCK` |

---

## Stage 9 — Detection Pipeline

### 9.1 Formation Detection

Derive mitigation block candidates from displacement legs:

| Direction | Opposing Candle | Displacement |
|-----------|-----------------|--------------|
| **Bullish MB** | Last bearish candle before bullish leg | Close-to-close or range >= `min_displacement_pips` |
| **Bearish MB** | Last bullish candle before bearish leg | Close-to-close or range >= `min_displacement_pips` |

Zone bounds derived per `zone_bound_mode`:

| Mode | Zone Bounds |
|------|-------------|
| `body` | Candle open to close (opposing direction) |
| `wick` | Full candle high to low |
| `full_candle` | Same as wick with body emphasis in scoring |

Secondary formation path: confluence-derived blocks when a displacement leg overlaps an upstream OB/FVG/Breaker zone (produces nested relationship).

### 9.2 Touch Tracking

Monitor active blocks for price interaction on each new closed candle:

| Interaction | Effect |
|-------------|--------|
| First wick entry | `fresh` → `partial`; `touch_count = 1` |
| Additional entry (distinct bar) | Increment `touch_count`; emit `MultiTouchMitigationBlock` |
| Cumulative traverse | Update `mitigation_percent` |
| Full traverse | Transition toward `used` |

Touch deduplication: same bar does not increment `touch_count` twice. Minimum `min_bars_between_touches` separates distinct touches.

### 9.3 Confirmation Validation

| Direction | Touch Expectation |
|-----------|-------------------|
| Bullish MB | Price returns down into zone — demand mitigation |
| Bearish MB | Price returns up into zone — supply mitigation |

Confirmation mode and gates defined in [CONFIGURATION.md](./CONFIGURATION.md).

### 9.4 Lifecycle Classification

| Status | Condition (Conceptual) |
|--------|------------------------|
| **Fresh** | Registered; no price interaction |
| **Partial** | Zone partially addressed |
| **Confirmed** | Confirmation rules satisfied |
| **Used** | Full mitigation per rules |
| **Invalidated** | Opposing boundary break |
| **Expired** | Age exceeds `max_block_age_bars` |

Lifecycle evaluated on each analysis cycle against latest closed candles and merged with `prior_state`.

### 9.5 Nesting Detection

For each block, evaluate containment against upstream zones and other active blocks:

```
if block.bounds ⊆ parent.bounds (≥ nest_overlap_min_percent):
    is_nested = true
    parent_zone_id = parent.id
    parent_zone_type = parent.type
```

### 9.6 Structure Scope Classification

| Scope | Criterion |
|-------|-----------|
| `internal` | Block midpoint within internal structure dealing range |
| `external` | Block midpoint within external structure dealing range |
| `undetermined` | Structure unavailable or midpoint outside both ranges |

### 9.7 MTF Alignment

**HTF:** Overlap LTF block with provided HTF blocks; score direction match and zone overlap.

**LTF:** When caller provides LTF blocks, detect containment within current block zone.

### 9.8 Confluence Scoring

**Liquidity** — overlap with `LiquidityState.active_zones` or sweep proximity within `liquidity_proximity_pips`.

**Order block** — overlap with fresh OB zones; direction alignment bonus.

**FVG** — overlap with open/partial gaps; CE proximity within `fvg_ce_proximity_pips`.

**Breaker** — overlap with confirmed/candidate breakers.

### 9.9 Quality Scoring

Composite score (0.0–1.0) from configurable weights. See [ARCHITECTURE.md](./ARCHITECTURE.md) for factor table.

Blocks below `min_quality_score` excluded from partitioned output lists.

---

## Stage 10 — Output Assembly

**Type:** `MitigationBlockAnalysis`

Partitioned views:

```
mitigation_blocks     → all blocks (any status)
fresh_blocks          → status == fresh
partial_blocks        → status == partial
confirmed_blocks      → status == confirmed
used_blocks           → status == used
invalidated_blocks    → status == invalidated
expired_blocks        → status == expired
bullish_blocks        → direction == bullish
bearish_blocks        → direction == bearish
nested_blocks         → is_nested == true
internal_blocks       → structure_scope == internal
external_blocks       → structure_scope == external
htf_aligned_blocks    → htf_aligned == true
```

Timeline events appended to `events` list and published via publisher.

Continuity state updated in `state.active_blocks` (fresh + partial + confirmed only).

---

## Stage 11 — Event Publishing

See [EVENTS.md](./EVENTS.md) for complete event catalog.

---

## ASCII Data Flow

```
 MT5 ──► MDE ──► NormalizedCandle[]
                    │
         ┌──────────┼──────────┬──────────┬──────────┐
         ▼          ▼          ▼          ▼          ▼
        MSE        LQE        OBE        FVE        MBE
         │          │          │          │          │
         ▼          ▼          ▼          ▼          ▼
  MarketStructure  LiquidityState  order_blocks  FairValueGapState  breaker_blocks
         │          │          │          │          │
         └──────────┴──────────┴──────────┴──────────┘
                              │
                              ▼
                    Mitigation Block Engine
                              │
                              ▼
                    MitigationBlockAnalysis
                              │
                              ▼
                         MMBE Events
```

---

## Orchestration Pattern (Future)

```python
# Conceptual — not implemented in Sprint 7.1
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
    timeframe="H1",
)
htf_mitigation = mitigation_engine.analyze(
    htf_candles, htf_structure, ...,
    timeframe="H4",
)
mitigation_analysis = mitigation_engine.analyze(
    candles,
    structure,
    order_blocks=ob_analysis.order_blocks,
    liquidity_state=liquidity_analysis.state,
    fair_value_gap_state=fvg_analysis.state,
    breaker_blocks=breaker_analysis.confirmed_breakers,
    htf_mitigation_blocks=htf_mitigation.confirmed_blocks,
    timeframe="H1",
)
```

---

## State Merge Strategy

On each analysis cycle:

1. Load `prior_state.active_blocks` from previous invocation
2. Register new blocks from newly detected displacement legs not yet tracked
3. Update touch counts, mitigation percent, and lifecycle status against latest candles
4. Remove used, invalidated, and expired blocks from `active_blocks`
5. Persist updated `MitigationBlockState` in output

| Merge Rule | Behavior |
|------------|----------|
| Same origin bar + direction | Update existing block; do not duplicate |
| New displacement | Create fresh block if within lookback |
| Stale fresh block | Expire if beyond `max_block_age_bars` |
| Touch on existing block | Increment touch count; update mitigation percent |
| Bar count | Increment `state.bar_count` by new closed candles |

---

## Data Retention

| Data | Retention |
|------|-----------|
| Active blocks | Held in `MitigationBlockState` across calls (fresh + partial + confirmed) |
| Used/invalidated/expired | Partitioned in analysis output; removed from active state |
| Touch history | Embedded in block fields (`touch_count`, `first_touch_bar_index`, `last_touch_bar_index`) |
| Event history | Published only — not persisted in Sprint 7.1 spec |

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [EVENTS.md](./EVENTS.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
