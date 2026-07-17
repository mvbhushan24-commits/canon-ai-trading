# Premium / Discount Engine — Data Pipeline

**Engine ID:** `market_premium_discount`  
**Sprint:** 8.1 (Architecture specification)  
**Status:** Not implemented

---

## Pipeline Overview

```
NormalizedCandles (Market Data Engine)
        │
        ├─────────────────────────────────────────────────────────────────────────┐
        │              │              │              │              │               │
        ▼              ▼              ▼              ▼              ▼               ▼
MarketStructure  LiquidityState  order_blocks  FairValueGapState  breaker_blocks  mitigation_blocks
(Market Structure) (Market Liquidity) (Order Block) (Fair Value Gap) (Breaker Block) (Mitigation Block)
        │              │              │              │              │               │
        │              │              │              │              │    htf_premium_discount_context
        │              │              │              │              │    (optional HTF context)
        └──────────────┴──────────────┴──────────────┴──────────────┴───────────────┘
                                   │
                                   ▼
                        Premium / Discount Input Validator
                                   │
                                   ▼
                        Premium / Discount Detector
                          ├── Swing Anchor Selection
                          ├── Dealing Range Construction (external + internal)
                          ├── Primary Range Selection
                          ├── Price / Zone Territory Classification
                          ├── Premium Array Assembly
                          ├── Discount Array Assembly
                          ├── Internal Premium / Discount Bands
                          ├── HTF Context Integration
                          ├── MTF Premium / Discount Alignment
                          ├── Nested Zone Detection
                          ├── Fibonacci Dealing Range Projection
                          ├── OTE Zone Derivation
                          ├── Institutional Context Assembly
                          └── Quality Scoring
                                   │
                                   ▼
                        PremiumDiscountAnalysis
                                   │
                                   ▼
                        Premium / Discount Event Publisher
                                   │
                                   ▼
                        Decision Engine (future)
```

---

## Stage 1 — Market Data Input

**Source:** `MarketDataEngine.load_historical_candles()` or `market.candle.closed` event

**Type:** `list[NormalizedCandle]`

| Field Used | Purpose |
|------------|---------|
| `open`, `high`, `low`, `close` | Current price reference, range invalidation checks |
| `open_time_utc` | Timestamps for range lifecycle |
| `is_closed` | Only closed candles used for analysis |
| `symbol`, `timeframe` | Analysis scope validation |
| `volume` | Optional liquidity confirmation factor |

**Boundary rule:** Premium / Discount Engine imports `NormalizedCandle` from `backend.engines.market_data` public API only.

---

## Stage 2 — Market Structure Context

**Source:** `MarketStructureEngine.analyze(candles)` or `analysis.structure.completed` event

**Type:** `MarketStructure`

| Field Used | Purpose |
|------------|---------|
| `swing_highs`, `swing_lows` | Primary swing anchor pool |
| `internal_structure` | Internal dealing range construction |
| `external_structure` | External dealing range construction |
| `internal_structure.last_swing_high/low` | Internal anchor fallback |
| `external_structure.last_swing_high/low` | External anchor fallback |
| `current_trend` | Institutional context and bias weighting |
| `bos_events`, `choch_events` | Range invalidation and quality scoring |
| `confidence` | Propagate into range quality scoring |

**When missing:** Engine proceeds with `bias: undetermined`; no dealing range established; evidence notes `"Structure context unavailable"`.

---

## Stage 3 — Liquidity Context

**Source:** `LiquidityEngine.analyze(candles, structure)` or `analysis.liquidity.completed` event

**Type:** `LiquidityState` (extracted by caller)

| Field Used | Purpose |
|------------|---------|
| `active_zones` | Liquidity zone entries in premium/discount arrays |
| `recent_sweeps` | Liquidity confirmation near range boundaries |
| `bar_count` | Consistency validation |

**When missing:** Engine proceeds without liquidity zones in arrays; liquidity confirmation factor defaults to neutral.

---

## Stage 4 — Order Block Context

**Source:** `OrderBlockEngine.analyze(...)` → extract `order_blocks`

**Type:** `list[OrderBlock]`

| Field Used | Purpose |
|------------|---------|
| `block_id` | Array member reference |
| `direction` | Array dominant direction inference |
| `high`, `low` | Territory classification and array clustering |
| `status` | Filter to active statuses per configuration |
| `strength`, `quality` | Array confluence scoring |

**When missing:** Premium/discount arrays exclude order blocks; OB alignment factor defaults to neutral.

---

## Stage 5 — Fair Value Gap Context

**Source:** `FairValueGapEngine.analyze(...)` → extract `FairValueGapState`

**Type:** `FairValueGapState`

| Field Used | Purpose |
|------------|---------|
| `active_gaps` | FVG entries in premium/discount arrays |
| `bar_count` | Consistency validation |

Per-gap fields: `gap_id`, `direction`, `high`, `low`, `ce_price`, `status`, `strength`.

**When missing:** Arrays exclude FVGs; FVG alignment factor defaults to neutral.

---

## Stage 6 — Breaker Block Context

**Source:** `BreakerBlockEngine.analyze(...)` → extract `breaker_blocks`

**Type:** `list[BreakerBlock]`

| Field Used | Purpose |
|------------|---------|
| `breaker_id` | Array member reference |
| `direction` | Dominant direction inference |
| `high`, `low` | Territory classification |
| `status` | Filter to active statuses |
| `strength` | Confluence scoring |

**When missing:** Arrays exclude breakers; breaker alignment factor defaults to neutral.

---

## Stage 7 — Mitigation Block Context

**Source:** `MitigationBlockEngine.analyze(...)` → extract `mitigation_blocks`

**Type:** `list[MitigationBlock]`

| Field Used | Purpose |
|------------|---------|
| `block_id` | Array member reference |
| `direction` | Dominant direction inference |
| `high`, `low` | Territory classification |
| `status` | Filter to active statuses |
| `strength` | Confluence scoring |

**When missing:** Arrays exclude mitigation blocks; mitigation alignment factor defaults to neutral.

---

## Stage 8 — HTF Context (Optional)

**Source:** Caller-provided prior HTF `PremiumDiscountAnalysis` or `PremiumDiscountContext`

**Type:** `PremiumDiscountContext`

| Field Used | Purpose |
|------------|---------|
| `dealing_range` | HTF range bounds and equilibrium |
| `price_location` | HTF territory reference |
| `premium_arrays`, `discount_arrays` | HTF array overlap for MTF alignment |
| `timeframe` | HTF timeframe label |

**When missing:** HTF premium/discount and MTF alignment fields remain `None`; evidence notes `"HTF context unavailable"`.

---

## Stage 9 — Detection Pipeline (Internal)

### 9.1 Swing Anchor Selection

Select swing high and swing low per configured mode:

| Mode | High Selection | Low Selection |
|------|----------------|---------------|
| `latest_confirmed` | Latest swing high in lookback | Latest swing low in lookback |
| `range_extreme` | Highest high in lookback | Lowest low in lookback |
| `structure_state` | `StructureState.last_swing_high` | `StructureState.last_swing_low` |

Score swing quality from label, recency, and structure event proximity.

Emit `SwingHighAnchored` / `SwingLowAnchored` when anchors change.

### 9.2 Dealing Range Construction

Build two ranges every cycle:

| Range | Swing Source |
|-------|--------------|
| **External** | External structure swings + primary swing pool |
| **Internal** | Internal structure swings + primary swing pool |

Validation:

```
range_high > range_low
range_size >= min_range_size_pips
swing_high.bar_index != swing_low.bar_index (unless allow_same_bar_range)
```

Emit `DealingRangeEstablished` on new valid range; `DealingRangeUpdated` on bound revision; `DealingRangeInvalidated` on failure.

### 9.3 Primary Range Selection

| `primary_range_mode` | Behavior |
|----------------------|----------|
| `external` | External range is primary |
| `internal` | Internal range is primary |
| `auto` | Select range with higher quality score; tie-break external |

Primary range drives bias, arrays, Fibonacci, and OTE.

### 9.4 Territory Classification

For `current_price` and each upstream zone midpoint:

```
equilibrium = (range_high + range_low) / 2
tolerance = equilibrium_tolerance_price

if price > equilibrium + tolerance → premium
if price < equilibrium - tolerance → discount
else → equilibrium
```

Emit `PremiumZoneEntered`, `DiscountZoneEntered`, or `EquilibriumReached` on price territory transitions vs prior state.

Repeat classification against internal range for `internal_premium` / `internal_discount` bands.

### 9.5 Premium / Discount Array Assembly

```
1. Normalize all upstream zones to ArrayZoneEntry
2. Classify each entry into premium or discount
3. Filter by active status lists per zone type
4. Sort by midpoint price
5. Cluster entries within array_cluster_pips
6. Score cluster confluence
7. Emit PremiumArrayFormed / DiscountArrayFormed for clusters >= min_array_entries
```

### 9.6 HTF Context Integration

When HTF context provided:

| Output | Derivation |
|--------|------------|
| `htf_premium` | HTF premium territory summary |
| `htf_discount` | HTF discount territory summary |

Emit `HTFPremiumContext` / `HTFDiscountContext`.

### 9.7 MTF Alignment Scoring

Compare LTF and HTF:

| Score Component | Weight (default) |
|-----------------|------------------|
| Territory match | 0.40 |
| Range overlap | 0.30 |
| Array overlap | 0.20 |
| Structure trend support | 0.10 |

Emit `MTFPremiumAligned` or `MTFDiscountAligned` when score ≥ `mtf_alignment_min_score`.

### 9.8 Nested Zone Detection

For each zone pair (child, parent) where child ⊂ parent:

```
if classify(child) == classify(parent):
    record NestedZoneContext
    emit NestedPremiumZone or NestedDiscountZone
```

Parent types: OB, FVG, breaker, mitigation, liquidity, array cluster.

### 9.9 Fibonacci Dealing Range Projection

Project configured Fibonacci ratios across primary dealing range:

```
bullish: level_price = range_low + (range_size * ratio)
bearish: level_price = range_high - (range_size * ratio)
```

Emit `FibonacciRangeComputed`.

### 9.10 OTE Zone Derivation

When range valid and Fibonacci projected:

| Structure Trend | OTE Territory | Fib Span |
|-----------------|---------------|----------|
| Bullish / range | Discount | `ote_fib_low` – `ote_fib_high` from range low |
| Bearish | Premium | `ote_fib_low` – `ote_fib_high` from range high |
| Undetermined | Discount (default long context) | Configurable via `ote_default_direction` |

Identify overlapping institutional zones within OTE bounds.

Emit `OTEZoneDerived` when OTE band is valid.

### 9.11 Institutional Context Assembly

Aggregate all sub-results into `InstitutionalPricingContext`:

1. Range scope and bounds narrative
2. Current price location statement
3. Array dominance summary
4. HTF alignment statement
5. OTE availability and overlap count
6. Structure trend and liquidity sweep notes
7. Distance from equilibrium assessment

Emit `InstitutionalContextUpdated`.

### 9.12 Quality Scoring

Composite score (0.0–1.0) from configurable weights. See [ARCHITECTURE.md](./ARCHITECTURE.md) for factor table.

Analysis below `min_quality_score` still returned but flagged `quality: low` with evidence.

---

## Stage 10 — Output Assembly

**Type:** `PremiumDiscountAnalysis`

Key partitioned views:

```
dealing_range          → primary active range
external_range         → external structure range
internal_range         → internal structure range
premium_arrays         → institutional clusters in premium
discount_arrays        → institutional clusters in discount
nested_premium_zones   → nested premium relationships
nested_discount_zones  → nested discount relationships
fibonacci_range        → projected Fibonacci levels
ote_zone               → optimal trade entry band (when derivable)
institutional_context  → composite pricing narrative
```

Timeline events appended to `events` list and published via publisher.

Continuity state updated in `state.active_dealing_range` and related fields.

---

## Stage 11 — Event Publishing

See [EVENTS.md](./EVENTS.md) for complete event catalog.

---

## ASCII Data Flow

```
 MT5 ──► MDE ──► NormalizedCandle[]
                    │
         ┌──────────┼──────────┬──────────┬──────────┬──────────┐
         ▼          ▼          ▼          ▼          ▼          ▼
        MSE        LQE        OBE        FVE        MBE        MMBE
         │          │          │          │          │          │
         ▼          ▼          ▼          ▼          ▼          ▼
  MarketStructure  LiquidityState  order_blocks  FairValueGapState  breaker_blocks  mitigation_blocks
         │          │          │          │          │          │
         └──────────┴──────────┴──────────┴──────────┴──────────┘
                              │
                              ▼
                    Premium / Discount Engine
                              │
                              ▼
                    PremiumDiscountAnalysis
                              │
                              ▼
                    Decision Engine (future)
```

---

## Orchestrator Integration (Future)

When the platform orchestrator wires the full pipeline:

```
1. MDE → candles
2. MSE → structure
3. LQE → liquidity_state
4. OBE → order_blocks
5. FVE → fair_value_gap_state
6. MBE → breaker_blocks
7. MMBE → mitigation_blocks
8. HTF pass (optional) → htf_premium_discount_context
9. PDE → PremiumDiscountAnalysis
10. Decision Engine → consumes institutional_context
```

Each stage passes only public API types across engine boundaries.

---

## Error Handling in Pipeline

| Stage | Failure | Behavior |
|-------|---------|----------|
| Validation | Malformed candles | Raise `PD_VALIDATION_FAILED`; halt |
| Validation | Insufficient candles | Raise `PD_INSUFFICIENT_DATA`; halt |
| Structure | Mismatch when provided | Raise `PD_INVALID_STRUCTURE`; halt |
| Range construction | No valid swings | Return analysis with `bias: undetermined` |
| Range construction | Range too small | `PD_DEALING_RANGE_INVALID` in evidence; `undetermined` bias |
| Optional zones | Empty lists | Proceed; arrays empty |
| HTF context | Invalid when provided | Raise `PD_INVALID_HTF_CONTEXT`; halt |
| Publisher | Emit failure | Log error; analysis still returned |

Constitution rule: **never force** premium or discount classification when evidence is insufficient.

---

## State Continuity Flow

```
prior_state ──► merge with new swing/range evidence
                    │
                    ├── same anchors → update territory transitions only
                    ├── revised anchors → DealingRangeUpdated
                    └── invalidated range → DealingRangeInvalidated → seek new range
```

`PremiumDiscountState` serialized by caller between analysis cycles.

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |
