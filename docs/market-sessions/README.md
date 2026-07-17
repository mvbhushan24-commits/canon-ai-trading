# Kill Zones & Trading Sessions Engine — Architecture Specification Index

**Sprint:** 9.1  
**Engine ID:** `market_sessions`  
**Status:** Architecture specification only — not implemented  
**Architecture Status:** FROZEN (Sprints 1–8 unchanged)

---

## Overview

The Kill Zones & Trading Sessions Engine is Sprint 9.1 of the Canon AI Trading platform. It is the **authoritative temporal context engine** for gold (XAUUSD / GOLD.i#). It consumes outputs from Market Data and upstream analysis engines to identify trading sessions, ICT-style kill zones, session transitions and overlaps, daily/weekly/monthly opens, session highs and lows, opening range, initial balance, time-of-day filters, and broker-normalized calendar handling — without emitting trade signals.

This sprint produces **architecture documentation only**. No production code, algorithms, tests, or APIs are included.

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Purpose, responsibilities, dependencies, components, canonical schemas, acceptance criteria |
| [DATA_PIPELINE.md](./DATA_PIPELINE.md) | Data flow from upstream engines through session resolution to output |
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
Premium / Discount (Sprint 8)
        ↓
Kill Zones & Sessions (Sprint 9.1 spec → Sprint 9.2 implementation)
        ↓
Decision Engine (future)
```

---

## Input Sources

| Engine | Output Type | Required |
|--------|-------------|----------|
| Market Data Engine | `NormalizedCandle` | **Yes** |
| Market Structure Engine | `MarketStructure` | **Optional** |
| Market Liquidity Engine | `LiquidityState` | **Optional** |
| Premium / Discount Engine | `PremiumDiscountAnalysis` | **Optional** |

### Input Contract Note

Per Sprint 9.1 specification, the Kill Zones & Sessions Engine consumes **only** the type categories above from upstream public APIs. It does **not** import full analysis envelopes (`LiquidityAnalysis`, etc.) or downstream engine types. Callers extract partitioned state objects when wiring the pipeline.

A reference `timestamp_utc` and optional `broker_timezone` are supplied by the caller for live session resolution.

---

## Output Types

| Output | Description |
|--------|-------------|
| Sydney Session | Active/inactive Sydney session window and phase |
| Tokyo Session | Active/inactive Tokyo session window and phase |
| London Session | Active/inactive London session window and phase |
| New York Session | Active/inactive New York session window and phase |
| Asian Kill Zone | ICT-style Asian kill zone state and quality |
| London Open Kill Zone | London open kill zone state and quality |
| New York Kill Zone | New York kill zone state and quality |
| London Close Kill Zone | London close kill zone state and quality |
| Session Transitions | Upcoming and recent session boundary crossings |
| Session Overlaps | Active overlap windows (e.g. London–New York) |
| Daily Open | Current trading day open price and timestamp |
| Weekly Open | Current trading week open price and timestamp |
| Monthly Open | Current trading month open price and timestamp |
| Session High / Low | Per-session high and low price levels |
| Opening Range | Configurable post-open price range |
| Initial Balance | Configurable initial balance range (typically first hour) |
| Time-of-Day Filter | Allow/block windows for downstream consumption |
| Weekend / DST / Holiday Context | Calendar normalization and market availability |
| Broker Timezone Normalization | All windows expressed in UTC with broker offset |
| Session Quality Context | Composite temporal context for Decision Engine |

---

## Out of Scope

- Trade signals / entries / exits
- Economic calendar event detection (News & Macro Engine)
- Risk sizing
- Telegram / dashboard
- AI inference
- Modifications to Sprints 1–8
- Replacing embedded session filters in upstream engines (future consolidation sprint)

---

## Relationship to Legacy Session Engine Contract

An earlier platform contract exists at [../engines/session-engine.md](../engines/session-engine.md) with engine ID `session`. Sprint 9.1 **`market_sessions`** supersedes that contract for implementation purposes while preserving compatible event naming where practical. The Decision Engine will consume `SessionAnalysis` from `market_sessions` when implemented.

---

## Related Platform Documents

| Document | Path |
|----------|------|
| System Architecture | [../SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) |
| Constitution | [../CONSTITUTION.md](../CONSTITUTION.md) |
| Market Data (implemented) | [../market-data/ARCHITECTURE.md](../market-data/ARCHITECTURE.md) |
| Market Structure (implemented) | [../market-structure/ARCHITECTURE.md](../market-structure/ARCHITECTURE.md) |
| Market Liquidity (implemented) | [../market-liquidity/ARCHITECTURE.md](../market-liquidity/ARCHITECTURE.md) |
| Premium / Discount (implemented) | [../market-premium-discount/ARCHITECTURE.md](../market-premium-discount/ARCHITECTURE.md) |
| Decision Engine (contract) | [../engines/decision-engine.md](../engines/decision-engine.md) |
| Legacy Session Engine (contract) | [../engines/session-engine.md](../engines/session-engine.md) |

---

## Implementation Sprint

Sprint 9.2 (planned) will implement this specification in `backend/engines/market_sessions/` following the module pattern established in Sprints 1–8.
