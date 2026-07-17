# Mitigation Block Engine — Events

**Engine ID:** `market_mitigation`  
**Sprint:** 7.1 (Architecture specification)  
**Status:** Not implemented

---

## Event Envelope

All events use the `MitigationBlockAnalysisEvent` envelope (consistent with Sprints 1–6):

```python
{
    "event_id": "uuid",
    "timestamp_utc": "ISO-8601",
    "symbol": "GOLD.i#",
    "source_engine": "market_mitigation",
    "event_type": "BullishMitigationBlockDetected",
    "payload": { ... }
}
```

---

## Published Events

### Detection Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `MitigationBlockDetected` | Any new mitigation block identified | Block summary |
| `BullishMitigationBlockDetected` | New bullish mitigation block | Block ID, zone bounds, displacement reference |
| `BearishMitigationBlockDetected` | New bearish mitigation block | Block ID, zone bounds, displacement reference |
| `FreshMitigationBlock` | Block registered as fresh | Block ID, direction, status |

### Mitigation Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `PartialMitigationBlock` | Partial zone interaction detected | Block ID, mitigation percent, touch count |
| `FullMitigationBlock` | Full zone traverse reached | Block ID, mitigation percent, price |
| `MultiTouchMitigationBlock` | Additional distinct touch recorded | Block ID, touch count, bar index |

### Confirmation Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `ConfirmedMitigationBlock` | Mitigation confirmation validated | Block ID, confirmation bar, price, reason |

### Lifecycle Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `UsedMitigationBlock` | Zone fully consumed | Block ID, used bar, final mitigation percent |
| `InvalidatedMitigationBlock` | Block role negated | Block ID, invalidation bar, price |
| `ExpiredMitigationBlock` | Block aged out | Block ID, expiration bar, age bars |

### Classification Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `NestedMitigationBlock` | Nested relationship detected | Block ID, parent zone ID, parent type |
| `InternalMitigationBlock` | Internal structure scope classified | Block ID, structure scope |
| `ExternalMitigationBlock` | External structure scope classified | Block ID, structure scope |
| `HTFMitigationAligned` | HTF alignment detected | Block ID, HTF block IDs, overlap percent |
| `LTFMitigationNested` | LTF nesting detected | Block ID, LTF block IDs |

### Confluence Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `LiquidityConfluenceMitigation` | Liquidity overlap or sweep proximity | Block ID, matched zone/sweep IDs |
| `OrderBlockConfluenceMitigation` | Order block overlap detected | Block ID, matched OB IDs, overlap percent |
| `FVGConfluenceMitigation` | FVG overlap or CE proximity | Block ID, matched FVG IDs, overlap percent |
| `BreakerConfluenceMitigation` | Breaker overlap detected | Block ID, matched breaker IDs, overlap percent |

### Completion Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `MitigationBlockUpdated` | Analysis cycle complete | Full `MitigationBlockAnalysis` summary |

---

## Contract Events (Event Bus Names)

| Contract Name | Maps To | Trigger |
|---------------|---------|---------|
| `analysis.mitigation.completed` | `MitigationBlockUpdated` | Analysis finished |
| `analysis.mitigation.detected` | `MitigationBlockDetected` | New block |
| `analysis.mitigation.bullish_detected` | `BullishMitigationBlockDetected` | New bullish block |
| `analysis.mitigation.bearish_detected` | `BearishMitigationBlockDetected` | New bearish block |
| `analysis.mitigation.fresh` | `FreshMitigationBlock` | Fresh block registered |
| `analysis.mitigation.partial` | `PartialMitigationBlock` | Partial mitigation |
| `analysis.mitigation.full` | `FullMitigationBlock` | Full mitigation |
| `analysis.mitigation.multi_touch` | `MultiTouchMitigationBlock` | Additional touch |
| `analysis.mitigation.confirmed` | `ConfirmedMitigationBlock` | Confirmation validated |
| `analysis.mitigation.used` | `UsedMitigationBlock` | Zone fully consumed |
| `analysis.mitigation.invalidated` | `InvalidatedMitigationBlock` | Invalidation detected |
| `analysis.mitigation.expired` | `ExpiredMitigationBlock` | Expiration detected |
| `analysis.mitigation.nested` | `NestedMitigationBlock` | Nesting detected |
| `analysis.mitigation.internal` | `InternalMitigationBlock` | Internal scope |
| `analysis.mitigation.external` | `ExternalMitigationBlock` | External scope |
| `analysis.mitigation.htf_aligned` | `HTFMitigationAligned` | HTF alignment |
| `analysis.mitigation.ltf_nested` | `LTFMitigationNested` | LTF nesting |
| `analysis.mitigation.liquidity_confluence` | `LiquidityConfluenceMitigation` | Liquidity confluence |
| `analysis.mitigation.ob_confluence` | `OrderBlockConfluenceMitigation` | OB confluence |
| `analysis.mitigation.fvg_confluence` | `FVGConfluenceMitigation` | FVG confluence |
| `analysis.mitigation.breaker_confluence` | `BreakerConfluenceMitigation` | Breaker confluence |
| `analysis.mitigation.error` | — | Analysis failure |

---

## Event Payload Schemas

### MitigationBlockDetected Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "fresh",
  "high": "4068.30",
  "low": "4067.10",
  "origin_bar_index": 475,
  "origin_time_utc": "2026-07-15T14:00:00+00:00",
  "displacement_bar_index": 476,
  "displacement_time_utc": "2026-07-15T15:00:00+00:00",
  "formation_bar_index": 476,
  "formation_time_utc": "2026-07-15T15:00:00+00:00",
  "mitigation_percent": "0.0",
  "touch_count": 0,
  "is_confirmed": false,
  "confirmation_reason": "Awaiting price interaction",
  "structure_scope": "external",
  "structure_alignment": true,
  "liquidity_confluence": false,
  "order_block_confluence": true,
  "fvg_confluence": false,
  "breaker_confluence": false,
  "is_nested": true,
  "parent_zone_id": "ob-bull-4067_50-def456",
  "parent_zone_type": "order_block",
  "htf_aligned": false,
  "quality": "medium",
  "strength": "0.58",
  "premium_discount": "discount",
  "timeframe": "H1"
}
```

### BullishMitigationBlockDetected Payload

Same as `MitigationBlockDetected` with `direction` guaranteed `"bullish"`.

### BearishMitigationBlockDetected Payload

Same as `MitigationBlockDetected` with `direction` guaranteed `"bearish"`.

### FreshMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "fresh",
  "high": "4068.30",
  "low": "4067.10",
  "touch_count": 0,
  "mitigation_percent": "0.0",
  "is_confirmed": false,
  "confirmation_reason": "No price interaction since formation",
  "timestamp_utc": "2026-07-15T15:00:00+00:00",
  "timeframe": "H1"
}
```

### PartialMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "partial",
  "high": "4068.30",
  "low": "4067.10",
  "touch_count": 1,
  "mitigation_percent": "35.0",
  "first_touch_bar_index": 482,
  "last_touch_bar_index": 482,
  "touch_price": "4067.80",
  "mitigation_mode": "wick",
  "timestamp_utc": "2026-07-16T01:00:00+00:00",
  "timeframe": "H1"
}
```

### FullMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "partial",
  "high": "4068.30",
  "low": "4067.10",
  "touch_count": 2,
  "mitigation_percent": "80.0",
  "last_touch_bar_index": 485,
  "full_mitigation_percent": "75.0",
  "timestamp_utc": "2026-07-16T04:00:00+00:00",
  "timeframe": "H1"
}
```

### MultiTouchMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "partial",
  "touch_count": 3,
  "last_touch_bar_index": 488,
  "touch_price": "4067.50",
  "mitigation_percent": "55.0",
  "bars_since_last_touch": 3,
  "timestamp_utc": "2026-07-16T07:00:00+00:00",
  "timeframe": "H1"
}
```

### ConfirmedMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "confirmed",
  "high": "4068.30",
  "low": "4067.10",
  "confirmation_bar_index": 485,
  "confirmation_time_utc": "2026-07-16T04:00:00+00:00",
  "confirmation_price": "4067.60",
  "confirmation_mode": "wick_touch",
  "confirmation_reason": "Wick entered zone 9 bars after formation; touch count 2",
  "touch_count": 2,
  "mitigation_percent": "45.0",
  "is_confirmed": true,
  "quality": "high",
  "strength": "0.74",
  "timestamp_utc": "2026-07-16T04:00:00+00:00",
  "timeframe": "H1"
}
```

### UsedMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "used",
  "high": "4068.30",
  "low": "4067.10",
  "used_bar_index": 490,
  "mitigation_percent": "85.0",
  "touch_count": 3,
  "timestamp_utc": "2026-07-16T09:00:00+00:00",
  "timeframe": "H1"
}
```

### InvalidatedMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "invalidated",
  "high": "4068.30",
  "low": "4067.10",
  "invalidation_bar_index": 492,
  "invalidation_price": "4066.80",
  "invalidation_mode": "close",
  "prior_status": "confirmed",
  "timestamp_utc": "2026-07-16T11:00:00+00:00",
  "timeframe": "H1"
}
```

### ExpiredMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "status": "expired",
  "high": "4068.30",
  "low": "4067.10",
  "expiration_bar_index": 530,
  "age_bars": 54,
  "prior_status": "fresh",
  "timestamp_utc": "2026-07-18T03:00:00+00:00",
  "timeframe": "H1"
}
```

### NestedMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "is_nested": true,
  "parent_zone_id": "ob-bull-4067_50-def456",
  "parent_zone_type": "order_block",
  "containment_percent": "92.0",
  "timestamp_utc": "2026-07-15T15:00:00+00:00",
  "timeframe": "H1"
}
```

### InternalMitigationBlock Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "structure_scope": "internal",
  "dealing_range_high": "4075.00",
  "dealing_range_low": "4060.00",
  "timestamp_utc": "2026-07-15T15:00:00+00:00",
  "timeframe": "H1"
}
```

### ExternalMitigationBlock Payload

```json
{
  "block_id": "mb-bear-4072_00-ghi789",
  "direction": "bearish",
  "structure_scope": "external",
  "dealing_range_high": "4080.00",
  "dealing_range_low": "4055.00",
  "timestamp_utc": "2026-07-15T18:00:00+00:00",
  "timeframe": "H1"
}
```

### HTFMitigationAligned Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "htf_aligned": true,
  "htf_block_ids": ["mb-bull-4065_00-xyz789"],
  "htf_timeframe": "H4",
  "overlap_percent": "42.0",
  "alignment_score": "0.81",
  "timestamp_utc": "2026-07-15T15:00:00+00:00",
  "timeframe": "H1"
}
```

### LTFMitigationNested Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "ltf_nested": true,
  "ltf_block_ids": ["mb-bull-4068_00-ltf001"],
  "ltf_timeframe": "M15",
  "ltf_block_count": 1,
  "timestamp_utc": "2026-07-15T15:00:00+00:00",
  "timeframe": "H1"
}
```

### LiquidityConfluenceMitigation Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "liquidity_confluence": true,
  "confluence_ids": ["liq-sweep-4066_50-jkl012"],
  "confluence_type": "sweep_proximity",
  "proximity_pips": "4.0",
  "timestamp_utc": "2026-07-15T15:00:00+00:00",
  "timeframe": "H1"
}
```

### OrderBlockConfluenceMitigation Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "order_block_confluence": true,
  "confluence_ids": ["ob-bull-4067_50-def456"],
  "overlap_percent": "68.0",
  "timestamp_utc": "2026-07-15T15:00:00+00:00",
  "timeframe": "H1"
}
```

### FVGConfluenceMitigation Payload

```json
{
  "block_id": "mb-bull-4068_30-abc123",
  "direction": "bullish",
  "fvg_confluence": true,
  "confluence_ids": ["fvg-bull-4066_00-mno345"],
  "overlap_percent": "28.0",
  "ce_proximity_pips": "2.1",
  "timestamp_utc": "2026-07-15T15:00:00+00:00",
  "timeframe": "H1"
}
```

### BreakerConfluenceMitigation Payload

```json
{
  "block_id": "mb-bear-4072_00-ghi789",
  "direction": "bearish",
  "breaker_confluence": true,
  "confluence_ids": ["brk-bear-4073_00-pqr678"],
  "overlap_percent": "45.0",
  "timestamp_utc": "2026-07-15T18:00:00+00:00",
  "timeframe": "H1"
}
```

### MitigationBlockUpdated Payload

Full `MitigationBlockAnalysis` serialized:

```json
{
  "symbol": "GOLD.i#",
  "timeframe": "H1",
  "timestamp_utc": "2026-07-16T09:00:00+00:00",
  "block_count": 4,
  "fresh_count": 1,
  "partial_count": 1,
  "confirmed_count": 1,
  "used_count": 0,
  "invalidated_count": 0,
  "expired_count": 1,
  "nested_count": 2,
  "htf_aligned_count": 1,
  "bias": "bullish",
  "confidence": "0.69",
  "evidence": [
    "1 confirmed bullish mitigation block in discount",
    "HTF alignment on mb-bull-4068_30-abc123",
    "Order block confluence on mb-bull-4068_30-abc123"
  ]
}
```

### Error Payload (`analysis.mitigation.error`)

```json
{
  "error_code": "MMBE_INVALID_STRUCTURE",
  "message": "Structure context symbol/timeframe mismatch",
  "symbol": "GOLD.i#",
  "timeframe": "H1",
  "timestamp_utc": "2026-07-16T09:00:00+00:00"
}
```

---

## Consumed Events

| Event | Source | Action |
|-------|--------|--------|
| `market.candle.closed` | Market Data Engine | Trigger analysis cycle (orchestrator) |
| `analysis.structure.completed` | Market Structure Engine | Optional context enrichment |
| `analysis.liquidity.completed` | Market Liquidity Engine | Extract `LiquidityState` for confluence |
| `analysis.order_block.completed` | Order Block Engine | Extract `order_blocks` for confluence/nesting |
| `analysis.order_block.mitigated` | Order Block Engine | Optional parent invalidation signal |
| `analysis.fvg.completed` | Fair Value Gap Engine | Extract `FairValueGapState` for confluence |
| `analysis.fvg.mitigated` | Fair Value Gap Engine | Optional parent invalidation signal |
| `analysis.breaker.completed` | Breaker Block Engine | Extract breaker blocks for confluence |
| `analysis.breaker.confirmed` | Breaker Block Engine | Optional confluence refresh signal |
| `analysis.mitigation.completed` | Mitigation Block Engine (HTF) | HTF blocks for LTF alignment |
| `system.config.updated` | Config service | Reload parameters via `handle_config_updated()` |

### Consumption Notes

The Mitigation Block Engine does **not** subscribe to events directly in Sprint 7.1. Event consumption is orchestrator responsibility. The table above defines the integration contract for future wiring.

When upstream zone events (`analysis.order_block.mitigated`, `analysis.fvg.mitigated`) are consumed, the orchestrator may trigger incremental mitigation analysis or pass updated upstream state on the next full cycle.

For HTF/LTF workflows, the orchestrator runs HTF analysis first, then passes `htf_mitigation_blocks` into the LTF `analyze()` call.

---

## Event Ordering Guarantees

Within a single `analyze()` invocation:

| Order | Event Sequence |
|-------|---------------|
| 1 | Detection events (`MitigationBlockDetected`, directional variants) |
| 2 | Fresh events (`FreshMitigationBlock`) |
| 3 | Classification events (`NestedMitigationBlock`, `InternalMitigationBlock`, `ExternalMitigationBlock`) |
| 4 | Confluence events (liquidity, OB, FVG, breaker) |
| 5 | MTF events (`HTFMitigationAligned`, `LTFMitigationNested`) |
| 6 | Mitigation events (`PartialMitigationBlock`, `MultiTouchMitigationBlock`, `FullMitigationBlock`) |
| 7 | Confirmation events (`ConfirmedMitigationBlock`) |
| 8 | Lifecycle events (`UsedMitigationBlock`, `InvalidatedMitigationBlock`, `ExpiredMitigationBlock`) |
| 9 | Completion event (`MitigationBlockUpdated`) |

Events for the same block are ordered chronologically by lifecycle stage.

---

## Event Idempotency

| Scenario | Behavior |
|----------|----------|
| Same block re-analyzed unchanged | No duplicate detection events |
| Status transition | Only new lifecycle event emitted |
| Touch on same bar | No duplicate `MultiTouchMitigationBlock` |
| Touch on new bar | `MultiTouchMitigationBlock` when `touch_count` increments |
| Confluence re-detected | Confluence event emitted once per analysis cycle |
| Re-confirmation on confirmed block | No duplicate `ConfirmedMitigationBlock` |

Publisher tracks `(block_id, event_type, bar_index)` within analysis cycle to prevent duplicates.

---

## Subscriber Pattern (Planned)

```python
publisher = MitigationBlockEventPublisher()

def on_confirmed(event: MitigationBlockAnalysisEvent) -> None:
    payload = event.payload
    # downstream handling

publisher.subscribe("ConfirmedMitigationBlock", on_confirmed)
publisher.subscribe("*", log_all_events)
```

Consistent with in-memory pub/sub pattern from Sprints 1–6.

---

## Timeline Events in Analysis Output

`MitigationBlockAnalysis.events` contains a chronological `list[MitigationBlockEvent]` mirroring published events for the current cycle. Each entry includes:

| Field | Purpose |
|-------|---------|
| `kind` | Event classification |
| `timestamp_utc` | When event occurred |
| `description` | Human-readable summary |
| `block_id` | Affected block |
| `touch_count` | Current touch count when relevant |
| `mitigation_percent` | Current mitigation percent when relevant |
| `parent_zone_id` | Parent zone when nested |

Timeline events are included in analysis output regardless of whether an external subscriber is registered.

---

## Future Event Bus Integration

| Sprint 7.1 | Future |
|------------|--------|
| In-memory `MitigationBlockEventPublisher` | Global event bus adapter |
| Contract names documented | Registered in platform event registry |
| No persistence | Optional SQLite event log |

Adapter must preserve payload schemas and contract names defined in this document.

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
