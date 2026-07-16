# Market Liquidity Engine — Data Pipeline

```
NormalizedCandles (Market Data Engine)
        │
        ▼
MarketStructure (Market Structure Engine)
        │
        ▼
Liquidity Input Validator
        │
        ├─► External Liquidity Detector
        ├─► Internal Liquidity (from structure)
        ├─► Equal High/Low Detector
        ├─► Buy/Sell Side Detector
        ├─► Sweep/Grab Detector
        └─► Zone Builder
        │
        ▼
LiquidityAnalysis
        │
        ▼
Event Publisher
```

## Events

| Event | Trigger |
|-------|---------|
| `LiquidityDetectedEvent` | Level identified |
| `LiquiditySweepEvent` | Sweep detected |
| `LiquidityGrabEvent` | Grab after sweep |
| `LiquidityZoneEvent` | Zone created |
| `analysis.liquidity.completed` | Analysis done |
