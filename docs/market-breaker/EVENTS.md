# Breaker Block Engine — Events

**Engine ID:** `market_breaker`  
**Sprint:** 6.1 (Architecture specification)  
**Status:** Not implemented

---

## Event Envelope

All events use the `BreakerBlockAnalysisEvent` envelope (consistent with Sprints 1–5):

```python
{
    "event_id": "uuid",
    "timestamp_utc": "ISO-8601",
    "symbol": "GOLD.i#",
    "source_engine": "market_breaker",
    "event_type": "BullishBreakerBlockDetected",
    "payload": { ... }
}
```

---

## Published Events

### Detection Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `BreakerBlockDetected` | Any new breaker candidate identified | Breaker summary |
| `BullishBreakerBlockDetected` | New bullish breaker | Breaker ID, zone bounds, source reference |
| `BearishBreakerBlockDetected` | New bearish breaker | Breaker ID, zone bounds, source reference |
| `CandidateBreakerBlock` | Breaker registered as candidate | Breaker ID, direction, source_id, status |

### Confirmation Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `ConfirmedBreakerBlock` | Retest confirmation validated | Breaker ID, confirmation bar, price, reason |

### Lifecycle Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `MitigatedBreakerBlock` | Breaker zone addressed | Breaker ID, mitigation mode, price |
| `InvalidatedBreakerBlock` | Breaker role negated | Breaker ID, invalidation bar, price |
| `ExpiredBreakerBlock` | Breaker aged out | Breaker ID, expiration bar, age bars |

### Confluence Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `LiquidityConfluenceBreaker` | Liquidity overlap or sweep proximity detected | Breaker ID, matched zone/sweep IDs |
| `FVGConfluenceBreaker` | FVG overlap or CE proximity detected | Breaker ID, matched FVG IDs, overlap percent |

### Completion Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `BreakerBlockUpdated` | Analysis cycle complete | Full `BreakerBlockAnalysis` |

---

## Contract Events (Event Bus Names)

| Contract Name | Maps To | Trigger |
|---------------|---------|---------|
| `analysis.breaker.completed` | `BreakerBlockUpdated` | Analysis finished |
| `analysis.breaker.detected` | `BreakerBlockDetected` | New breaker |
| `analysis.breaker.bullish_detected` | `BullishBreakerBlockDetected` | New bullish breaker |
| `analysis.breaker.bearish_detected` | `BearishBreakerBlockDetected` | New bearish breaker |
| `analysis.breaker.candidate` | `CandidateBreakerBlock` | Candidate registered |
| `analysis.breaker.confirmed` | `ConfirmedBreakerBlock` | Confirmation validated |
| `analysis.breaker.mitigated` | `MitigatedBreakerBlock` | Mitigation detected |
| `analysis.breaker.invalidated` | `InvalidatedBreakerBlock` | Invalidation detected |
| `analysis.breaker.expired` | `ExpiredBreakerBlock` | Expiration detected |
| `analysis.breaker.liquidity_confluence` | `LiquidityConfluenceBreaker` | Liquidity confluence |
| `analysis.breaker.fvg_confluence` | `FVGConfluenceBreaker` | FVG confluence |
| `analysis.breaker.error` | — | Analysis failure |

---

## Event Payload Schemas

### BreakerBlockDetected Payload

```json
{
  "breaker_id": "brk-bear-4075_20-abc123",
  "direction": "bearish",
  "status": "candidate",
  "high": "4075.20",
  "low": "4073.50",
  "source_type": "order_block",
  "source_id": "ob-bull-4075_20-def456",
  "source_direction": "bullish",
  "invalidation_bar_index": 478,
  "invalidation_time_utc": "2026-07-15T17:00:00+00:00",
  "formation_bar_index": 479,
  "formation_time_utc": "2026-07-15T18:00:00+00:00",
  "is_confirmed": false,
  "confirmation_reason": "Awaiting retest",
  "quality": "medium",
  "strength": "0.62",
  "structure_alignment": true,
  "liquidity_confluence": false,
  "fvg_confluence": true,
  "premium_discount": "premium",
  "timeframe": "H1"
}
```

### BullishBreakerBlockDetected Payload

Same as `BreakerBlockDetected` with `direction` guaranteed `"bullish"`.

### BearishBreakerBlockDetected Payload

Same as `BreakerBlockDetected` with `direction` guaranteed `"bearish"`.

### CandidateBreakerBlock Payload

```json
{
  "breaker_id": "brk-bear-4075_20-abc123",
  "direction": "bearish",
  "status": "candidate",
  "high": "4075.20",
  "low": "4073.50",
  "source_id": "ob-bull-4075_20-def456",
  "source_type": "order_block",
  "is_confirmed": false,
  "confirmation_reason": "Awaiting retest within 50 bars",
  "timestamp_utc": "2026-07-15T18:00:00+00:00",
  "timeframe": "H1"
}
```

### ConfirmedBreakerBlock Payload

```json
{
  "breaker_id": "brk-bear-4075_20-abc123",
  "direction": "bearish",
  "status": "confirmed",
  "high": "4075.20",
  "low": "4073.50",
  "source_id": "ob-bull-4075_20-def456",
  "confirmation_bar_index": 485,
  "confirmation_time_utc": "2026-07-16T00:00:00+00:00",
  "confirmation_price": "4074.80",
  "confirmation_mode": "wick_touch",
  "confirmation_reason": "Wick entered zone 6 bars after invalidation",
  "is_confirmed": true,
  "quality": "high",
  "strength": "0.78",
  "timestamp_utc": "2026-07-16T00:00:00+00:00",
  "timeframe": "H1"
}
```

### MitigatedBreakerBlock Payload

```json
{
  "breaker_id": "brk-bear-4075_20-abc123",
  "direction": "bearish",
  "status": "mitigated",
  "high": "4075.20",
  "low": "4073.50",
  "mitigation_bar_index": 490,
  "mitigation_mode": "wick",
  "mitigation_price": "4074.20",
  "timestamp_utc": "2026-07-16T05:00:00+00:00",
  "timeframe": "H1"
}
```

### InvalidatedBreakerBlock Payload

```json
{
  "breaker_id": "brk-bear-4075_20-abc123",
  "direction": "bearish",
  "status": "invalidated",
  "high": "4075.20",
  "low": "4073.50",
  "invalidation_breaker_bar_index": 492,
  "invalidation_price": "4075.50",
  "invalidation_mode": "close",
  "timestamp_utc": "2026-07-16T07:00:00+00:00",
  "timeframe": "H1"
}
```

### ExpiredBreakerBlock Payload

```json
{
  "breaker_id": "brk-bear-4075_20-abc123",
  "direction": "bearish",
  "status": "expired",
  "high": "4075.20",
  "low": "4073.50",
  "expiration_bar_index": 530,
  "age_bars": 52,
  "timestamp_utc": "2026-07-18T02:00:00+00:00",
  "timeframe": "H1"
}
```

### LiquidityConfluenceBreaker Payload

```json
{
  "breaker_id": "brk-bear-4075_20-abc123",
  "direction": "bearish",
  "liquidity_confluence": true,
  "liquidity_confluence_ids": ["liq-sweep-4076_00-ghi789"],
  "confluence_type": "sweep_proximity",
  "proximity_pips": "3.5",
  "timestamp_utc": "2026-07-16T00:00:00+00:00",
  "timeframe": "H1"
}
```

### FVGConfluenceBreaker Payload

```json
{
  "breaker_id": "brk-bear-4075_20-abc123",
  "direction": "bearish",
  "fvg_confluence": true,
  "fvg_confluence_ids": ["fvg-bear-4074_00-jkl012"],
  "overlap_percent": "35.0",
  "ce_proximity_pips": "1.2",
  "timestamp_utc": "2026-07-16T00:00:00+00:00",
  "timeframe": "H1"
}
```

### BreakerBlockUpdated Payload

Full `BreakerBlockAnalysis` serialized:

```json
{
  "symbol": "GOLD.i#",
  "timeframe": "H1",
  "timestamp_utc": "2026-07-16T09:00:00+00:00",
  "breaker_count": 3,
  "candidate_count": 1,
  "confirmed_count": 1,
  "mitigated_count": 0,
  "invalidated_count": 0,
  "expired_count": 1,
  "bias": "bearish",
  "confidence": "0.71",
  "evidence": [
    "1 confirmed bearish breaker in premium",
    "FVG confluence on brk-bear-4075_20-abc123"
  ]
}
```

### Error Payload (`analysis.breaker.error`)

```json
{
  "error_code": "MBE_INVALID_ORDER_BLOCKS",
  "message": "Input contains non-invalidated order blocks",
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
| `analysis.order_block.completed` | Order Block Engine | Extract `invalidated_blocks` for formation |
| `analysis.order_block.invalidated` | Order Block Engine | Early candidate registration signal |
| `analysis.fvg.completed` | Fair Value Gap Engine | Extract `FairValueGapState` for confluence |
| `analysis.fvg.invalidated` | Fair Value Gap Engine | Optional FVG-derived formation |
| `system.config.updated` | Config service | Reload parameters via `handle_config_updated()` |

### Consumption Notes

The Breaker Block Engine does **not** subscribe to events directly in Sprint 6.1. Event consumption is orchestrator responsibility. The table above defines the integration contract for future wiring.

When `analysis.order_block.invalidated` is consumed, the orchestrator may trigger an incremental breaker analysis without waiting for the full pipeline cycle.

---

## Event Ordering Guarantees

Within a single `analyze()` invocation:

| Order | Event Sequence |
|-------|---------------|
| 1 | Detection events (`BreakerBlockDetected`, directional variants) |
| 2 | Candidate events (`CandidateBreakerBlock`) |
| 3 | Confirmation events (`ConfirmedBreakerBlock`) |
| 4 | Confluence events (`LiquidityConfluenceBreaker`, `FVGConfluenceBreaker`) |
| 5 | Lifecycle events (`MitigatedBreakerBlock`, `InvalidatedBreakerBlock`, `ExpiredBreakerBlock`) |
| 6 | Completion event (`BreakerBlockUpdated`) |

Events for the same breaker are ordered chronologically by lifecycle stage.

---

## Event Idempotency

| Scenario | Behavior |
|----------|----------|
| Same breaker re-analyzed unchanged | No duplicate detection events |
| Status transition | Only new lifecycle event emitted |
| Confluence re-detected | Confluence event emitted once per analysis cycle |
| Re-confirmation attempt on confirmed breaker | No duplicate `ConfirmedBreakerBlock` |

Publisher tracks `(breaker_id, event_type, bar_index)` within analysis cycle to prevent duplicates.

---

## Subscriber Pattern (Planned)

```python
publisher = BreakerBlockEventPublisher()

def on_confirmed(event: BreakerBlockAnalysisEvent) -> None:
    payload = event.payload
    # downstream handling

publisher.subscribe("ConfirmedBreakerBlock", on_confirmed)
publisher.subscribe("*", log_all_events)
```

Consistent with in-memory pub/sub pattern from Sprints 1–5.

---

## Timeline Events in Analysis Output

`BreakerBlockAnalysis.events` contains a chronological `list[BreakerBlockEvent]` mirroring published events for the current cycle. Each entry includes:

| Field | Purpose |
|-------|---------|
| `kind` | Event classification |
| `timestamp_utc` | When event occurred |
| `description` | Human-readable summary |
| `breaker_id` | Affected breaker |
| `source_id` | Origin block/gap when relevant |

Timeline events are included in analysis output regardless of whether an external subscriber is registered.

---

## Future Event Bus Integration

| Sprint 6.1 | Future |
|------------|--------|
| In-memory `BreakerBlockEventPublisher` | Global event bus adapter |
| Contract names documented | Registered in platform event registry |
| No persistence | Optional SQLite event log |

Adapter must preserve payload schemas and contract names defined in this document.

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
