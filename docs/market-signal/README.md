# Signal Engine — Architecture Specification Index

**Sprint:** 11.1  
**Engine ID:** `market_signal`  
**Status:** Architecture specification only — not implemented  
**Architecture Status:** FROZEN (Sprints 1–10 unchanged)

---

## Overview

The Signal Engine is Sprint 11.1 of the Canon AI Trading platform. It is the **authoritative institutional trading signal layer** for gold (XAUUSD / GOLD.i#). It consumes **only** validated outputs from the Decision Engine and converts qualified trade decisions into explainable, lifecycle-managed **trading signals**.

The Signal Engine **never analyzes the market**. It does not import upstream analysis engines, re-run detection logic, or derive new directional bias. Its sole responsibility is to validate, normalize, score, and publish institutional signals from decisions that are already `BUY` or `SELL`.

Per the Constitution:

- **NO TRADE is success** — `NO_TRADE` and `WAIT` decisions produce no signal; rejection is a successful outcome.
- **Clean I/O** — explicit typed inputs (`TradeDecision`) and outputs (`TradingSignal`).
- **External configuration** — all thresholds, weights, and lifecycle rules in YAML.

This sprint produces **architecture documentation only**. No production code, algorithms, tests, or APIs are included.

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Purpose, responsibilities, components, signal pipeline, schemas, lifecycle, quality model |
| [DATA_PIPELINE.md](./DATA_PIPELINE.md) | Decision-to-signal conversion flow and lifecycle update path |
| [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) | Planned public API, schemas, exceptions, downstream integration |
| [CONFIGURATION.md](./CONFIGURATION.md) | YAML settings, validation rules, quality weights, lifecycle |
| [EVENTS.md](./EVENTS.md) | Published and consumed events |

---

## Position in Pipeline

```
Market Data (Sprint 1)
        ↓
Market Structure (Sprint 2)
        ↓
Market Liquidity (Sprint 3)
        ↓
Order Block (Sprint 4)
        ↓
Fair Value Gap (Sprint 5)
        ↓
Breaker Block (Sprint 6)
        ↓
Mitigation Block (Sprint 7)
        ↓
Premium / Discount (Sprint 8)
        ↓
Kill Zones & Sessions (Sprint 9)
        ↓
Decision Engine (Sprint 10)
        ↓
Signal Engine (Sprint 11.1 spec → Sprint 11.2 implementation)
        ↓
Telegram Engine / Dashboard (future)
```

---

## Input Source

| Engine | Engine ID | Input Type | Required |
|--------|-----------|------------|----------|
| Decision Engine | `market_decision` | `TradeDecision` | **Yes** |

### Decision States Consumed

| Decision State | Signal Engine Behavior |
|----------------|------------------------|
| `BUY` | Eligible for signal creation after validation |
| `SELL` | Eligible for signal creation after validation |
| `NO_TRADE` | No signal emitted — successful rejection |
| `WAIT` | No signal emitted — await next decision |
| `NO_DATA` | No signal emitted — upstream incomplete |
| `INVALID` | No signal emitted — validation failure logged |

### Input Contract Note

The Signal Engine consumes **only** the `TradeDecision` public type from `backend.engines.market_decision`. It does **not** import sibling engine internals, access raw candles, or call upstream analysis APIs. The orchestrator or event bus supplies completed decision envelopes via `DecisionPublished` or direct `decide()` output.

---

## Signal Output Summary

| Field | Description |
|-------|-------------|
| `signal_id` | Unique signal identifier |
| `timestamp_utc` | Signal creation timestamp (UTC) |
| `symbol` | Instrument identifier |
| `timeframe` | Primary analysis timeframe |
| `direction` | `BUY` or `SELL` |
| `entry_price` | Resolved entry price |
| `stop_loss` | Protective stop level |
| `take_profit_1` | Primary profit target |
| `take_profit_2` | Secondary profit target (optional) |
| `take_profit_3` | Tertiary profit target (optional) |
| `risk_reward` | Primary target risk-reward ratio |
| `confidence` | 0–100 from source decision |
| `signal_quality` | 0–100 composite signal quality score |
| `reasons` | Human-readable signal rationale |
| `evidence_summary` | Copied from decision evidence summary |
| `risk_summary` | Copied from decision risk summary |
| `warnings` | Non-blocking concerns |
| `expiry_time` | Signal validity deadline (UTC) |

---

## Signal States

| State | Description |
|-------|-------------|
| `CREATED` | Signal object assembled; not yet active |
| `ACTIVE` | Signal published and monitorable |
| `TRIGGERED` | Entry price reached |
| `PARTIALLY_FILLED` | Partial entry fill recorded |
| `TP1_HIT` | Take profit 1 reached |
| `TP2_HIT` | Take profit 2 reached |
| `TP3_HIT` | Take profit 3 reached |
| `BREAK_EVEN` | Stop moved to break-even |
| `TRAILING` | Trailing stop active |
| `STOP_LOSS` | Stop loss hit — terminal |
| `CLOSED` | Signal fully closed — terminal |
| `EXPIRED` | Expiry reached without completion — terminal |
| `CANCELLED` | Manually or system cancelled — terminal |

---

## Signal Validation

| Validator | Purpose |
|-----------|---------|
| Duplicate Detection | Prevent redundant signals for same symbol/direction/zone |
| Confidence Threshold | Enforce minimum confidence from decision |
| Session Validation | Confirm decision session context still valid at signal time |
| Risk Validation | Re-validate R:R, stop size, and spread from decision |
| Decision Validation | Schema, state, and field completeness checks |
| Expiry Validation | Reject or expire stale decisions |

---

## Out of Scope

- Market analysis or evidence synthesis
- Upstream engine consumption (Sprints 1–9)
- Decision logic modification
- Order execution or position management
- Modifications to Sprints 1–10
- Sprint 11.2 implementation
- Tests and verification

---

## Relationship to Legacy Contracts

The legacy Telegram Engine contract ([../engines/telegram-engine.md](../engines/telegram-engine.md)) currently consumes `decision.signal.published` directly. Sprint 11.1 introduces **`market_signal`** as the canonical signal layer between Decision Engine and downstream consumers. Telegram Engine integration will migrate to `signal.activated` / `SignalActivated` in a future sprint while preserving backward-compatible bus aliases where practical.

---

## Related Platform Documents

| Document | Path |
|----------|------|
| System Architecture | [../SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) |
| Constitution | [../CONSTITUTION.md](../CONSTITUTION.md) |
| Decision Engine | [../market-decision/ARCHITECTURE.md](../market-decision/ARCHITECTURE.md) |
| Telegram Engine (consumer) | [../engines/telegram-engine.md](../engines/telegram-engine.md) |
| Legacy Decision Contract | [../engines/decision-engine.md](../engines/decision-engine.md) |

---

## Implementation Sprint

Sprint 11.2 (planned) will implement this specification in `backend/engines/market_signal/` following the module pattern established in Sprints 1–10. See [ARCHITECTURE.md § Sprint 11.2 Implementation Plan](./ARCHITECTURE.md#sprint-112-implementation-plan).
