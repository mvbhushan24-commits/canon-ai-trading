# Market Structure Engine — Data Pipeline

```
NormalizedCandles (Market Data Engine)
        │
        ▼
   Input Validator
        │
        ▼
  Swing Detector ──────► Internal Structure
        │                External Structure
        ▼
  Swing Labeler (HH/HL/LH/LL)
        │
        ▼
   Trend Analyzer
        │
        ├──────────────┐
        ▼              ▼
   BOS Detector   CHoCH Detector
        │              │
        └──────┬───────┘
               ▼
        MarketStructure
               │
               ▼
      Event Publisher
               │
               ▼
   Future Engines (Liquidity, SMC, Decision)
```

---

## ASCII Pipeline

```
Market Data Engine
        │
        ▼
 NormalizedCandles
        │
        ▼
    Validator
        │
        ▼
 Swing Detection
        │
        ▼
 HH / HL / LH / LL
        │
        ▼
  Trend Analysis
        │
        ▼
  BOS + CHoCH
        │
        ▼
 MarketStructure
        │
        ▼
    Events
        │
        ▼
 Future Analysis Engines
```

---

## Event Flow

| Step | Event |
|------|-------|
| Swing confirmed | `SwingDetected` |
| BOS found | `BOSDetected` / `analysis.structure.bos_detected` |
| CHoCH found | `CHoCHDetected` / `analysis.structure.choch_detected` |
| Trend shift | `TrendChanged` / `analysis.structure.bias_changed` |
| Analysis done | `StructureUpdated` / `analysis.structure.completed` |

---

## Consumption Pattern

```python
from backend.engines.market_data import MarketDataEngine, NormalizedCandle
from backend.engines.market_structure import MarketStructureEngine

# Sprint 1 — fetch candles
candles: list[NormalizedCandle] = market_data_engine.load_historical_candles(timeframe="H1")

# Sprint 2 — analyze structure
structure_engine = MarketStructureEngine()
result = structure_engine.analyze(candles)
```

No direct import of MT5, broker, or market_data internal modules.
