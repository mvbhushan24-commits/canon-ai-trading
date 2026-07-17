# Signal Engine — Events

**Engine ID:** `market_signal`  
**Sprint:** 11.1 (Architecture specification)  
**Status:** Not implemented

---

## Event Envelope

All events use the `SignalAnalysisEvent` envelope (consistent with Sprints 1–10):

```python
{
    "event_id": "uuid",
    "timestamp_utc": "ISO-8601",
    "symbol": "GOLD.i#",
    "source_engine": "market_signal",
    "event_type": "SignalCreated",
    "payload": { ... }
}
```

---

## Published Events

### Signal Lifecycle Events (Required)

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `SignalCreated` | Signal object assembled (validation passed) | `signal_id`, `decision_id`, `direction`, `state`, `confidence`, `signal_quality` |
| `SignalActivated` | Signal transitions to `ACTIVE` | Full `TradingSignal` |
| `SignalTriggered` | Entry price reached (`ACTIVE` → `TRIGGERED`) | `signal_id`, `entry_price`, `trigger_price`, `timestamp_utc` |
| `SignalExpired` | `expiry_time` elapsed without trigger/completion | `signal_id`, `original_state`, `expired_at_utc` |
| `SignalCancelled` | Manual or system cancellation | `signal_id`, `reason`, `cancelled_at_utc` |
| `SignalClosed` | Terminal close (SL hit, manual close, full TP completion) | `signal_id`, `final_state`, `close_reason`, `closed_at_utc` |

### Optional Audit Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `SignalRejected` | Validation pipeline rejects signal creation | `decision_id`, `error_codes`, `blocking_reasons` |
| `SignalStateChanged` | Any lifecycle state transition | `signal_id`, `prior_state`, `current_state`, `reason` |

Optional events are published only when configured (`events.publish_rejections: true` or `events.publish_lifecycle_events: true`).

---

## Contract Events (Event Bus Names)

These names provide downstream consumer compatibility and clean separation from Decision Engine events.

| Contract Name | Maps To | Trigger |
|---------------|---------|---------|
| `signal.created` | `SignalCreated` | Signal object assembled |
| `signal.activated` | `SignalActivated` | Signal becomes `ACTIVE` |
| `signal.triggered` | `SignalTriggered` | Entry price reached |
| `signal.expired` | `SignalExpired` | Signal expired |
| `signal.cancelled` | `SignalCancelled` | Signal cancelled |
| `signal.closed` | `SignalClosed` | Signal terminal close |
| `signal.rejected` | `SignalRejected` | Validation rejection (optional) |
| `signal.state_changed` | `SignalStateChanged` | Any state transition (optional) |

### Legacy Compatibility Notes

| Legacy Event | Sprint 11.1 Behavior |
|--------------|---------------------|
| `decision.signal.published` | Remains Decision Engine event; Signal Engine consumes it |
| `signal.activated` | New canonical event for Telegram/Dashboard consumers |
| Dual publishing | During migration, orchestrator may wire both paths; Telegram migrates to `signal.activated` in future sprint |

---

## Event Payload Schemas

### SignalCreated Payload

```json
{
  "signal_id": "s1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "GOLD.i#",
  "timestamp_utc": "2026-07-16T14:30:00+00:00",
  "timeframe": "M15",
  "direction": "BUY",
  "state": "CREATED",
  "entry_price": 2346.00,
  "stop_loss": 2343.50,
  "take_profit_1": 2350.00,
  "take_profit_2": 2353.20,
  "take_profit_3": null,
  "risk_reward": 2.5,
  "confidence": 78,
  "signal_quality": 84,
  "quality_tier": "high",
  "expiry_time": "2026-07-16T15:30:00+00:00"
}
```

### SignalActivated Payload

Full `TradingSignal.model_dump(mode="json")`:

```json
{
  "signal_id": "s1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp_utc": "2026-07-16T14:30:00+00:00",
  "symbol": "GOLD.i#",
  "timeframe": "M15",
  "direction": "BUY",
  "state": "ACTIVE",
  "entry_price": 2346.00,
  "stop_loss": 2343.50,
  "take_profit_1": 2350.00,
  "take_profit_2": 2353.20,
  "take_profit_3": null,
  "risk_reward": 2.5,
  "confidence": 78,
  "signal_quality": 84,
  "quality_tier": "high",
  "reasons": [
    "Bullish structure trend with recent BOS",
    "Sell-side liquidity swept within 30 bars",
    "Active bullish order block in discount territory",
    "Price in discount zone with OTE alignment",
    "London open kill zone active"
  ],
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
  "expiry_time": "2026-07-16T15:30:00+00:00",
  "metadata": {
    "pipeline_version": "0.1.0",
    "config_hash": "def456",
    "duration_ms": 12,
    "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "decision_timestamp_utc": "2026-07-16T14:30:00+00:00",
    "entry_type": "zone",
    "tp_count": 2,
    "duplicate_check_passed": true
  }
}
```

### SignalTriggered Payload

```json
{
  "signal_id": "s1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "GOLD.i#",
  "direction": "BUY",
  "prior_state": "ACTIVE",
  "current_state": "TRIGGERED",
  "entry_price": 2346.00,
  "trigger_price": 2346.10,
  "timestamp_utc": "2026-07-16T14:45:00+00:00"
}
```

### SignalExpired Payload

```json
{
  "signal_id": "s1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "GOLD.i#",
  "direction": "BUY",
  "original_state": "ACTIVE",
  "entry_price": 2346.00,
  "created_at_utc": "2026-07-16T14:30:00+00:00",
  "expired_at_utc": "2026-07-16T15:30:00+00:00",
  "expiry_time": "2026-07-16T15:30:00+00:00",
  "was_triggered": false
}
```

### SignalCancelled Payload

```json
{
  "signal_id": "s1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "GOLD.i#",
  "direction": "BUY",
  "prior_state": "ACTIVE",
  "reason": "Manual cancellation by operator",
  "cancelled_at_utc": "2026-07-16T14:50:00+00:00",
  "cancelled_by": "system"
}
```

### SignalClosed Payload

```json
{
  "signal_id": "s1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "GOLD.i#",
  "direction": "BUY",
  "final_state": "STOP_LOSS",
  "close_reason": "Stop loss hit at 2343.50",
  "entry_price": 2346.00,
  "exit_price": 2343.50,
  "closed_at_utc": "2026-07-16T15:10:00+00:00",
  "duration_minutes": 40,
  "was_triggered": true
}
```

### SignalRejected Payload (Optional)

```json
{
  "decision_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "symbol": "GOLD.i#",
  "timestamp_utc": "2026-07-16T14:30:00+00:00",
  "decision_state": "BUY",
  "error_codes": ["DUPLICATE_SIGNAL"],
  "blocking_reasons": [
    "Active BUY signal exists for GOLD.i# within 60-minute window",
    "Entry price 2346.00 within 5.0 pips of active signal s0x9y8z7-..."
  ],
  "source": "market_signal"
}
```

---

## Consumed Events

| Contract Name | Source Engine | Action |
|---------------|---------------|--------|
| `decision.signal.published` | Decision Engine (`market_decision`) | Primary trigger: `create_signal(decision)` |
| `decision.completed` | Decision Engine | Optional: filter for `BUY`/`SELL` before create |
| `decision.expired` | Decision Engine | Cancel pending signal creation for expired decision |
| `decision.updated` | Decision Engine | Optional: re-evaluate active signal linkage |
| `market.tick.received` | Market Data (`market_data`) | Lifecycle price update only (not analysis) |
| `system.config.updated` | Config service | Reload `market_signal` config |

### Events NOT Consumed

| Event | Reason |
|-------|--------|
| `analysis.*.completed` | Signal Engine never analyzes market |
| `decision.no_trade.published` | No signal created — no action needed |
| `decision.wait.published` | No signal created — no action needed |

### Consumption Boundary

The Signal Engine consumes `decision.signal.published` for signal **creation** and `market.tick.received` for lifecycle **threshold checks** only. Tick consumption performs no technical analysis — only comparison of price against pre-computed signal levels.

---

## Event Flow Diagram

```
Decision Engine                         Signal Engine                         Downstream
───────────────                         ─────────────                         ──────────

decision.signal.published ──────────►  create_signal()
(TradeDecision: BUY/SELL)                      │
                                               ▼
                                        Validation Pipeline
                                               │
                         ┌─────────────────────┼─────────────────────┐
                         ▼                     ▼                     ▼
                  SignalCreated          SignalActivated       SignalRejected
                         │                     │               (optional audit)
                         └──────────┬──────────┘
                                    ▼
                             signal.activated
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             Telegram Engine   Dashboard      Signal Store

market.tick.received ──────────────►  update_lifecycle()
                                               │
                         ┌─────────────────────┼─────────────────────┐
                         ▼                     ▼                     ▼
                  SignalTriggered       SignalExpired          SignalClosed
                         │                     │                     │
                         ▼                     ▼                     ▼
                  signal.triggered      signal.expired         signal.closed

Manual cancel/close API ───────────►  cancel_signal() / close_signal()
                                               │
                                               ▼
                                    SignalCancelled / SignalClosed
```

---

## SignalEventPublisher (Planned)

```python
class SignalEventPublisher:
    def subscribe(self, event_type: str, handler: Callable) -> None: ...
    def publish(self, event: SignalAnalysisEvent) -> None: ...

    def publish_signal_created(self, signal: TradingSignal) -> None: ...
    def publish_signal_activated(self, signal: TradingSignal) -> None: ...
    def publish_signal_triggered(
        self, signal: TradingSignal, trigger_price: Decimal
    ) -> None: ...
    def publish_signal_expired(self, signal: TradingSignal) -> None: ...
    def publish_signal_cancelled(
        self, signal: TradingSignal, reason: str
    ) -> None: ...
    def publish_signal_closed(
        self, signal: TradingSignal, reason: str, exit_price: Decimal | None
    ) -> None: ...
    def publish_signal_rejected(self, rejection: SignalRejection) -> None: ...
```

### Contract Bus Publishing

```python
def publish_signal_activated(self, signal: TradingSignal) -> None:
    self.publish(SignalAnalysisEvent(
        event_type="SignalActivated",
        payload=signal.model_dump(mode="json"),
    ))
    # Contract alias
    self._bus.emit("signal.activated", signal)
    self._bus.emit("signal.created", signal)  # Created fires first; activated is canonical for delivery
```

---

## Subscriber Examples

### Telegram Engine (Future Migration)

```python
event_bus.on("signal.activated", telegram.send_signal_alert)
event_bus.on("signal.triggered", telegram.send_entry_confirmation)
event_bus.on("signal.expired", telegram.send_expiry_notice)
event_bus.on("signal.closed", telegram.send_close_summary)
```

### Dashboard

```python
event_bus.on("signal.created", dashboard.render_signal_card)
event_bus.on("signal.activated", dashboard.highlight_active_signal)
event_bus.on("signal.triggered", dashboard.update_signal_badge)
event_bus.on("signal.closed", dashboard.archive_signal)
event_bus.on("signal.expired", dashboard.mark_signal_expired)
event_bus.on("signal.cancelled", dashboard.mark_signal_cancelled)
```

### Pipeline Orchestrator

```python
event_bus.on("decision.signal.published", signal_engine.handle_decision_published)
event_bus.on("market.tick.received", signal_engine.handle_tick_received)
event_bus.on("system.config.updated", signal_engine.handle_config_updated)
```

---

## Event Ordering Guarantees

| Guarantee | Description |
|-----------|-------------|
| Per symbol FIFO | Events for the same symbol processed in emission order |
| `SignalCreated` before `SignalActivated` | Created always precedes activation |
| No duplicate `signal_id` | Each creation produces unique `signal_id` |
| Expiry idempotent | `SignalExpired` emitted at most once per `signal_id` |
| Close idempotent | `SignalClosed` emitted at most once per terminal signal |
| Trigger after active | `SignalTriggered` only when prior state is `ACTIVE` |

---

## Event Type Mapping Table

| Internal `event_type` | Contract Bus Name | `TradingSignal.state` |
|-----------------------|-------------------|------------------------|
| `SignalCreated` | `signal.created` | `CREATED` |
| `SignalActivated` | `signal.activated` | `ACTIVE` |
| `SignalTriggered` | `signal.triggered` | `TRIGGERED` |
| `SignalExpired` | `signal.expired` | `EXPIRED` |
| `SignalCancelled` | `signal.cancelled` | `CANCELLED` |
| `SignalClosed` | `signal.closed` | `STOP_LOSS`, `CLOSED`, `TP3_HIT` (terminal paths) |
| `SignalRejected` | `signal.rejected` | N/A (no signal created) |

---

## Error Event Payload

When signal creation fails validation:

```json
{
  "decision_id": "d4e5f6a7-b8c9-0123-def0-234567890123",
  "symbol": "GOLD.i#",
  "timestamp_utc": "2026-07-16T14:30:00+00:00",
  "decision_state": "BUY",
  "error_codes": ["LOW_CONFIDENCE"],
  "blocking_reasons": ["Decision confidence 58 below signal minimum 65"],
  "source": "market_signal"
}
```

Contract bus (when enabled): `signal.rejected`

---

## Error Code Reference

| Code | Event Context |
|------|---------------|
| `SIGNAL_VALIDATION_FAILED` | Input/schema/session validation rejection |
| `SIGNAL_EXPIRED` | Decision or signal past validity |
| `LOW_CONFIDENCE` | Confidence or quality below threshold |
| `DUPLICATE_SIGNAL` | Duplicate active signal detected |
| `INVALID_DECISION` | Decision state not eligible or missing fields |
| `INVALID_RISK` | Risk re-validation failed |

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Decision Engine Events | [../market-decision/EVENTS.md](../market-decision/EVENTS.md) |
| Telegram Engine | [../engines/telegram-engine.md](../engines/telegram-engine.md) |
| Event Bus Convention | [../engines/README.md](../engines/README.md) |
