# Order Block Engine — Events

**Engine ID:** `order_block`  
**Sprint:** 4.1 (Architecture specification)  
**Status:** Not implemented

---

## Event Envelope

All events use the `OrderBlockAnalysisEvent` envelope (consistent with Sprints 1–3):

```python
{
    "event_id": "uuid",
    "timestamp_utc": "ISO-8601",
    "symbol": "GOLD.i#",
    "source_engine": "order_block",
    "event_type": "BullishOrderBlockDetected",
    "payload": { ... }
}
```

---

## Published Events

### Lifecycle Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `OrderBlockDetected` | Any new order block identified | `OrderBlock` summary |
| `BullishOrderBlockDetected` | New bullish order block | Block ID, zone bounds, quality |
| `BearishOrderBlockDetected` | New bearish order block | Block ID, zone bounds, quality |
| `FreshOrderBlock` | Block confirmed untested | Block ID, direction, zone |
| `MitigatedOrderBlock` | Price re-entered zone | Block ID, mitigation bar, price |
| `InvalidatedOrderBlock` | Zone broken | Block ID, invalidation bar, price |
| `OrderBlockUpdated` | Analysis cycle complete | Full `OrderBlockAnalysis` |

### Contract Events (Event Bus Names)

| Contract Name | Maps To | Trigger |
|---------------|---------|---------|
| `analysis.order_block.completed` | `OrderBlockUpdated` | Analysis finished |
| `analysis.order_block.detected` | `OrderBlockDetected` | New block |
| `analysis.order_block.bullish_detected` | `BullishOrderBlockDetected` | New bullish block |
| `analysis.order_block.bearish_detected` | `BearishOrderBlockDetected` | New bearish block |
| `analysis.order_block.fresh` | `FreshOrderBlock` | Fresh status confirmed |
| `analysis.order_block.mitigated` | `MitigatedOrderBlock` | Mitigation detected |
| `analysis.order_block.invalidated` | `InvalidatedOrderBlock` | Invalidation detected |
| `analysis.order_block.error` | — | Analysis failure |

---

## Event Payload Schemas

### OrderBlockDetected Payload

```json
{
  "block_id": "ob-bull-4081_14-abc123",
  "direction": "bullish",
  "status": "fresh",
  "high": "4081.14",
  "low": "4076.50",
  "origin_time_utc": "2026-07-15T21:00:00+00:00",
  "origin_bar_index": 482,
  "quality": "high",
  "strength": "0.78",
  "timeframe": "H1"
}
```

### MitigatedOrderBlock Payload

```json
{
  "block_id": "ob-bull-4081_14-abc123",
  "direction": "bullish",
  "status": "mitigated",
  "high": "4081.14",
  "low": "4076.50",
  "mitigation_bar_index": 490,
  "mitigation_price": "4079.00",
  "timestamp_utc": "2026-07-16T05:00:00+00:00",
  "timeframe": "H1"
}
```

### InvalidatedOrderBlock Payload

```json
{
  "block_id": "ob-bull-4081_14-abc123",
  "direction": "bullish",
  "status": "invalidated",
  "high": "4081.14",
  "low": "4076.50",
  "invalidation_bar_index": 495,
  "invalidation_price": "4074.20",
  "timestamp_utc": "2026-07-16T10:00:00+00:00",
  "timeframe": "H1"
}
```

### analysis.order_block.completed Payload

Full `OrderBlockAnalysis.model_dump(mode="json")`.

---

## Consumed Events

| Event | Source Engine | Action |
|-------|---------------|--------|
| `market.candle.closed` | Market Data | Trigger order block analysis (orchestrator) |
| `analysis.structure.completed` | Market Structure | Enrich with structure context |
| `analysis.liquidity.completed` | Market Liquidity | Enrich with liquidity confluence |
| `system.config.updated` | Config service | Reload `OrderBlockConfig` |

### Consumption Notes

| Event | Required | Fallback |
|-------|----------|----------|
| `market.candle.closed` | Yes (event-driven mode) | Batch `analyze()` call with candle list |
| `analysis.structure.completed` | No | Direct `MarketStructure` injection |
| `analysis.liquidity.completed` | No | Direct `LiquidityAnalysis` injection or skip |
| `system.config.updated` | No | Manual `handle_config_updated()` |

---

## Event Flow Diagram

```
market.candle.closed
        │
        ├──────────────────────────────────────┐
        │                                      │
        ▼                                      ▼
analysis.structure.completed     analysis.liquidity.completed
        │                                      │
        └──────────────┬───────────────────────┘
                       │
                       ▼
              Order Block Engine
              .analyze(candles, structure, liquidity)
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
BullishOrderBlock  MitigatedOrderBlock  InvalidatedOrderBlock
Detected           │                    │
         │         ▼                    ▼
         ▼    analysis.order_block   analysis.order_block
FreshOrderBlock   .mitigated          .invalidated
         │
         ▼
analysis.order_block.completed
         │
         ▼
   Future: Decision Engine
```

---

## Publisher Interface

```python
class OrderBlockEventPublisher:
    def subscribe(self, event_type: str, handler: EventHandler) -> None: ...
    def publish(self, event: OrderBlockAnalysisEvent) -> None: ...
    def publish_block_detected(self, block: OrderBlock, symbol: str) -> None: ...
    def publish_bullish_block(self, block: OrderBlock, symbol: str) -> None: ...
    def publish_bearish_block(self, block: OrderBlock, symbol: str) -> None: ...
    def publish_fresh_block(self, block: OrderBlock, symbol: str) -> None: ...
    def publish_mitigated_block(self, block: OrderBlock, symbol: str) -> None: ...
    def publish_invalidated_block(self, block: OrderBlock, symbol: str) -> None: ...
    def publish_analysis_completed(self, analysis: OrderBlockAnalysis) -> None: ...
    def clear_handlers(self) -> None: ...
```

Wildcard `"*"` subscription supported (consistent with Sprints 1–3).

---

## Event Ordering

Events within a single analysis cycle are emitted in lifecycle order:

1. Individual block detections (`BullishOrderBlockDetected`, `BearishOrderBlockDetected`)
2. Status transitions (`FreshOrderBlock`, `MitigatedOrderBlock`, `InvalidatedOrderBlock`)
3. Completion (`OrderBlockUpdated` / `analysis.order_block.completed`)

Timeline events in `OrderBlockAnalysis.events` are sorted by `timestamp_utc`.

---

## Error Events

| Event | Code | Payload |
|-------|------|---------|
| `analysis.order_block.error` | `OBE_*` | `{ "code": "OBE_INSUFFICIENT_DATA", "message": "...", "details": {} }` |

Error events are published; they do not crash the orchestrator unless configured to fail-fast.

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)
- [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)
