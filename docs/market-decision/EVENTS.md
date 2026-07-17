# Decision Engine — Events

**Engine ID:** `market_decision`  
**Sprint:** 10.1 (Architecture specification)  
**Status:** Not implemented

---

## Event Envelope

All events use the `DecisionAnalysisEvent` envelope (consistent with Sprints 1–9):

```python
{
    "event_id": "uuid",
    "timestamp_utc": "ISO-8601",
    "symbol": "GOLD.i#",
    "source_engine": "market_decision",
    "event_type": "DecisionCreated",
    "payload": { ... }
}
```

---

## Published Events

### Decision Lifecycle Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `DecisionCreated` | Decision cycle completes (any terminal state) | `decision_id`, `state`, `direction`, `confidence` |
| `DecisionPublished` | `BUY` or `SELL` decision passes all gates | Full `TradeDecision` |
| `DecisionRejected` | `NO_TRADE` or `INVALID` decision | `decision_id`, `blocking_reasons`, `error_codes` |
| `DecisionUpdated` | Active decision revised (evidence change) | Prior and current `TradeDecision` summary |
| `DecisionExpired` | `valid_until_utc` elapsed | `decision_id`, `original_state`, `expired_at_utc` |

### Internal Pipeline Events (Optional — Sprint 10.2)

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `EvidenceCollected` | Evidence bundle assembled | Availability flags, engine count |
| `ConflictDetected` | Conflict severity ≥ warn | `conflict_ratio`, `severity`, `conflicting_engines` |
| `GateFailed` | Validation gate short-circuits | Gate name, error code, blocking reason |
| `ConfidenceScored` | Confidence computation complete | `confidence`, penalties, bonuses |

Internal events are published only when `config.publish_pipeline_events: true` (default `false`). They are not part of the contract bus.

---

## Contract Events (Event Bus Names)

These names maintain compatibility with the legacy Decision Engine contract ([decision-engine.md](../engines/decision-engine.md)) and downstream consumers (Telegram Engine, Dashboard).

| Contract Name | Maps To | Trigger |
|---------------|---------|---------|
| `decision.completed` | `DecisionCreated` | Any decision cycle complete |
| `decision.signal.published` | `DecisionPublished` | `BUY` or `SELL` decision |
| `decision.no_trade.published` | `DecisionRejected` | `NO_TRADE` decision |
| `decision.wait.published` | — | `WAIT` state (optional; not published by default) |
| `decision.expired` | `DecisionExpired` | Decision validity expired |
| `decision.error` | `DecisionRejected` | `INVALID` state |
| `decision.updated` | `DecisionUpdated` | Active decision revised |

### Legacy Mapping Notes

| Legacy Event | Sprint 10.1 Behavior |
|--------------|---------------------|
| `decision.completed` | Fired for all terminal states including `NO_TRADE` |
| `decision.signal.published` | Fired only for `BUY`/`SELL` |
| `decision.no_trade.published` | Fired for `NO_TRADE` (not `INVALID`) |
| `decision.wait.published` | Suppressed by default; enable via config |
| `decision.error` | Fired for `INVALID` with `error_codes` |

---

## Event Payload Schemas

### DecisionCreated Payload

```json
{
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "GOLD.i#",
  "timestamp_utc": "2026-07-16T14:30:00+00:00",
  "state": "NO_TRADE",
  "direction": "NONE",
  "confidence": 58,
  "quality_score": 62,
  "quality_tier": "medium",
  "engines_available": 7,
  "engines_stale": 1
}
```

### DecisionPublished Payload

Full `TradeDecision.model_dump(mode="json")`:

```json
{
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "GOLD.i#",
  "timestamp_utc": "2026-07-16T14:30:00+00:00",
  "state": "BUY",
  "direction": "BUY",
  "entry": {
    "price": null,
    "zone_high": 2346.20,
    "zone_low": 2345.80,
    "entry_type": "zone",
    "source_engine": "order_block",
    "source_zone_id": "ob-12345",
    "distance_pips": 3.5
  },
  "stop_loss": 2343.50,
  "take_profit": [2350.00, 2353.20],
  "risk_reward_ratio": 2.5,
  "confidence": 78,
  "quality_score": 82,
  "quality_tier": "high",
  "reasons": [
    "Bullish structure trend with recent BOS",
    "Sell-side liquidity swept within 30 bars",
    "Active bullish order block in discount territory",
    "Price in discount zone with OTE alignment",
    "London open kill zone active"
  ],
  "blocking_reasons": [],
  "evidence_summary": [
    {
      "engine_id": "market_structure",
      "available": true,
      "stale": false,
      "direction_bias": "bullish",
      "confidence": 0.82,
      "weight": 0.20,
      "weighted_contribution": 0.148,
      "quality_tier": "high",
      "key_evidence": ["HH/HL sequence intact", "Bullish BOS at 2344.00"]
    }
  ],
  "risk_summary": {
    "risk_reward_ratio": 2.5,
    "stop_size_pips": 22.0,
    "spread_pips": 2.5,
    "min_rr_met": true,
    "max_rr_met": true,
    "spread_acceptable": true,
    "stop_size_acceptable": true,
    "confidence_acceptable": true,
    "session_allowed": true,
    "news_blocked": false,
    "news_block_reason": null,
    "rule_outcomes": []
  },
  "warnings": [],
  "error_codes": [],
  "valid_until_utc": "2026-07-16T15:30:00+00:00",
  "metadata": {
    "pipeline_version": "0.1.0",
    "config_hash": "abc123",
    "duration_ms": 45,
    "engines_available": 8,
    "engines_stale": 0,
    "conflict_severity": "low",
    "zone_confluence_count": 3
  }
}
```

### DecisionRejected Payload

```json
{
  "decision_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "symbol": "GOLD.i#",
  "timestamp_utc": "2026-07-16T14:30:00+00:00",
  "state": "NO_TRADE",
  "direction": "NONE",
  "confidence": 52,
  "blocking_reasons": [
    "Confidence 52 below minimum 65",
    "Conflicting evidence: market_structure bullish vs market_premium_discount bearish"
  ],
  "error_codes": ["LOW_CONFIDENCE", "CONFLICTING_EVIDENCE"],
  "evidence_summary": [],
  "warnings": ["market_liquidity evidence stale (age 420s)"]
}
```

### DecisionUpdated Payload

```json
{
  "prior_decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "decision_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "symbol": "GOLD.i#",
  "timestamp_utc": "2026-07-16T14:35:00+00:00",
  "prior_state": "BUY",
  "current_state": "NO_TRADE",
  "update_reason": "Structure CHoCH detected — bullish bias invalidated",
  "confidence_delta": -22
}
```

### DecisionExpired Payload

```json
{
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "GOLD.i#",
  "original_state": "BUY",
  "direction": "BUY",
  "created_at_utc": "2026-07-16T14:30:00+00:00",
  "expired_at_utc": "2026-07-16T15:30:00+00:00",
  "validity_minutes": 60
}
```

---

## Consumed Events

| Contract Name | Source Engine | Action |
|---------------|---------------|--------|
| `analysis.structure.completed` | Market Structure (`market_structure`) | Cache `MarketStructure` |
| `analysis.liquidity.completed` | Market Liquidity (`market_liquidity`) | Cache `LiquidityAnalysis` |
| `analysis.order_block.completed` | Order Block (`order_block`) | Cache `OrderBlockAnalysis` |
| `analysis.fvg.completed` | Fair Value Gap (`fair_value_gap`) | Cache `FairValueGapAnalysis` |
| `analysis.breaker.completed` | Breaker Block (`market_breaker`) | Cache `BreakerBlockAnalysis` |
| `analysis.mitigation.completed` | Mitigation Block (`market_mitigation`) | Cache `MitigationBlockAnalysis` |
| `analysis.premium_discount.completed` | Premium / Discount (`market_premium_discount`) | Cache `PremiumDiscountAnalysis` |
| `analysis.session.completed` | Market Sessions (`market_sessions`) | Cache `SessionAnalysis` |
| `market.tick.received` | Market Data (`market_data`) | Update `current_price`, `spread` |
| `market.candle.closed` | Market Data (`market_data`) | Optional price refresh |
| `system.config.updated` | Config service | Reload `market_decision` config |

### Future Consumed Events (Not Sprint 10.1 Scope)

| Contract Name | Source | Notes |
|---------------|--------|-------|
| `analysis.smart_money.completed` | Smart Money Engine | Legacy contract; not implemented |
| `analysis.trend.completed` | Trend Engine | Legacy contract; not implemented |
| `analysis.news_macro.completed` | News & Macro Engine | Replaces news restriction hook |
| `analysis.risk.completed` | Risk Engine | Legacy contract; v1.0 uses internal risk rules |

---

## Event Flow Diagram

```
Upstream Engines                    Decision Engine                    Downstream
─────────────────                   ───────────────                    ──────────

analysis.structure.completed ──┐
analysis.liquidity.completed ──┤
analysis.order_block.completed─┤
analysis.fvg.completed ────────┤    ┌─────────────────┐
analysis.breaker.completed ────├───►│  Evidence Cache  │
analysis.mitigation.completed ─┤    └────────┬────────┘
analysis.premium_discount.completed──┤       │
analysis.session.completed ────┤              ▼
market.tick.received ──────────┘    ┌─────────────────┐
                                    │  decide() cycle  │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
            DecisionCreated          DecisionPublished          DecisionRejected
                    │                        │                        │
                    ▼                        ▼                        ▼
            decision.completed      decision.signal.published  decision.no_trade.published
                                             │                        │
                                             ▼                        ▼
                                      Telegram Engine            Dashboard
                                      (signal alert)             (no-trade log)

Active BUY/SELL + evidence change:
    DecisionUpdated → decision.updated

valid_until_utc elapsed:
    DecisionExpired → decision.expired
```

---

## DecisionEventPublisher (Planned)

```python
class DecisionEventPublisher:
    def subscribe(self, event_type: str, handler: Callable) -> None: ...
    def publish(self, event: DecisionAnalysisEvent) -> None: ...

    def publish_decision_created(self, decision: TradeDecision) -> None: ...
    def publish_decision_published(self, decision: TradeDecision) -> None: ...
    def publish_decision_rejected(self, decision: TradeDecision) -> None: ...
    def publish_decision_updated(
        self, prior: TradeDecision, current: TradeDecision, reason: str
    ) -> None: ...
    def publish_decision_expired(self, decision: TradeDecision) -> None: ...
```

### Contract Bus Publishing

```python
def publish_decision_published(self, decision: TradeDecision) -> None:
    self.publish(DecisionAnalysisEvent(
        event_type="DecisionPublished",
        payload=decision.model_dump(mode="json"),
    ))
    # Contract alias
    self._bus.emit("decision.signal.published", decision)
    self._bus.emit("decision.completed", decision)
```

---

## Subscriber Examples

### Telegram Engine

```python
event_bus.on("decision.signal.published", telegram.send_signal_alert)
event_bus.on("decision.no_trade.published", telegram.send_no_trade_info)  # optional
event_bus.on("decision.expired", telegram.send_expiry_notice)
```

### Dashboard

```python
event_bus.on("decision.completed", dashboard.render_decision_panel)
event_bus.on("decision.updated", dashboard.refresh_decision_card)
event_bus.on("decision.expired", dashboard.archive_decision)
```

### Pipeline Orchestrator

```python
event_bus.on("analysis.session.completed", decision_engine.handle_session_completed)
event_bus.on("analysis.premium_discount.completed", decision_engine.handle_premium_discount_completed)
event_bus.on("market.tick.received", decision_engine.handle_tick_received)
```

---

## Event Ordering Guarantees

| Guarantee | Description |
|-----------|-------------|
| Per symbol FIFO | Events for the same symbol are processed in emission order |
| `DecisionCreated` before outcome | `DecisionCreated` always precedes `DecisionPublished` or `DecisionRejected` |
| No duplicate `decision_id` | Each cycle produces a unique `decision_id` |
| Expiry idempotent | `DecisionExpired` emitted at most once per `decision_id` |

---

## Event Type Mapping Table

| Internal `event_type` | Contract Bus Name | `TradeDecision.state` |
|-----------------------|-------------------|-----------------------|
| `DecisionCreated` | `decision.completed` | Any terminal |
| `DecisionPublished` | `decision.signal.published` | `BUY`, `SELL` |
| `DecisionRejected` | `decision.no_trade.published` | `NO_TRADE` |
| `DecisionRejected` | `decision.error` | `INVALID` |
| `DecisionUpdated` | `decision.updated` | Any change |
| `DecisionExpired` | `decision.expired` | Prior `BUY`/`SELL` |

---

## Error Event Payload

When `state == INVALID`:

```json
{
  "decision_id": "d4e5f6a7-b8c9-0123-def0-234567890123",
  "symbol": "GOLD.i#",
  "timestamp_utc": "2026-07-16T14:30:00+00:00",
  "state": "INVALID",
  "error_codes": ["DECISION_VALIDATION_FAILED"],
  "blocking_reasons": ["Symbol 'EURUSD' not supported; expected XAUUSD/GOLD.i#"],
  "source": "market_decision"
}
```

Contract bus: `decision.error`

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Legacy Decision Contract | [../engines/decision-engine.md](../engines/decision-engine.md) |
| Telegram Engine | [../engines/telegram-engine.md](../engines/telegram-engine.md) |
| Event Bus Convention | [../engines/README.md](../engines/README.md) |
