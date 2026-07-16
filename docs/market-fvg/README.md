# Fair Value Gap Engine — Architecture Specification Index

**Sprint:** 5.1  
**Engine ID:** `fair_value_gap`  
**Status:** Architecture specification only — not implemented  
**Architecture Status:** FROZEN (Sprints 1–4 unchanged)

---

## Overview

The Fair Value Gap (FVG) Engine is Sprint 5.1 of the Canon AI Trading platform. It detects institutional fair value gap imbalances on gold (XAUUSD / GOLD.i#) by consuming outputs from the Market Data, Market Structure, Market Liquidity, and Order Block engines.

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
Fair Value Gap (Sprint 5.1 spec → Sprint 5.2 implementation)
        ↓
Future: Breaker, Decision, Notification
```

---

## Input Sources

| Engine | Output Type | Required |
|--------|-------------|----------|
| Market Data Engine | `NormalizedCandle` | **Yes** |
| Market Structure Engine | `MarketStructure` | **Recommended** |
| Market Liquidity Engine | `LiquidityState` | **Optional** |
| Order Block Engine | `OrderBlockState` | **Optional** |

### Input Contract Note

Per Sprint 5.1 specification, the FVG Engine consumes **only** the four types above. It does **not** import `LiquidityAnalysis`, `OrderBlockAnalysis`, or any other upstream analysis envelope. Callers extract `LiquidityState` and `OrderBlockState` from their respective analysis outputs when wiring the pipeline.

---

## Output Types

| Output | Description |
|--------|-------------|
| Bullish Fair Value Gap | Imbalance below displacement — price expected to revisit from above |
| Bearish Fair Value Gap | Imbalance above displacement — price expected to revisit from below |
| Open Gap | Untested — price has not entered the gap zone |
| Partial Fill | Price entered gap but did not fully traverse or close beyond CE |
| Full Fill | Gap fully traversed per configuration rules |
| Mitigated Gap | Gap imbalance addressed — CE touched or fill threshold met |
| Invalidated Gap | Gap broken in opposing direction |
| Expired Gap | Gap aged beyond configured bar limit |
| Consequent Encroachment (CE) | 50% midpoint of gap — institutional reaction level |
| Nested FVG | Child gap contained within parent gap boundaries |
| MTF-Aligned FVG | Gap confirmed across multiple configured timeframes |

---

## Out of Scope

- Breaker blocks
- Mitigation blocks (as separate entity)
- Trade signals / entries / exits
- Risk sizing
- Telegram / dashboard
- AI inference
- Modifications to Sprints 1, 2, 3, or 4

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
| Smart Money Contract (broader) | [../engines/smart-money-engine.md](../engines/smart-money-engine.md) |

---

## Implementation Sprint

Sprint 5.2 (planned) will implement this specification in `backend/engines/market_fvg/` following the module pattern established in Sprints 1–4.
