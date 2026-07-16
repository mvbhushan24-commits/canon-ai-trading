# Fair Value Gap Engine — Events

**Engine ID:** `fair_value_gap`  
**Sprint:** 5.1 (Architecture specification)  
**Status:** Not implemented

---

## Event Envelope

All events use the `FairValueGapAnalysisEvent` envelope (consistent with Sprints 1–4):

```python
{
    "event_id": "uuid",
    "timestamp_utc": "ISO-8601",
    "symbol": "GOLD.i#",
    "source_engine": "fair_value_gap",
    "event_type": "BullishFairValueGapDetected",
    "payload": { ... }
}
```

---

## Published Events

### Detection Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `FairValueGapDetected` | Any new FVG identified | Gap summary |
| `BullishFairValueGapDetected` | New bullish FVG | Gap ID, zone bounds, CE, quality |
| `BearishFairValueGapDetected` | New bearish FVG | Gap ID, zone bounds, CE, quality |
| `OpenFairValueGap` | Gap confirmed untested | Gap ID, direction, zone |

### Lifecycle Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `PartialFillFairValueGap` | Price entered gap | Gap ID, fill_percent, entry price |
| `FilledFairValueGap` | Gap fully traversed | Gap ID, fill_bar_index, fill_percent |
| `MitigatedFairValueGap` | Imbalance addressed | Gap ID, mitigation mode, price |
| `InvalidatedFairValueGap` | Gap broken | Gap ID, invalidation bar, price |
| `ExpiredFairValueGap` | Gap aged out | Gap ID, expiration bar, age bars |

### Institutional Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `CEEncroached` | Consequent Encroachment touched | Gap ID, ce_price, fill_percent |
| `NestedFairValueGap` | Child gap nested in parent | Child ID, parent ID, zone bounds |
| `MTFAlignedFairValueGap` | Multi-timeframe alignment confirmed | Gap ID, aligned timeframes, score |

### Completion Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `FairValueGapUpdated` | Analysis cycle complete | Full `FairValueGapAnalysis` |

---

## Contract Events (Event Bus Names)

| Contract Name | Maps To | Trigger |
|---------------|---------|---------|
| `analysis.fvg.completed` | `FairValueGapUpdated` | Analysis finished |
| `analysis.fvg.detected` | `FairValueGapDetected` | New gap |
| `analysis.fvg.bullish_detected` | `BullishFairValueGapDetected` | New bullish gap |
| `analysis.fvg.bearish_detected` | `BearishFairValueGapDetected` | New bearish gap |
| `analysis.fvg.open` | `OpenFairValueGap` | Open status confirmed |
| `analysis.fvg.partial_fill` | `PartialFillFairValueGap` | Partial fill detected |
| `analysis.fvg.filled` | `FilledFairValueGap` | Full fill detected |
| `analysis.fvg.mitigated` | `MitigatedFairValueGap` | Mitigation detected |
| `analysis.fvg.invalidated` | `InvalidatedFairValueGap` | Invalidation detected |
| `analysis.fvg.expired` | `ExpiredFairValueGap` | Expiration detected |
| `analysis.fvg.ce_encroached` | `CEEncroached` | CE level touched |
| `analysis.fvg.nested` | `NestedFairValueGap` | Nesting resolved |
| `analysis.fvg.mtf_aligned` | `MTFAlignedFairValueGap` | MTF alignment confirmed |
| `analysis.fvg.error` | — | Analysis failure |

---

## Event Payload Schemas

### FairValueGapDetected Payload

```json
{
  "gap_id": "fvg-bull-4082_50-abc123",
  "direction": "bullish",
  "status": "open",
  "high": "4082.50",
  "low": "4080.20",
  "ce_price": "4081.35",
  "gap_size": "2.30",
  "gap_size_pips": "23.0",
  "fill_percent": "0.0",
  "origin_time_utc": "2026-07-15T21:00:00+00:00",
  "origin_bar_index": 482,
  "candle_a_index": 480,
  "candle_b_index": 481,
  "candle_c_index": 482,
  "quality": "high",
  "strength": "0.82",
  "premium_discount": "discount",
  "structure_alignment": true,
  "liquidity_confluence": false,
  "order_block_confluence": true,
  "timeframe": "H1"
}
```

### BullishFairValueGapDetected Payload

Same as `FairValueGapDetected` with `direction` guaranteed `"bullish"`.

### PartialFillFairValueGap Payload

```json
{
  "gap_id": "fvg-bull-4082_50-abc123",
  "direction": "bullish",
  "status": "partial",
  "high": "4082.50",
  "low": "4080.20",
  "ce_price": "4081.35",
  "fill_percent": "35.0",
  "entry_price": "4082.10",
  "entry_bar_index": 488,
  "timestamp_utc": "2026-07-16T03:00:00+00:00",
  "timeframe": "H1"
}
```

### FilledFairValueGap Payload

```json
{
  "gap_id": "fvg-bull-4082_50-abc123",
  "direction": "bullish",
  "status": "filled",
  "high": "4082.50",
  "low": "4080.20",
  "fill_percent": "100.0",
  "fill_bar_index": 492,
  "fill_price": "4080.20",
  "timestamp_utc": "2026-07-16T07:00:00+00:00",
  "timeframe": "H1"
}
```

### MitigatedFairValueGap Payload

```json
{
  "gap_id": "fvg-bull-4082_50-abc123",
  "direction": "bullish",
  "status": "mitigated",
  "high": "4082.50",
  "low": "4080.20",
  "ce_price": "4081.35",
  "fill_percent": "50.0",
  "mitigation_mode": "ce",
  "mitigation_bar_index": 490,
  "mitigation_price": "4081.35",
  "timestamp_utc": "2026-07-16T05:00:00+00:00",
  "timeframe": "H1"
}
```

### InvalidatedFairValueGap Payload

```json
{
  "gap_id": "fvg-bull-4082_50-abc123",
  "direction": "bullish",
  "status": "invalidated",
  "high": "4082.50",
  "low": "4080.20",
  "invalidation_bar_index": 495,
  "invalidation_price": "4079.80",
  "timestamp_utc": "2026-07-16T10:00:00+00:00",
  "timeframe": "H1"
}
```

### ExpiredFairValueGap Payload

```json
{
  "gap_id": "fvg-bull-4082_50-abc123",
  "direction": "bullish",
  "status": "expired",
  "high": "4082.50",
  "low": "4080.20",
  "expiration_bar_index": 632,
  "age_bars": 150,
  "timestamp_utc": "2026-07-22T10:00:00+00:00",
  "timeframe": "H1"
}
```

### CEEncroached Payload

```json
{
  "gap_id": "fvg-bull-4082_50-abc123",
  "direction": "bullish",
  "ce_price": "4081.35",
  "fill_percent": "50.0",
  "encroachment_bar_index": 490,
  "encroachment_price": "4081.35",
  "gap_status": "partial",
  "timestamp_utc": "2026-07-16T05:00:00+00:00",
  "timeframe": "H1"
}
```

### NestedFairValueGap Payload

```json
{
  "child_gap_id": "fvg-bull-4081_80-def456",
  "parent_gap_id": "fvg-bull-4082_50-abc123",
  "child_high": "4081.80",
  "child_low": "4081.10",
  "parent_high": "4082.50",
  "parent_low": "4080.20",
  "timeframe": "H1",
  "timestamp_utc": "2026-07-16T02:00:00+00:00"
}
```

### MTFAlignedFairValueGap Payload

```json
{
  "gap_id": "fvg-bull-4081_80-def456",
  "direction": "bullish",
  "timeframe": "H1",
  "aligned_timeframes": ["H4", "H1"],
  "alignment_direction": "bullish",
  "alignment_score": "0.78",
  "parent_timeframe": "H4",
  "parent_gap_id": "fvg-bull-4080_00-ghi789",
  "timestamp_utc": "2026-07-16T02:00:00+00:00"
}
```

### analysis.fvg.completed Payload

Full `FairValueGapAnalysis.model_dump(mode="json")`.

### analysis.fvg.error Payload

```json
{
  "error_code": "FVE_INSUFFICIENT_DATA",
  "message": "Insufficient closed candles: 12 < 20",
  "symbol": "GOLD.i#",
  "timeframe": "H1",
  "timestamp_utc": "2026-07-16T10:00:00+00:00"
}
```

---

## Consumed Events

| Event | Source Engine | Action |
|-------|---------------|--------|
| `market.candle.closed` | Market Data | Trigger FVG analysis (orchestrator) |
| `analysis.structure.completed` | Market Structure | Enrich with structure context |
| `analysis.liquidity.completed` | Market Liquidity | Extract `LiquidityState` for confluence |
| `analysis.order_block.completed` | Order Block | Extract `OrderBlockState` for confluence |
| `system.config.updated` | Config service | Reload `FairValueGapConfig` |

### Consumption Notes

| Event | Required | Fallback |
|-------|----------|----------|
| `market.candle.closed` | Yes (event-driven mode) | Batch `analyze()` call with candle list |
| `analysis.structure.completed` | No | Direct `MarketStructure` injection |
| `analysis.liquidity.completed` | No | Direct `LiquidityState` injection or skip |
| `analysis.order_block.completed` | No | Direct `OrderBlockState` injection or skip |
| `system.config.updated` | No | Manual `handle_config_updated()` |

### State Extraction from Upstream Events

The FVG Engine does not subscribe to upstream engines directly. The orchestrator extracts state:

```
analysis.liquidity.completed  →  payload.state  →  LiquidityState
analysis.order_block.completed  →  payload.state  →  OrderBlockState
```

---

## Event Flow Diagram

```
market.candle.closed
        │
        ├──────────────────────────────────────────────────┐
        │                          │                       │
        ▼                          ▼                       ▼
analysis.structure.completed   analysis.liquidity.completed   analysis.order_block.completed
        │                          │                       │
        │                   extract .state            extract .state
        │                          │                       │
        └──────────────┬───────────┴───────────────────────┘
                       │
                       ▼
              Fair Value Gap Engine
              .analyze(candles, structure,
                       liquidity_state, order_block_state)
                       │
         ┌─────────────┼─────────────┬─────────────┐
         ▼             ▼             ▼             ▼
BullishFVGDetected  PartialFill   CEEncroached  MTFAligned
         │             │             │             │
         └─────────────┴─────────────┴─────────────┘
                       │
                       ▼
              FairValueGapUpdated
              (analysis.fvg.completed)
```

---

## Lifecycle Event State Machine

```
                    ┌──────────────┐
                    │   DETECTED   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
              ┌─────│     OPEN     │─────┐
              │     └──────┬───────┘     │
              │            │             │
              │   price    │    age >    │
              │   enters   │  max_age    │
              │            ▼             ▼
              │     ┌──────────────┐  ┌─────────┐
              │     │   PARTIAL    │  │ EXPIRED │
              │     └──────┬───────┘  └─────────┘
              │            │
              │     ┌──────┼──────┐
              │     ▼      ▼      ▼
              │  ┌──────┐ ┌────┐ ┌─────────────┐
              │  │CE    │ │FULL│ │ INVALIDATED │
              │  │TOUCH │ │FILL│ │             │
              │  └──┬───┘ └──┬─┘ └─────────────┘
              │     ▼        ▼
              │  ┌──────────────────┐
              └──│    MITIGATED     │
                 └──────────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │    FILLED    │
                 └──────────────┘
```

### Transition Event Mapping

| Transition | Event(s) Emitted |
|------------|-----------------|
| Detection → Open | `FairValueGapDetected`, `Bullish/BearishFairValueGapDetected`, `OpenFairValueGap` |
| Open → Partial | `PartialFillFairValueGap` |
| Partial → CE touched | `CEEncroached` |
| Partial/Open → Mitigated | `MitigatedFairValueGap` |
| Partial → Filled | `FilledFairValueGap` |
| Any → Invalidated | `InvalidatedFairValueGap` |
| Open/Partial → Expired | `ExpiredFairValueGap` |
| Nesting resolved | `NestedFairValueGap` |
| MTF confirmed | `MTFAlignedFairValueGap` |
| Cycle complete | `FairValueGapUpdated` |

---

## Event Ordering Guarantees

| Guarantee | Description |
|-----------|-------------|
| Detection before lifecycle | `FairValueGapDetected` always precedes lifecycle events for the same gap |
| CE before mitigation | When `mitigation_mode: ce`, `CEEncroached` precedes `MitigatedFairValueGap` |
| Completion last | `FairValueGapUpdated` is always the final event in a cycle |
| No duplicate detection | Same `gap_id` will not emit `FairValueGapDetected` twice |
| Idempotent lifecycle | Re-emitting same status on subsequent cycles is suppressed |

---

## Publisher Interface Summary

See [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) for `FairValueGapEventPublisher` method signatures.

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
