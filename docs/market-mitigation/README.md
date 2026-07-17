# Mitigation Block Engine — Architecture Specification Index

**Sprint:** 7.1  
**Engine ID:** `market_mitigation`  
**Status:** Architecture specification only — not implemented  
**Architecture Status:** FROZEN (Sprints 1–6 unchanged)

---

## Overview

The Mitigation Block Engine is Sprint 7.1 of the Canon AI Trading platform. It detects institutional mitigation block zones on gold (XAUUSD / GOLD.i#) by consuming outputs from the Market Data, Market Structure, Market Liquidity, Order Block, Fair Value Gap, and Breaker Block engines.

A mitigation block is an **institutional zone formed by the last opposing candle before a displacement leg**, representing unfilled orders that price may return to address. The engine tracks formation, confirmation, partial and full mitigation, multi-touch interaction, nested relationships, internal/external structure placement, and higher-timeframe alignment — without emitting trade signals.

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
Breaker Block (Sprint 6)
        ↓
Mitigation Block (Sprint 7.1 spec → Sprint 7.2 implementation)
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
| Order Block Engine | `list[OrderBlock]` (fresh + mitigated) | **Recommended** |
| Fair Value Gap Engine | `FairValueGapState` | **Optional** |
| Breaker Block Engine | `list[BreakerBlock]` (confirmed + candidate) | **Optional** |

### Input Contract Note

Per Sprint 7.1 specification, the Mitigation Block Engine consumes **only** the six type categories above from upstream public APIs. It does **not** import full analysis envelopes (`OrderBlockAnalysis`, `FairValueGapAnalysis`, `LiquidityAnalysis`, `BreakerBlockAnalysis`) or downstream engine types. Callers extract partitioned lists and state objects when wiring the pipeline.

---

## Output Types

| Output | Description |
|--------|-------------|
| Bullish Mitigation Block | Last bearish candle zone before bullish displacement — demand mitigation target |
| Bearish Mitigation Block | Last bullish candle zone before bearish displacement — supply mitigation target |
| Fresh Mitigation Block | Newly formed zone with no price interaction |
| Partial Mitigation | Price entered zone but did not fully traverse per configuration |
| Full Mitigation | Zone fully addressed per mitigation rules |
| Multi-Touch Mitigation | Multiple distinct price interactions with the same zone |
| Nested Mitigation Block | Mitigation block contained within or overlapping another zone |
| Internal Mitigation | Mitigation relative to internal structure swing range |
| External Mitigation | Mitigation relative to external structure swing range |
| HTF Mitigation | Higher-timeframe mitigation block alignment |
| LTF Mitigation | Lower-timeframe mitigation block nested within HTF zone |
| Confirmed Mitigation | Mitigation validated per confirmation rules |
| Invalidated Mitigation | Zone failed — broken in opposing direction |
| Expired Mitigation | Zone aged beyond configured bar limit without resolution |
| Used Mitigation | Zone fully consumed — no longer an active institutional target |

---

## Out of Scope

- Order block detection (consumed, not produced)
- Fair value gap detection (consumed, not produced)
- Breaker block detection (consumed, not produced)
- Trade signals / entries / exits
- Risk sizing
- Telegram / dashboard
- AI inference
- Modifications to Sprints 1, 2, 3, 4, 5, or 6

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
| Breaker Block (implemented) | [../market-breaker/ARCHITECTURE.md](../market-breaker/ARCHITECTURE.md) |
| Smart Money Contract (broader) | [../engines/smart-money-engine.md](../engines/smart-money-engine.md) |

---

## Implementation Sprint

Sprint 7.2 (planned) will implement this specification in `backend/engines/market_mitigation/` following the module pattern established in Sprints 1–6.
