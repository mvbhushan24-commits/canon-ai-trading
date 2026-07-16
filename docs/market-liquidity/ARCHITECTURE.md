# Market Liquidity Engine — Architecture

**Engine ID:** `market_liquidity`  
**Module:** `backend/engines/market_liquidity/`  
**Sprint:** 3  
**Input:** `NormalizedCandle` + `MarketStructure`  
**Output:** `LiquidityAnalysis`

## Module Structure

```
backend/engines/market_liquidity/
├── engine.py         # LiquidityEngine orchestrator
├── detector.py       # LiquidityDetector
├── external.py       # Previous/weekly/daily/session levels
├── equal.py          # Equal highs/lows, buy/sell side
├── sweep.py          # Sweeps and grabs
├── zones.py          # Liquidity zones
├── config.py         # MarketLiquidityConfig
├── schemas.py        # LiquidityAnalysis and events
├── validator.py      # Input validation
├── events.py         # LiquidityAnalysisEvent
└── publisher.py      # LiquidityEventPublisher
```

## Detection Layers

| Layer | Module | Detects |
|-------|--------|---------|
| External | `external.py` | Previous, weekly, daily, session H/L |
| Internal | `equal.py` | Internal swing highs/lows from structure |
| Equal | `equal.py` | Equal highs/lows clusters |
| Side | `equal.py` | Buy-side / sell-side liquidity |
| Sweep | `sweep.py` | Liquidity sweeps and grabs |
| Zone | `zones.py` | Clustered liquidity zones |

## Dependency Rules

- Consumes `NormalizedCandle` from Market Data Engine
- Consumes `MarketStructure` from Market Structure Engine
- Does not modify Sprint 1 or Sprint 2 code
