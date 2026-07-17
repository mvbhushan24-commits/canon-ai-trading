# Premium / Discount Engine — Events

**Engine ID:** `market_premium_discount`  
**Sprint:** 8.1 (Architecture specification)  
**Status:** Not implemented

---

## Event Envelope

All events use the `PremiumDiscountAnalysisEvent` envelope (consistent with Sprints 1–7):

```python
{
    "event_id": "uuid",
    "timestamp_utc": "ISO-8601",
    "symbol": "GOLD.i#",
    "source_engine": "market_premium_discount",
    "event_type": "DealingRangeEstablished",
    "payload": { ... }
}
```

---

## Published Events

### Dealing Range Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `DealingRangeEstablished` | New valid dealing range activated | Range ID, bounds, equilibrium, swing anchors |
| `DealingRangeUpdated` | Existing range bounds revised | Range ID, updated bounds, reason |
| `DealingRangeInvalidated` | Range failed validation or structure break | Range ID, invalidation reason, bar index |

### Swing Anchor Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `SwingHighAnchored` | Swing high selected as range anchor | Price, bar index, label, quality score |
| `SwingLowAnchored` | Swing low selected as range anchor | Price, bar index, label, quality score |

### Territory Transition Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `PremiumZoneEntered` | Price crossed into premium territory | Price, equilibrium, dealing range ID |
| `DiscountZoneEntered` | Price crossed into discount territory | Price, equilibrium, dealing range ID |
| `EquilibriumReached` | Price entered equilibrium tolerance band | Price, tolerance bounds, dealing range ID |

### Array Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `PremiumArrayFormed` | Premium institutional array assembled | Array ID, entry count, cluster bounds, confluence score |
| `DiscountArrayFormed` | Discount institutional array assembled | Array ID, entry count, cluster bounds, confluence score |

### Internal Range Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `InternalPremiumClassified` | Internal premium band computed | Band bounds, internal range ID |
| `InternalDiscountClassified` | Internal discount band computed | Band bounds, internal range ID |

### HTF Context Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `HTFPremiumContext` | HTF premium context applied | HTF timeframe, equilibrium, array count |
| `HTFDiscountContext` | HTF discount context applied | HTF timeframe, equilibrium, array count |

### MTF Alignment Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `MTFPremiumAligned` | LTF/HTF premium alignment score ≥ threshold | LTF/HTF timeframes, alignment score, overlap percent |
| `MTFDiscountAligned` | LTF/HTF discount alignment score ≥ threshold | LTF/HTF timeframes, alignment score, overlap percent |

### Nesting Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `NestedPremiumZone` | Nested premium relationship detected | Child zone ID, parent zone ID, containment percent |
| `NestedDiscountZone` | Nested discount relationship detected | Child zone ID, parent zone ID, containment percent |

### Fibonacci and OTE Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `FibonacciRangeComputed` | Fibonacci levels projected within dealing range | Range ID, direction, level count |
| `OTEZoneDerived` | Optimal trade entry zone derived | OTE ID, bounds, overlapping zone IDs, territory |

### Context Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `InstitutionalContextUpdated` | Composite institutional pricing context refreshed | Narrative summary, bias, confidence |
| `PremiumDiscountUpdated` | Full analysis cycle complete | Full `PremiumDiscountAnalysis` summary |

---

## Contract Events (Event Bus Names)

| Contract Name | Maps To | Trigger |
|---------------|---------|---------|
| `analysis.premium_discount.completed` | `PremiumDiscountUpdated` | Analysis finished |
| `analysis.premium_discount.dealing_range_established` | `DealingRangeEstablished` | New range |
| `analysis.premium_discount.dealing_range_updated` | `DealingRangeUpdated` | Range revised |
| `analysis.premium_discount.dealing_range_invalidated` | `DealingRangeInvalidated` | Range invalidated |
| `analysis.premium_discount.swing_high_anchored` | `SwingHighAnchored` | Swing high anchor |
| `analysis.premium_discount.swing_low_anchored` | `SwingLowAnchored` | Swing low anchor |
| `analysis.premium_discount.premium_entered` | `PremiumZoneEntered` | Price entered premium |
| `analysis.premium_discount.discount_entered` | `DiscountZoneEntered` | Price entered discount |
| `analysis.premium_discount.equilibrium_reached` | `EquilibriumReached` | Price at equilibrium |
| `analysis.premium_discount.premium_array` | `PremiumArrayFormed` | Premium array formed |
| `analysis.premium_discount.discount_array` | `DiscountArrayFormed` | Discount array formed |
| `analysis.premium_discount.internal_premium` | `InternalPremiumClassified` | Internal premium band |
| `analysis.premium_discount.internal_discount` | `InternalDiscountClassified` | Internal discount band |
| `analysis.premium_discount.htf_premium` | `HTFPremiumContext` | HTF premium context |
| `analysis.premium_discount.htf_discount` | `HTFDiscountContext` | HTF discount context |
| `analysis.premium_discount.mtf_premium_aligned` | `MTFPremiumAligned` | MTF premium alignment |
| `analysis.premium_discount.mtf_discount_aligned` | `MTFDiscountAligned` | MTF discount alignment |
| `analysis.premium_discount.nested_premium` | `NestedPremiumZone` | Nested premium zone |
| `analysis.premium_discount.nested_discount` | `NestedDiscountZone` | Nested discount zone |
| `analysis.premium_discount.fibonacci_computed` | `FibonacciRangeComputed` | Fibonacci projected |
| `analysis.premium_discount.ote_derived` | `OTEZoneDerived` | OTE zone derived |
| `analysis.premium_discount.context_updated` | `InstitutionalContextUpdated` | Context refreshed |
| `analysis.premium_discount.error` | — | Analysis failure |

---

## Event Payload Schemas

### DealingRangeEstablished Payload

```json
{
  "range_id": "dr-ext-4070_50-4060_20-h1",
  "scope": "external",
  "high": "4070.50",
  "low": "4060.20",
  "equilibrium": "4065.35",
  "range_size": "10.30",
  "swing_high": {
    "price": "4070.50",
    "bar_index": 480,
    "kind": "swing_high",
    "label": "HH",
    "quality_score": "0.82"
  },
  "swing_low": {
    "price": "4060.20",
    "bar_index": 465,
    "kind": "swing_low",
    "label": "HL",
    "quality_score": "0.75"
  },
  "formation_bar_index": 480,
  "formation_time_utc": "2026-07-16T08:00:00+00:00",
  "is_valid": true,
  "quality": "high",
  "strength": "0.78",
  "timeframe": "H1"
}
```

### DealingRangeUpdated Payload

```json
{
  "range_id": "dr-ext-4070_50-4060_20-h1",
  "scope": "external",
  "high": "4072.10",
  "low": "4060.20",
  "equilibrium": "4066.15",
  "previous_high": "4070.50",
  "update_reason": "New swing high anchor replaced prior high",
  "formation_bar_index": 485,
  "timeframe": "H1"
}
```

### DealingRangeInvalidated Payload

```json
{
  "range_id": "dr-ext-4070_50-4060_20-h1",
  "scope": "external",
  "invalidation_reason": "Opposing BOS close below range low",
  "invalidation_bar_index": 490,
  "invalidation_price": "4059.80",
  "timeframe": "H1"
}
```

### SwingHighAnchored Payload

```json
{
  "price": "4070.50",
  "bar_index": 480,
  "timestamp_utc": "2026-07-16T08:00:00+00:00",
  "kind": "swing_high",
  "label": "HH",
  "quality_score": "0.82",
  "scope": "external",
  "timeframe": "H1"
}
```

### SwingLowAnchored Payload

```json
{
  "price": "4060.20",
  "bar_index": 465,
  "timestamp_utc": "2026-07-15T17:00:00+00:00",
  "kind": "swing_low",
  "label": "HL",
  "quality_score": "0.75",
  "scope": "external",
  "timeframe": "H1"
}
```

### PremiumZoneEntered Payload

```json
{
  "price": "4067.80",
  "equilibrium": "4065.35",
  "tolerance_high": "4065.65",
  "dealing_range_id": "dr-ext-4070_50-4060_20-h1",
  "previous_territory": "equilibrium",
  "timestamp_utc": "2026-07-16T12:00:00+00:00",
  "timeframe": "H1"
}
```

### DiscountZoneEntered Payload

```json
{
  "price": "4062.50",
  "equilibrium": "4065.35",
  "tolerance_low": "4065.05",
  "dealing_range_id": "dr-ext-4070_50-4060_20-h1",
  "previous_territory": "premium",
  "timestamp_utc": "2026-07-16T14:00:00+00:00",
  "timeframe": "H1"
}
```

### EquilibriumReached Payload

```json
{
  "price": "4065.40",
  "equilibrium": "4065.35",
  "tolerance_high": "4065.65",
  "tolerance_low": "4065.05",
  "dealing_range_id": "dr-ext-4070_50-4060_20-h1",
  "previous_territory": "discount",
  "timestamp_utc": "2026-07-16T16:00:00+00:00",
  "timeframe": "H1"
}
```

### PremiumArrayFormed Payload

```json
{
  "array_id": "pa-h1-4068_80-4067_20",
  "territory": "premium",
  "scope": "external",
  "cluster_high": "4068.80",
  "cluster_low": "4067.20",
  "entry_count": 3,
  "dominant_direction": "bearish",
  "confluence_score": "0.71",
  "zone_entries": [
    {
      "zone_id": "ob-bear-4068_50-abc",
      "zone_type": "order_block",
      "midpoint": "4068.00",
      "direction": "bearish",
      "placement_score": "0.85"
    },
    {
      "zone_id": "fvg-bear-4067_80-def",
      "zone_type": "fair_value_gap",
      "midpoint": "4067.90",
      "direction": "bearish",
      "placement_score": "0.72"
    },
    {
      "zone_id": "bb-bear-4067_30-ghi",
      "zone_type": "breaker_block",
      "midpoint": "4067.50",
      "direction": "bearish",
      "placement_score": "0.68"
    }
  ],
  "timeframe": "H1"
}
```

### DiscountArrayFormed Payload

```json
{
  "array_id": "da-h1-4062_50-4061_10",
  "territory": "discount",
  "scope": "external",
  "cluster_high": "4062.50",
  "cluster_low": "4061.10",
  "entry_count": 2,
  "dominant_direction": "bullish",
  "confluence_score": "0.68",
  "zone_entries": [
    {
      "zone_id": "ob-bull-4062_00-jkl",
      "zone_type": "order_block",
      "midpoint": "4062.00",
      "direction": "bullish",
      "placement_score": "0.80"
    },
    {
      "zone_id": "mb-bull-4061_50-mno",
      "zone_type": "mitigation_block",
      "midpoint": "4061.80",
      "direction": "bullish",
      "placement_score": "0.74"
    }
  ],
  "timeframe": "H1"
}
```

### InternalPremiumClassified Payload

```json
{
  "territory": "premium",
  "scope": "internal",
  "high": "4068.20",
  "low": "4066.90",
  "internal_range_id": "dr-int-4068_50-4065_00-h1",
  "equilibrium": "4067.55",
  "timeframe": "H1"
}
```

### InternalDiscountClassified Payload

```json
{
  "territory": "discount",
  "scope": "internal",
  "high": "4066.80",
  "low": "4065.10",
  "internal_range_id": "dr-int-4068_50-4065_00-h1",
  "equilibrium": "4067.55",
  "timeframe": "H1"
}
```

### HTFPremiumContext Payload

```json
{
  "htf_timeframe": "H4",
  "territory": "premium",
  "equilibrium": "4075.20",
  "dealing_range_high": "4085.00",
  "dealing_range_low": "4065.40",
  "array_count": 2,
  "ltf_timeframe": "H1",
  "timeframe": "H1"
}
```

### HTFDiscountContext Payload

```json
{
  "htf_timeframe": "H4",
  "territory": "discount",
  "equilibrium": "4075.20",
  "dealing_range_high": "4085.00",
  "dealing_range_low": "4065.40",
  "array_count": 1,
  "ltf_timeframe": "H1",
  "timeframe": "H1"
}
```

### MTFPremiumAligned Payload

```json
{
  "territory": "premium",
  "ltf_timeframe": "H1",
  "htf_timeframe": "H4",
  "alignment_score": "0.72",
  "range_overlap_percent": "45.0",
  "array_overlap_count": 1,
  "ltf_price_location": "premium",
  "htf_price_location": "premium",
  "evidence": [
    "LTF and HTF both in premium territory",
    "Dealing ranges overlap 45%",
    "1 premium array overlap between timeframes"
  ],
  "timeframe": "H1"
}
```

### MTFDiscountAligned Payload

```json
{
  "territory": "discount",
  "ltf_timeframe": "H1",
  "htf_timeframe": "H4",
  "alignment_score": "0.65",
  "range_overlap_percent": "38.0",
  "array_overlap_count": 1,
  "ltf_price_location": "discount",
  "htf_price_location": "discount",
  "evidence": [
    "LTF and HTF both in discount territory",
    "Dealing ranges overlap 38%",
    "1 discount array overlap between timeframes"
  ],
  "timeframe": "H1"
}
```

### NestedPremiumZone Payload

```json
{
  "child_zone_id": "fvg-bear-4067_80-def",
  "child_zone_type": "fair_value_gap",
  "parent_zone_id": "ob-bear-4068_50-abc",
  "parent_zone_type": "order_block",
  "territory": "premium",
  "containment_percent": "92.0",
  "child_midpoint": "4067.90",
  "parent_midpoint": "4068.00",
  "timeframe": "H1"
}
```

### NestedDiscountZone Payload

```json
{
  "child_zone_id": "mb-bull-4061_50-mno",
  "child_zone_type": "mitigation_block",
  "parent_zone_id": "ob-bull-4062_00-jkl",
  "parent_zone_type": "order_block",
  "territory": "discount",
  "containment_percent": "88.0",
  "child_midpoint": "4061.80",
  "parent_midpoint": "4062.00",
  "timeframe": "H1"
}
```

### FibonacciRangeComputed Payload

```json
{
  "range_id": "dr-ext-4070_50-4060_20-h1",
  "direction": "bullish",
  "equilibrium_level": "4065.35",
  "ote_low_level": "4062.59",
  "ote_high_level": "4061.87",
  "levels": [
    { "ratio": "0.0", "price": "4060.20", "label": "range_low" },
    { "ratio": "0.236", "price": "4061.63", "label": "fib_236" },
    { "ratio": "0.382", "price": "4062.59", "label": "fib_382" },
    { "ratio": "0.5", "price": "4065.35", "label": "equilibrium" },
    { "ratio": "0.618", "price": "4066.56", "label": "fib_618" },
    { "ratio": "0.705", "price": "4067.46", "label": "fib_705" },
    { "ratio": "0.79", "price": "4068.34", "label": "fib_790" },
    { "ratio": "1.0", "price": "4070.50", "label": "range_high" }
  ],
  "timeframe": "H1"
}
```

### OTEZoneDerived Payload

```json
{
  "ote_id": "ote-disc-bull-h1-4062_59-4068_34",
  "territory": "discount",
  "direction": "bullish",
  "high": "4068.34",
  "low": "4062.59",
  "fib_low_ratio": "0.62",
  "fib_high_ratio": "0.79",
  "overlapping_zone_ids": [
    "ob-bull-4062_00-jkl",
    "mb-bull-4061_50-mno"
  ],
  "quality": "high",
  "strength": "0.76",
  "dealing_range_id": "dr-ext-4070_50-4060_20-h1",
  "timeframe": "H1"
}
```

### InstitutionalContextUpdated Payload

```json
{
  "current_price_location": "discount",
  "bias": "discount",
  "confidence": "0.74",
  "active_dealing_range_scope": "external",
  "structure_trend": "bullish",
  "dominant_array_territory": "discount",
  "mtf_aligned": true,
  "ote_available": true,
  "narrative": [
    "External dealing range 4060.20 – 4070.50 (equilibrium 4065.35)",
    "Price at 4063.10 in discount territory",
    "Discount array with 2 institutional zones (bullish dominant)",
    "HTF H4 discount alignment score 0.65",
    "OTE zone 4062.59 – 4068.34 with 2 overlapping zones",
    "Structure trend bullish — discount favored for long context"
  ],
  "timeframe": "H1"
}
```

### PremiumDiscountUpdated Payload

```json
{
  "symbol": "GOLD.i#",
  "timeframe": "H1",
  "timestamp_utc": "2026-07-16T16:00:00+00:00",
  "current_price": "4063.10",
  "price_location": "discount",
  "bias": "discount",
  "confidence": "0.74",
  "quality": "high",
  "strength": "0.76",
  "dealing_range": {
    "range_id": "dr-ext-4070_50-4060_20-h1",
    "scope": "primary",
    "high": "4070.50",
    "low": "4060.20",
    "equilibrium": "4065.35",
    "is_valid": true
  },
  "premium_array_count": 1,
  "discount_array_count": 1,
  "ote_available": true,
  "mtf_premium_aligned": false,
  "mtf_discount_aligned": true,
  "evidence": [
    "External dealing range established from HH/HL swing pair",
    "Price in discount below equilibrium 4065.35",
    "1 discount array with OB + mitigation confluence",
    "HTF H4 discount alignment confirmed",
    "OTE zone available with 2 overlapping institutional zones"
  ]
}
```

---

## Consumed Events

| Event | Source | Action |
|-------|--------|--------|
| `market.candle.closed` | Market Data Engine | Trigger premium/discount analysis (orchestrator) |
| `analysis.structure.completed` | Market Structure Engine | Provide structure context |
| `analysis.liquidity.completed` | Market Liquidity Engine | Provide liquidity state |
| `analysis.order_block.completed` | Order Block Engine | Extract order blocks for arrays |
| `analysis.fvg.completed` | Fair Value Gap Engine | Extract FVG state for arrays |
| `analysis.breaker.completed` | Breaker Block Engine | Extract breaker blocks for arrays |
| `analysis.mitigation.completed` | Mitigation Block Engine | Extract mitigation blocks for arrays |
| `analysis.premium_discount.completed` | Self (HTF pass) | HTF context for LTF MTF alignment |
| `system.config.updated` | Config service | Reload `market_premium_discount` parameters |

### Consumption Notes

- The engine does **not** subscribe directly to upstream engines in Sprint 8.2; the orchestrator passes typed inputs to `analyze()`.
- Event consumption wiring is a future orchestrator sprint deliverable.
- HTF context is typically produced by running this engine on a higher timeframe before the LTF pass.

---

## Error Event

### analysis.premium_discount.error

Published when analysis fails with a `PD_*` error code:

```json
{
  "event_id": "uuid",
  "timestamp_utc": "2026-07-16T16:00:00+00:00",
  "symbol": "GOLD.i#",
  "source_engine": "market_premium_discount",
  "event_type": "analysis.premium_discount.error",
  "payload": {
    "code": "PD_INSUFFICIENT_DATA",
    "message": "Insufficient candles: 12 < min_candles 20",
    "timeframe": "H1",
    "details": {
      "candle_count": 12,
      "min_candles": 20
    }
  }
}
```

| Code | Published When |
|------|----------------|
| `PD_INSUFFICIENT_DATA` | Candle count below minimum |
| `PD_VALIDATION_FAILED` | Invalid input batch |
| `PD_INVALID_STRUCTURE` | Structure context invalid |
| `PD_INVALID_LIQUIDITY_STATE` | Liquidity state invalid |
| `PD_INVALID_ORDER_BLOCKS` | Order blocks invalid |
| `PD_INVALID_FVG_STATE` | FVG state invalid |
| `PD_INVALID_BREAKER_BLOCKS` | Breaker blocks invalid |
| `PD_INVALID_MITIGATION_BLOCKS` | Mitigation blocks invalid |
| `PD_INVALID_HTF_CONTEXT` | HTF context invalid |
| `PD_TIMEFRAME_UNSUPPORTED` | Timeframe not configured |
| `PD_STATE_CORRUPT` | Prior state corrupt |
| `PD_ERROR` | Unexpected internal failure |

`PD_DEALING_RANGE_INVALID` is **not** published as an error event — it is a degraded analysis outcome reflected in `PremiumDiscountUpdated` with `bias: undetermined`.

---

## Event Idempotency

| Event Category | Idempotency Rule |
|----------------|------------------|
| Territory transitions | Emit only when territory changes vs `prior_state.last_price_location` |
| Dealing range established | Emit only when new `range_id` differs from prior active range |
| Dealing range updated | Emit only when bounds change beyond tolerance |
| Array formed | Emit when array membership changes (new zone added or removed) |
| MTF alignment | Re-emit when alignment score crosses threshold in either direction |
| Fibonacci computed | Emit when dealing range ID or direction changes |
| OTE derived | Emit when OTE bounds change |
| Analysis completed | Emit every analysis cycle |

---

## Event Ordering

Within a single analysis cycle, events are published in pipeline order:

```
1. SwingHighAnchored / SwingLowAnchored (if changed)
2. DealingRangeEstablished / DealingRangeUpdated / DealingRangeInvalidated
3. PremiumZoneEntered / DiscountZoneEntered / EquilibriumReached (if transitioned)
4. PremiumArrayFormed / DiscountArrayFormed
5. InternalPremiumClassified / InternalDiscountClassified
6. HTFPremiumContext / HTFDiscountContext
7. MTFPremiumAligned / MTFDiscountAligned
8. NestedPremiumZone / NestedDiscountZone
9. FibonacciRangeComputed
10. OTEZoneDerived
11. InstitutionalContextUpdated
12. PremiumDiscountUpdated
```

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
