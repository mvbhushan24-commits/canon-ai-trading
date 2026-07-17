# Signal Engine — Data Pipeline

**Engine ID:** `market_signal`  
**Sprint:** 11.1 (Architecture specification)  
**Status:** Not implemented

---

## Pipeline Overview

```
Decision Engine (TradeDecision)
        │
        ▼
Signal Input Validator
        │
        ▼
Decision Validator ──(NO_TRADE/WAIT/NO_DATA)──► No Signal (success)
        │
        ▼
Expiry Validator
        │
        ▼
Confidence Validator
        │
        ▼
Session Validator (decision-derived)
        │
        ▼
Risk Validator (decision-derived)
        │
        ▼
Duplicate Detector
        │
        ▼
Entry Normalizer
        │
        ▼
Take Profit Mapper
        │
        ▼
Signal Quality Scorer
        │
        ▼
Signal Assembler
        │
        ▼
Signal Activator
        │
        ▼
TradingSignal (state: CREATED or ACTIVE)
        │
        ▼
Signal Event Publisher
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
Telegram Engine      Dashboard          Signal Store (SQLite)
(future)             (future)           (Sprint 11.2)

Lifecycle Path (operational — not analysis):
        │
        ▼
Price Update (orchestrator-supplied)
        │
        ▼
Signal Lifecycle Manager
        │
        ├── Entry check ──► TRIGGERED
        ├── TP checks ──► TP1_HIT / TP2_HIT / TP3_HIT
        ├── SL check ──► STOP_LOSS ──► CLOSED
        ├── Expiry sweep ──► EXPIRED
        └── Cancel/Close ──► CANCELLED / CLOSED
```

---

## Stage 1 — Decision Engine Input

**Source:** `DecisionPublished` event or direct `TradeDecision` from orchestrator

**Type:** `TradeDecision` (from `backend.engines.market_decision`)

| Field | Required for Signal | Purpose |
|-------|---------------------|---------|
| `decision_id` | **Yes** | Provenance and duplicate detection |
| `symbol` | **Yes** | Instrument identification |
| `timestamp_utc` | **Yes** | Signal timestamp reference |
| `state` | **Yes** | Must be `BUY` or `SELL` for signal creation |
| `direction` | **Yes** | Must align with `state` |
| `entry` | **Yes** | Entry normalization source |
| `stop_loss` | **Yes** | Signal stop level |
| `take_profit` | **Yes** (≥ 1) | TP1/TP2/TP3 mapping |
| `risk_reward_ratio` | **Yes** | Signal R:R display and validation |
| `confidence` | **Yes** | Confidence gate and signal field |
| `quality_score` | Recommended | Signal quality dimension |
| `quality_tier` | Recommended | Signal quality tier |
| `reasons` | **Yes** | Explainability |
| `evidence_summary` | **Yes** (when configured) | Explainability |
| `risk_summary` | **Yes** | Session and risk re-validation |
| `warnings` | No | Copied to signal |
| `valid_until_utc` | **Yes** | Expiry validation and `expiry_time` |
| `metadata` | Recommended | Timeframe, pipeline version |

**Boundary rule:** Signal Engine reads decisions from caller or event payload. It does **not** call `MarketDecisionEngine.decide()` directly in the hot path.

**Failure:** Missing or invalid envelope → rejection with `SIGNAL_VALIDATION_FAILED`.

---

## Stage 2 — Decision State Routing

| `TradeDecision.state` | Pipeline Action | Output |
|-----------------------|-----------------|--------|
| `BUY` | Continue validation pipeline | `TradingSignal` (on pass) |
| `SELL` | Continue validation pipeline | `TradingSignal` (on pass) |
| `NO_TRADE` | Stop; no signal | None (success) |
| `WAIT` | Stop; no signal | None (success) |
| `NO_DATA` | Stop; no signal | None (success) |
| `INVALID` | Stop; rejection logged | `SignalRejection` with `INVALID_DECISION` |

**Constitution alignment:** Emitting no signal for `NO_TRADE` and `WAIT` is the correct outcome.

---

## Stage 3 — Expiry Validation

**Source:** `TradeDecision.valid_until_utc`, `TradeDecision.timestamp_utc`

| Check | Default | Failure |
|-------|---------|---------|
| `now_utc <= valid_until_utc` | — | `SIGNAL_EXPIRED` |
| Decision age ≤ `max_decision_age_seconds` | 300 | `SIGNAL_EXPIRED` |

No market data consulted. Validation uses decision timestamps only.

---

## Stage 4 — Confidence Validation

**Source:** `TradeDecision.confidence`, `TradeDecision.quality_score`

| Check | Default Threshold | Failure |
|-------|-------------------|---------|
| `confidence >= min_confidence` | 65 | `LOW_CONFIDENCE` |
| `quality_score >= min_decision_quality` (optional) | 60 | `LOW_CONFIDENCE` |

Confidence values are copied verbatim to the signal; no re-scoring of evidence.

---

## Stage 5 — Session Validation

**Source:** `TradeDecision.risk_summary` (decision-derived)

| Field Used | Validation |
|------------|------------|
| `session_allowed` | Must be `true` when session gate enabled |
| `rule_outcomes` | Session rule must show pass |
| Decision `warnings` | Session-related warnings may reduce quality (not auto-reject unless configured) |

**No calls to Market Sessions Engine.** Session context was resolved by the Decision Engine; Signal Engine trusts and re-checks the decision's recorded outcome.

---

## Stage 6 — Risk Validation

**Source:** `TradeDecision.risk_summary`, `TradeDecision.risk_reward_ratio`

| Field Used | Validation |
|------------|------------|
| `min_rr_met` | Must be `true` |
| `max_rr_met` | Must be `true` when max R:R configured |
| `spread_acceptable` | Must be `true` |
| `stop_size_acceptable` | Must be `true` |
| `confidence_acceptable` | Must be `true` |
| `risk_reward_ratio` | Within `[min_risk_reward, max_risk_reward]` |

**No new risk computation.** Signal Engine verifies the decision's risk summary still satisfies configured signal-level thresholds.

---

## Stage 7 — Duplicate Detection

**Source:** Active signal registry + incoming decision

| Criterion | Default | Failure |
|-----------|---------|---------|
| Same `symbol` + same `direction` | — | Compare against active signals |
| Within `duplicate_window_minutes` | 60 | `DUPLICATE_SIGNAL` |
| Entry within `duplicate_entry_tolerance_pips` | 5.0 | `DUPLICATE_SIGNAL` |
| Same `decision_id` already converted | — | `DUPLICATE_SIGNAL` |

Duplicate detection uses stored signal metadata only — no price or market analysis.

---

## Stage 8 — Entry Normalization

**Source:** `TradeDecision.entry` (`EntrySpec`)

| Input | Output |
|-------|--------|
| `entry_type=point`, `price=2345.50` | `entry_price=2345.50` |
| `entry_type=zone`, `zone_low=2345.80`, `zone_high=2346.20` | `entry_price=2346.00` (midpoint default) |
| `entry_type=ote`, zone bounds | `entry_price=OTE midpoint` |

Direction-specific edge preference configurable — see [CONFIGURATION.md](./CONFIGURATION.md).

---

## Stage 9 — Take Profit Mapping

**Source:** `TradeDecision.take_profit` (ordered list)

```
take_profit[0]  →  take_profit_1  (required)
take_profit[1]  →  take_profit_2  (optional)
take_profit[2]  →  take_profit_3  (optional)
```

| Decision TP Count | Signal Fields |
|-------------------|---------------|
| 1 | TP1 only |
| 2 | TP1, TP2 |
| 3+ | TP1, TP2, TP3 (additional targets ignored or logged in warnings) |

---

## Stage 10 — Signal Quality Scoring

**Source:** Decision fields only

| Dimension | Input Fields |
|-----------|--------------|
| Decision confidence | `confidence` |
| Decision quality | `quality_score` |
| Risk clarity | `risk_summary.rule_outcomes` |
| Entry precision | `entry.entry_type` |
| Target structure | `len(take_profit)` |
| Evidence completeness | `evidence_summary` availability count |
| Explainability | `len(reasons)` |

See [ARCHITECTURE.md § Quality Scoring](./ARCHITECTURE.md#quality-scoring).

---

## Stage 11 — Signal Assembly & Activation

Assembled `TradingSignal` fields populated per [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md).

| Step | Action |
|------|--------|
| Assign `signal_id` | UUID v4 |
| Set `timestamp_utc` | Signal creation time (UTC) |
| Set `timeframe` | From config default or decision metadata |
| Copy explainability | `reasons`, `evidence_summary`, `risk_summary`, `warnings` |
| Set `expiry_time` | `valid_until_utc` or `now + signal_validity_minutes` |
| Set `state` | `CREATED` then `ACTIVE` if auto-activate |
| Persist | Signal store when enabled |

---

## Stage 12 — Event Publishing

| Outcome | Events |
|---------|--------|
| Signal created | `SignalCreated` |
| Signal activated | `SignalActivated` |
| Validation failed | `SignalRejected` (optional audit) |

Contract bus names — see [EVENTS.md](./EVENTS.md).

---

## Lifecycle Pipeline

Lifecycle processing is **operational state tracking**, not market analysis. Price is compared against levels already derived from the decision.

### Trigger: Price Update

**Source:** Orchestrator calls `update_lifecycle(symbol, current_price, timestamp_utc)` or `handle_tick_received(event)`

| Check | Condition | New State | Event |
|-------|-----------|-----------|-------|
| Entry | `ACTIVE` + price crosses `entry_price` | `TRIGGERED` | `SignalTriggered` |
| TP1 | `TRIGGERED`/`PARTIALLY_FILLED` + price reaches TP1 | `TP1_HIT` | — |
| TP2 | After TP1 + price reaches TP2 | `TP2_HIT` | — |
| TP3 | After TP2 + price reaches TP3 | `TP3_HIT` | — |
| Stop loss | Open signal + price hits SL | `STOP_LOSS` → `CLOSED` | `SignalClosed` |
| Break-even | Config rule after TP1 | `BREAK_EVEN` | — |
| Trailing | Config enabled after TP1 | `TRAILING` | — |

### Trigger: Time Expiry

**Source:** `expire_signals(now_utc)` scheduled task

| Condition | New State | Event |
|-----------|-----------|-------|
| `ACTIVE` + untriggered + `now >= expiry_time` | `EXPIRED` | `SignalExpired` |

### Trigger: Manual / System

| Action | New State | Event |
|--------|-----------|-------|
| `cancel_signal(id, reason)` | `CANCELLED` | `SignalCancelled` |
| `close_signal(id, reason)` | `CLOSED` | `SignalClosed` |

---

## Data Flow Diagram

```
                    Decision Engine
                          │
              decision.signal.published
              (TradeDecision: BUY/SELL)
                          │
                          ▼
              ┌───────────────────────┐
              │   MarketSignalEngine   │
              │   create_signal()      │
              └───────────┬───────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
   Validation        Normalization      Quality Score
   (6 gates)         (entry + TP)       (weighted)
         │                │                │
         └────────────────┼────────────────┘
                          ▼
                   TradingSignal
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       SignalCreated            SignalActivated
              │                       │
              └───────────┬───────────┘
                          ▼
                   Active Signal Registry
                          │
              (orchestrator price updates)
                          ▼
              Signal Lifecycle Manager
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
  SignalTriggered   SignalExpired    SignalClosed
  SignalCancelled
```

---

## Orchestrator Integration (Recommended)

```python
# After Decision Engine publishes BUY/SELL:
signal_result = signal_engine.create_signal(decision)

if signal_result.accepted:
    signal = signal_result.signal
    # signal.state == ACTIVE (when auto_activate)
else:
    # NO_TRADE/WAIT: no call needed
    # Rejection: log signal_result.rejection
    pass

# Periodic lifecycle sweep:
signal_engine.expire_signals(datetime.now(UTC))

# On tick (operational only):
signal_engine.update_lifecycle(
    symbol=tick.symbol,
    current_price=tick.mid,
    timestamp_utc=tick.timestamp_utc,
)
```

---

## Input Boundary Summary

| Allowed | Prohibited |
|---------|------------|
| `TradeDecision` from Decision Engine public API | Raw candles |
| Orchestrator-supplied `current_price` for lifecycle | Direct Market Data Engine imports |
| Configuration from YAML | Upstream analysis engine imports |
| Active signal registry (internal) | Re-running decision pipeline |
| SQLite signal store | Technical analysis computations |

---

## Failure Modes

| Condition | Pipeline Behavior | Downstream Impact |
|-----------|-------------------|-------------------|
| Decision is `NO_TRADE` | No signal; no event (or optional audit) | Telegram silent — correct |
| Decision is `WAIT` | No signal | Await next decision cycle |
| Decision expired | Rejection `SIGNAL_EXPIRED` | No alert |
| Duplicate active signal | Rejection `DUPLICATE_SIGNAL` | No duplicate alert |
| Low confidence | Rejection `LOW_CONFIDENCE` | No alert |
| Invalid risk summary | Rejection `INVALID_RISK` | No alert |
| Missing entry/SL/TP | Rejection `INVALID_DECISION` | No alert |

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |
| Decision Engine Pipeline | [../market-decision/DATA_PIPELINE.md](../market-decision/DATA_PIPELINE.md) |
