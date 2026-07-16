# Canon AI Trading — Architecture

**Status:** Frozen (Sprint 0 reference)

This document describes the approved architecture. The Implementation Engineer must not redesign it.

## System Overview

Canon AI Trading is an engine-based platform that ingests XAUUSD market data, runs independent analysis engines, synthesizes decisions, and delivers explainable alerts.

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│  Frontend   │────▶│   FastAPI   │────▶│     SQLite       │
│  (React)    │◀────│   API Layer │◀────│     Database     │
└─────────────┘     └──────┬──────┘     └──────────────────┘
                           │
              ┌────────────┴────────────┐
              │     Engine Pipeline     │
              └────────────┬────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
 Data Ingestion      Analysis Engines       Decision Engine
 (MT5 / XMGlobal)    (SMC, structure,       (signals / NO TRADE)
                     liquidity, trend,
                     price action, macro,
                     news, volatility, risk)
                           │
                           ▼
                  Notification Engine
                    (Telegram Bot API)
```

## Layers

### Presentation Layer

- React + Vite + TypeScript dashboard
- Lightweight Charts for price visualization
- Consumes backend API (future sprints)

### API Layer

- FastAPI application (`backend/main.py`)
- Route modules under `backend/api/routes/` (future sprints)

### Engine Layer

Independent engines under `backend/engines/`:

| Engine | Responsibility |
|--------|----------------|
| `data_ingestion` | Live XAUUSD data from MT5 (XMGlobal) |
| `market_structure` | Market structure analysis |
| `smart_money` | Smart Money Concepts |
| `liquidity` | Liquidity analysis |
| `trend` | Trend context |
| `price_action` | Price action patterns |
| `macro_events` | Macroeconomic events |
| `news` | News impact assessment |
| `volatility` | Volatility conditions |
| `risk` | Risk assessment |
| `decision` | Signal synthesis / NO TRADE |
| `notification` | Telegram alerts |

Each engine:

- Has a single responsibility
- Accepts structured input
- Returns structured output
- Contains no cross-engine business logic (orchestration in future sprints)

### Data Layer

- SQLite database
- Session and models under `backend/db/` (future sprints)

### Configuration

- Environment variables (`.env`)
- YAML settings (`config/settings.yaml`)
- No hardcoded credentials or trading parameters

## External Integrations

| Integration | Purpose | Sprint |
|-------------|---------|--------|
| MetaTrader 5 | Market data (XMGlobal) | Future |
| Telegram Bot API | Signal alerts | Future |

## Design Principles

1. **Modularity** — engines are independently testable
2. **Explainability** — every signal includes reasoning
3. **Conservative decisions** — NO TRADE when evidence is weak
4. **Manual execution** — no automated order placement in v1.0

## Architecture Change Policy

Architecture changes require Product Owner and System Architect approval. The Implementation Engineer documents recommendations only.
