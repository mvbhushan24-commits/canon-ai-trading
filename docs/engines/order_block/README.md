# Order Block Engine — Architecture Specification Index

**Sprint:** 4.1  
**Engine ID:** `order_block`  
**Status:** Architecture specification only — not implemented  
**Architecture Status:** FROZEN (Sprints 1–3 unchanged)

---

## Overview

The Order Block Engine is Sprint 4.1 of the Canon AI Trading platform. It detects institutional order block zones on gold (XAUUSD / GOLD.i#) by consuming outputs from the Market Data, Market Structure, and Market Liquidity engines.

This sprint produces **architecture documentation only**. No production code, tests, or APIs are included.

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Purpose, responsibilities, dependencies, components, acceptance criteria |
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
Order Block (Sprint 4.1 spec → Sprint 4.2 implementation)
        ↓
Future: FVG, Breaker, Decision, Notification
```

---

## Input Sources

| Engine | Output Type |
|--------|-------------|
| Market Data Engine | `NormalizedCandle` |
| Market Structure Engine | `MarketStructure` |
| Market Liquidity Engine | `LiquidityAnalysis` |

---

## Output Types

| Output | Description |
|--------|-------------|
| Bullish Order Block | Demand zone below displacement |
| Bearish Order Block | Supply zone above displacement |
| Fresh Order Block | Untested — price has not returned |
| Mitigated Order Block | Price re-entered zone |
| Invalidated Order Block | Zone broken |

---

## Out of Scope

- Breaker blocks
- Mitigation blocks (as separate entity)
- Fair value gaps
- Trade signals
- Risk engine
- Telegram / dashboard
- AI inference
- Modifications to Sprints 1, 2, or 3

---

## Related Platform Documents

| Document | Path |
|----------|------|
| System Architecture | [../../SYSTEM_ARCHITECTURE.md](../../SYSTEM_ARCHITECTURE.md) |
| Constitution | [../../CONSTITUTION.md](../../CONSTITUTION.md) |
| Smart Money Contract (broader) | [../smart-money-engine.md](../smart-money-engine.md) |
| Market Structure (implemented) | [../../market-structure/ARCHITECTURE.md](../../market-structure/ARCHITECTURE.md) |
| Market Liquidity (implemented) | [../../market-liquidity/ARCHITECTURE.md](../../market-liquidity/ARCHITECTURE.md) |

---

## Implementation Sprint

Sprint 4.2 (planned) will implement this specification in `backend/engines/market_order_block/` following the module pattern established in Sprints 1–3.
