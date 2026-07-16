# Engine Interface Contracts

**Sprint:** 0.1  
**Status:** Contract definitions only — no implementation  
**Authority:** [Constitution](../CONSTITUTION.md)

This directory contains interface contracts for all Canon AI Trading engines and presentation components. Each contract defines purpose, I/O, dependencies, events, configuration, errors, and success criteria.

## Contracts

| Engine | Document | Backend Module (future) |
|--------|----------|-------------------------|
| Market Data Engine | [market-data-engine.md](./market-data-engine.md) | `backend/engines/market_data/` |
| Market Structure Engine | [market-structure-engine.md](./market-structure-engine.md) | `backend/engines/market_structure/` |
| Liquidity Engine | [liquidity-engine.md](./liquidity-engine.md) | `backend/engines/liquidity/` |
| Smart Money Engine | [smart-money-engine.md](./smart-money-engine.md) | `backend/engines/smart_money/` |
| Trend Engine | [trend-engine.md](./trend-engine.md) | `backend/engines/trend/` |
| Session Engine | [session-engine.md](./session-engine.md) | TBD |
| News & Macro Engine | [news-macro-engine.md](./news-macro-engine.md) | `backend/engines/news/`, `backend/engines/macro_events/` |
| Risk Engine | [risk-engine.md](./risk-engine.md) | `backend/engines/risk/` |
| Decision Engine | [decision-engine.md](./decision-engine.md) | `backend/engines/decision/` |
| Telegram Engine | [telegram-engine.md](./telegram-engine.md) | `backend/engines/notification/` |
| Dashboard | [dashboard.md](./dashboard.md) | `frontend/` |
| Backtesting Engine | [backtesting-engine.md](./backtesting-engine.md) | TBD |
| Learning Engine | [learning-engine.md](./learning-engine.md) | TBD |

## Contract Rules

1. Engines expose **structured inputs** and **structured outputs** only.
2. Engines do **not** import business logic from sibling engines.
3. Configuration is **external** — no hardcoded values.
4. A **NO TRADE** outcome is valid success for downstream consumers.
5. Contracts are frozen for implementation sprints unless the Product Owner approves changes.

## Event Bus Convention

Events use dot-separated namespacing:

```
<domain>.<entity>.<action>
```

Examples: `market.candle.closed`, `analysis.trend.completed`, `decision.signal.published`

All events include: `event_id`, `timestamp_utc`, `symbol`, `source_engine`, `payload`.
