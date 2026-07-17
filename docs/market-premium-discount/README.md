# Premium / Discount Engine — Architecture Specification Index

**Sprint:** 8.1  
**Engine ID:** `market_premium_discount`  
**Status:** Architecture specification only — not implemented  
**Architecture Status:** FROZEN (Sprints 1–7 unchanged)

---

## Overview

The Premium / Discount Engine is Sprint 8.1 of the Canon AI Trading platform. It is the **authoritative institutional pricing context engine** for gold (XAUUSD / GOLD.i#). It consumes outputs from Market Data, Market Structure, Market Liquidity, Order Block, Fair Value Gap, Breaker Block, and Mitigation Block engines to derive dealing ranges, premium/discount/equilibrium classification, Fibonacci levels, optimal trade entry zones, premium/discount arrays, multi-timeframe alignment, nested zone relationships, and composite institutional pricing context — without emitting trade signals.

This sprint produces **architecture documentation only**. No production code, algorithms, tests, or APIs are included.

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Purpose, responsibilities, dependencies, components, canonical schemas, acceptance criteria |
| [DATA_PIPELINE.md](./DATA_PIPELINE.md) | Data flow from upstream engines through classification to output |
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
Mitigation Block (Sprint 7)
        ↓
Premium / Discount (Sprint 8.1 spec → Sprint 8.2 implementation)
        ↓
Decision Engine (future)
```

---

## Input Sources

| Engine | Output Type | Required |
|--------|-------------|----------|
| Market Data Engine | `NormalizedCandle` | **Yes** |
| Market Structure Engine | `MarketStructure` | **Recommended** |
| Market Liquidity Engine | `LiquidityState` | **Optional** |
| Order Block Engine | `list[OrderBlock]` | **Optional** |
| Fair Value Gap Engine | `FairValueGapState` | **Optional** |
| Breaker Block Engine | `list[BreakerBlock]` | **Optional** |
| Mitigation Block Engine | `list[MitigationBlock]` | **Optional** |

### Input Contract Note

Per Sprint 8.1 specification, the Premium / Discount Engine consumes **only** the seven type categories above from upstream public APIs. It does **not** import full analysis envelopes (`OrderBlockAnalysis`, `FairValueGapAnalysis`, `LiquidityAnalysis`, `BreakerBlockAnalysis`, `MitigationBlockAnalysis`) or downstream engine types. Callers extract partitioned lists and state objects when wiring the pipeline.

Optional `htf_premium_discount_context` may be supplied by the caller for multi-timeframe alignment scoring.

---

## Output Types

| Output | Description |
|--------|-------------|
| Dealing Range | Swing-anchored price range (high, low, equilibrium) |
| Swing High | Confirmed swing high anchor used for range construction |
| Swing Low | Confirmed swing low anchor used for range construction |
| External Range | Dealing range derived from external structure swings |
| Internal Range | Dealing range derived from internal structure swings |
| Premium Zone | Price territory above equilibrium (upper half of dealing range) |
| Discount Zone | Price territory below equilibrium (lower half of dealing range) |
| Equilibrium (50%) | Midpoint of active dealing range |
| Premium Arrays | Clustered institutional zones in premium territory |
| Discount Arrays | Clustered institutional zones in discount territory |
| Internal Premium | Premium classification within internal dealing range |
| Internal Discount | Discount classification within internal dealing range |
| HTF Premium | Higher-timeframe premium context |
| HTF Discount | Higher-timeframe discount context |
| Multi-Timeframe Premium Alignment | LTF premium aligned with HTF premium |
| Multi-Timeframe Discount Alignment | LTF discount aligned with HTF discount |
| Nested Premium Zones | Premium zones nested within parent premium context |
| Nested Discount Zones | Discount zones nested within parent discount context |
| Fibonacci Dealing Range | Configurable Fibonacci levels within dealing range |
| Optimal Trade Entry Zone | OTE band within premium or discount (typically 62–79% retracement) |
| Institutional Pricing Context | Composite pricing narrative for downstream Decision Engine |

---

## Out of Scope

- Order block, FVG, breaker, or mitigation detection (consumed, not produced)
- Trade signals / entries / exits
- Risk sizing
- Telegram / dashboard
- AI inference
- Modifications to Sprints 1–7
- Refactoring upstream engines to remove embedded premium/discount classification (future sprint)

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
| Mitigation Block (implemented) | [../market-mitigation/ARCHITECTURE.md](../market-mitigation/ARCHITECTURE.md) |
| Decision Engine (contract) | [../engines/decision-engine.md](../engines/decision-engine.md) |

---

## Implementation Sprint

Sprint 8.2 (planned) will implement this specification in `backend/engines/market_premium_discount/` following the module pattern established in Sprints 1–7.
