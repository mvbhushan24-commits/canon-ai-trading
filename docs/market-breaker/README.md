# Breaker Block Engine — Architecture Specification Index

**Sprint:** 6.1  
**Engine ID:** `market_breaker`  
**Status:** Architecture specification only — not implemented  
**Architecture Status:** FROZEN (Sprints 1–5 unchanged)

---

## Overview

The Breaker Block Engine is Sprint 6.1 of the Canon AI Trading platform. It detects institutional breaker block zones on gold (XAUUSD / GOLD.i#) by consuming outputs from the Market Data, Market Structure, Market Liquidity, Order Block, and Fair Value Gap engines.

A breaker block is a **polarity-flipped institutional zone** formed when a previously valid order block (or, optionally, fair value gap) is invalidated and price later returns to that zone — converting failed support into resistance or failed resistance into support.

This sprint produces **architecture documentation only**. No production code, algorithms, tests, or APIs are included.

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Purpose, responsibilities, dependencies, components, canonical schemas, acceptance criteria |
| [DATA_PIPELINE.md](./DATA_PIPELINE.md) | Data flow from upstream engines through detection to output |
| [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) | Planned public API, schemas, exceptions |
| [CONFIGURATION.md](./CONFIGURATION.md) | YAML settings and parameter reference |
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
Breaker Block (Sprint 6.1 spec → Sprint 6.2 implementation)
        ↓
Future: Decision, Notification, Dashboard
```

---

## Input Sources

| Engine | Output Type | Required |
|--------|-------------|----------|
| Market Data Engine | `NormalizedCandle` | **Yes** |
| Market Structure Engine | `MarketStructure` | **Recommended** |
| Market Liquidity Engine | `LiquidityState` | **Optional** |
| Order Block Engine | `list[OrderBlock]` (invalidated blocks) | **Yes** |
| Fair Value Gap Engine | `FairValueGapState` | **Optional** |

### Input Contract Note

Per Sprint 6.1 specification, the Breaker Block Engine consumes **only** the five type categories above from upstream public APIs. It does **not** import full analysis envelopes (`OrderBlockAnalysis`, `FairValueGapAnalysis`, `LiquidityAnalysis`) or downstream engine types. Callers extract invalidated order blocks from `OrderBlockAnalysis.invalidated_blocks` and `FairValueGapState` from `FairValueGapAnalysis.state` when wiring the pipeline.

---

## Output Types

| Output | Description |
|--------|-------------|
| Bullish Breaker Block | Former bearish supply zone invalidated — now acts as demand support |
| Bearish Breaker Block | Former bullish demand zone invalidated — now acts as supply resistance |
| Candidate Breaker | Invalidated source zone identified; awaiting retest confirmation |
| Confirmed Breaker | Price returned to zone after invalidation — polarity flip validated |
| Mitigated Breaker | Price traded through breaker zone per configuration |
| Invalidated Breaker | Breaker failed — zone broken in opposing direction |
| Expired Breaker | Breaker aged beyond configured bar limit without resolution |
| Liquidity Confluence | Breaker overlaps swept liquidity or active zone |
| FVG Confluence | Breaker overlaps open/partial fair value gap |

---

## Out of Scope

- Order block detection (consumed, not produced)
- Fair value gap detection (consumed, not produced)
- Mitigation blocks (as separate entity)
- Trade signals / entries / exits
- Risk sizing
- Telegram / dashboard
- AI inference
- Modifications to Sprints 1, 2, 3, 4, or 5

---

## Related Platform Documents

| Document | Path |
|----------|------|
| System Architecture | [../SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) |
| Constitution | [../CONSTITUTION.md](../CONSTITUTION.md) |
| Market Data (implemented) | [../market-data/ARCHITECTURE.md](../market-data/ARCHITECTURE.md) |
| Market Structure (implemented) | [../market-structure/ARCHITECTURE.md](../market-structure/ARCHITECTURE.md) |
| Market Liquidity (implemented) | [../market-liquidity/ARCHITECTURE.md](../market-liquidity/ARCHITECTURE.md) |
| Order Block (implemented) | [../engines/order_block/ARCHITECTURE.md](../engines/order_block/ARCHITECTURE.md) |
| Fair Value Gap (implemented) | [../market-fvg/ARCHITECTURE.md](../market-fvg/ARCHITECTURE.md) |
| Smart Money Contract (broader) | [../engines/smart-money-engine.md](../engines/smart-money-engine.md) |

---

## Implementation Sprint

Sprint 6.2 (planned) will implement this specification in `backend/engines/market_breaker/` following the module pattern established in Sprints 1–5.
