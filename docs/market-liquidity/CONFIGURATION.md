# Market Liquidity Engine — Configuration

```yaml
market_liquidity:
  enabled: true
  timeframes:
    - M15
    - H1
    - H4
  equal_high_tolerance: 3.0
  equal_low_tolerance: 3.0
  pip_size: 0.1
  minimum_cluster_size: 2
  lookback: 100
  min_candles: 20
  session_filter:
    - asian
    - london
    - new_york
  sweep_rejection_ratio: 0.5
  zone_buffer_pips: 2.0

engines:
  market_liquidity: true
```

| Key | Default | Description |
|-----|---------|-------------|
| `equal_high_tolerance` | 3.0 | Pip tolerance for equal highs |
| `equal_low_tolerance` | 3.0 | Pip tolerance for equal lows |
| `minimum_cluster_size` | 2 | Min touches for equal cluster |
| `lookback` | 100 | Bars for external liquidity |
| `session_filter` | asian,london,new_york | Sessions to analyze |
| `sweep_rejection_ratio` | 0.5 | Min body/range for grab detection |
| `zone_buffer_pips` | 2.0 | Zone boundary buffer |
