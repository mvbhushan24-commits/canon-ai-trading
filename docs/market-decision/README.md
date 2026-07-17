# Decision Engine — Architecture Specification Index

**Sprint:** 10.1  
**Engine ID:** `market_decision`  
**Status:** Architecture specification only — not implemented  
**Architecture Status:** FROZEN (Sprints 1–9 unchanged)

---

## Overview

The Decision Engine is Sprint 10.1 of the Canon AI Trading platform. It is the **authoritative institutional trade decision layer** for gold (XAUUSD / GOLD.i#). It consumes completed evidence from every upstream analysis engine and produces **one** explainable trade decision: `BUY`, `SELL`, or `NO_TRADE`.

Per the Constitution: **NO TRADE is success**. The engine must never force trades. When evidence is insufficient, conflicting, or fails risk validation, `NO_TRADE` is the correct outcome.

This sprint produces **architecture documentation only**. No production code, algorithms, tests, or APIs are included.

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Purpose, responsibilities, dependencies, components, decision pipeline, schemas, acceptance criteria |
| [DATA_PIPELINE.md](./DATA_PIPELINE.md) | Evidence collection flow from upstream engines through decision generation |
| [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) | Planned public API, schemas, exceptions, downstream integration |
| [CONFIGURATION.md](./CONFIGURATION.md) | YAML settings, evidence weights, risk rules, quality model |
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
Decision Engine (Sprint 10.1 spec → Sprint 10.2 implementation)
        ↓
Telegram Engine / Dashboard (future)
```

---

## Evidence Sources

| Engine | Engine ID | Output Type | Required |
|--------|-----------|-------------|----------|
| Market Structure | `market_structure` | `MarketStructure` | **Recommended** |
| Market Liquidity | `market_liquidity` | `LiquidityAnalysis` | **Recommended** |
| Order Block | `order_block` | `OrderBlockAnalysis` | **Recommended** |
| Fair Value Gap | `fair_value_gap` | `FairValueGapAnalysis` | **Recommended** |
| Breaker Block | `market_breaker` | `BreakerBlockAnalysis` | **Recommended** |
| Mitigation Block | `market_mitigation` | `MitigationBlockAnalysis` | **Recommended** |
| Premium / Discount | `market_premium_discount` | `PremiumDiscountAnalysis` | **Recommended** |
| Market Sessions | `market_sessions` | `SessionAnalysis` | **Recommended** |
| Market Data | `market_data` | `current_price`, `spread` | **Yes** |

### Input Contract Note

Per Sprint 10.1 specification, the Decision Engine consumes **only** the typed outputs above from upstream public APIs. It does **not** import sibling engine internals, re-run detection logic, or access raw candles directly. The orchestrator or event bus supplies completed analysis envelopes.

---

## Decision States

| State | Description |
|-------|-------------|
| `NO_DATA` | Required inputs (price) unavailable; decision cycle cannot start |
| `WAIT` | Evidence partially available; awaiting upstream completion or freshness |
| `BUY` | Qualified long signal with entry, stop loss, take profit |
| `SELL` | Qualified short signal with entry, stop loss, take profit |
| `NO_TRADE` | Evidence insufficient, conflicting, or risk-blocked — **successful outcome** |
| `INVALID` | Input validation or configuration failure; no trade decision emitted |

---

## Decision Output Summary

| Field | Description |
|-------|-------------|
| `direction` | `BUY`, `SELL`, or `NONE` |
| `entry` | Suggested entry price or zone |
| `stop_loss` | Protective stop level |
| `take_profit` | One or more profit targets |
| `confidence` | 0–100 composite confidence score |
| `reasons` | Human-readable decision rationale |
| `evidence_summary` | Per-engine weighted contribution summary |
| `risk_summary` | R:R, spread, stop size, session, and rule outcomes |
| `warnings` | Non-blocking concerns |
| `decision_id` | Unique decision identifier |
| `timestamp_utc` | Decision timestamp (UTC) |

---

## Out of Scope

- Order execution or position management
- Re-running upstream detection algorithms
- Modifications to Sprints 1–9
- Telegram delivery (Telegram Engine)
- Dashboard rendering
- AI inference
- Sprint 10.2 implementation
- Tests and verification

---

## Relationship to Legacy Decision Engine Contract

An earlier platform contract exists at [../engines/decision-engine.md](../engines/decision-engine.md) with engine ID `decision`. Sprint 10.1 **`market_decision`** supersedes that contract for implementation purposes while preserving compatible bus names where practical (`decision.*` contract events map to internal `Decision*` event types).

The legacy contract references Smart Money, Trend, News & Macro, and Risk engines not yet implemented in Sprints 1–9. Sprint 10.1 scopes evidence consumption to the **nine implemented upstream engines** plus Market Data price context. Future engines may be integrated via configuration without architectural redesign.

---

## Related Platform Documents

| Document | Path |
|----------|------|
| System Architecture | [../SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) |
| Constitution | [../CONSTITUTION.md](../CONSTITUTION.md) |
| Market Structure | [../market-structure/ARCHITECTURE.md](../market-structure/ARCHITECTURE.md) |
| Market Liquidity | [../market-liquidity/ARCHITECTURE.md](../market-liquidity/ARCHITECTURE.md) |
| Order Block | [../engines/order_block/ARCHITECTURE.md](../engines/order_block/ARCHITECTURE.md) |
| Fair Value Gap | [../market-fvg/ARCHITECTURE.md](../market-fvg/ARCHITECTURE.md) |
| Breaker Block | [../market-breaker/ARCHITECTURE.md](../market-breaker/ARCHITECTURE.md) |
| Mitigation Block | [../market-mitigation/ARCHITECTURE.md](../market-mitigation/ARCHITECTURE.md) |
| Premium / Discount | [../market-premium-discount/ARCHITECTURE.md](../market-premium-discount/ARCHITECTURE.md) |
| Market Sessions | [../market-sessions/ARCHITECTURE.md](../market-sessions/ARCHITECTURE.md) |
| Legacy Decision Engine (contract) | [../engines/decision-engine.md](../engines/decision-engine.md) |
| Telegram Engine (consumer) | [../engines/telegram-engine.md](../engines/telegram-engine.md) |

---

## Implementation Sprint

Sprint 10.2 (planned) will implement this specification in `backend/engines/market_decision/` following the module pattern established in Sprints 1–9. See [ARCHITECTURE.md § Sprint 10.2 Implementation Plan](./ARCHITECTURE.md#sprint-102-implementation-plan).
