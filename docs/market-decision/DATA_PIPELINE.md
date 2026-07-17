# Decision Engine — Data Pipeline

**Engine ID:** `market_decision`  
**Sprint:** 10.1 (Architecture specification)  
**Status:** Not implemented

---

## Pipeline Overview

```
Market Data (current_price, spread)
        │
        ├──────────────────────────────────────────────────────────────────┐
        │         │         │         │         │         │         │      │
        ▼         ▼         ▼         ▼         ▼         ▼         ▼      ▼
  MarketStructure  LiquidityAnalysis  OrderBlockAnalysis  FairValueGapAnalysis
  (Sprint 2)       (Sprint 3)         (Sprint 4)          (Sprint 5)
        │         │         │         │         │         │         │
        ▼         ▼         ▼         ▼         ▼         ▼         ▼
  BreakerBlockAnalysis  MitigationBlockAnalysis  PremiumDiscountAnalysis  SessionAnalysis
  (Sprint 6)            (Sprint 7)               (Sprint 8)               (Sprint 9)
        │         │         │         │         │         │         │         │
        └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
                                   │
                                   ▼
                        Decision Input Validator
                                   │
                                   ▼
                        Evidence Collector
                                   │
                                   ▼
                        Evidence Normalizer
                                   │
                                   ▼
                        Conflict Detector
                                   │
                                   ▼
                        Evidence Weighter
                                   │
                                   ▼
                        Confidence Scorer
                                   │
                                   ▼
                        Provisional Direction Resolver
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            Session Gate    Premium/Discount Gate  Liquidity Gate
                    │              │              │
                    └──────────────┼──────────────┘
                                   ▼
                          Structure Gate
                                   │
                                   ▼
                    Zone Gates (OB / FVG / Breaker / Mitigation)
                                   │
                                   ▼
                    Entry Validator → Stop Loss → Take Profit
                                   │
                                   ▼
                    Risk Reward Validator → Risk Validator
                                   │
                                   ▼
                        Decision Quality Scorer
                                   │
                                   ▼
                        Final Decision Generator
                                   │
                                   ▼
                            TradeDecision
                                   │
                                   ▼
                        Decision Event Publisher
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            Telegram Engine   Dashboard      Decision History (SQLite)
            (future)          (future)       (Sprint 10.2)
```

---

## Stage 1 — Market Data Input

**Source:** `market.tick.received` event or caller-supplied price

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `current_price` | `Decimal` | **Yes** | Mid price for entry validation and zone proximity |
| `spread` | `Decimal` | No | Risk validation (`max_spread_pips`) |
| `timestamp_utc` | `datetime` | **Yes** | Decision reference time |
| `symbol` | `str` | **Yes** | Must match `XAUUSD` / `GOLD.i#` |

**Failure:** Missing price → `NO_DATA` state; pipeline does not proceed.

**Boundary rule:** Decision Engine reads price from caller or event payload. It does **not** call `MarketDataEngine` directly in the hot path (orchestrator supplies price).

---

## Stage 2 — Market Structure Evidence

**Source:** `MarketStructureEngine.analyze(candles)` or `analysis.structure.completed` event

**Type:** `MarketStructure`

| Field Used | Decision Purpose |
|------------|------------------|
| `current_trend` | Provisional direction bias |
| `bos_events`, `choch_events` | Structure gate; confidence bonus |
| `swing_highs`, `swing_lows` | Stop loss and take profit anchors |
| `confidence` | Normalized evidence confidence |
| `evidence` | Reasons chain |

**Normalization:**

```
trend=bullish  → direction_bias=bullish
trend=bearish  → direction_bias=bearish
trend=range    → direction_bias=neutral
undetermined   → direction_bias=undetermined (weight=0)
```

**Stale threshold:** Default 300 seconds. Stale structure excluded from weighting; warning appended.

---

## Stage 3 — Market Liquidity Evidence

**Source:** `LiquidityEngine.analyze(candles, structure)` or `analysis.liquidity.completed` event

**Type:** `LiquidityAnalysis`

| Field Used | Decision Purpose |
|------------|------------------|
| `bias` | Directional bias |
| `sweeps`, `grabs` | Liquidity gate; entry/TP context |
| `buy_side_liquidity`, `sell_side_liquidity` | TP target pools |
| `equal_highs`, `equal_lows` | TP and SL reference |
| `confidence` | Normalized evidence confidence |
| `evidence` | Reasons chain |

**Normalization:**

```
bias=bullish + recent_sell_side_sweep → direction_bias=bullish, strength+=0.2
bias=bearish + recent_buy_side_sweep  → direction_bias=bearish, strength+=0.2
```

**Gate:** Proposed `BUY` requires sell-side liquidity swept or bullish grab within `liquidity_lookback_bars`. Mirror for `SELL`.

---

## Stage 4 — Order Block Evidence

**Source:** `OrderBlockEngine.analyze(...)` or `analysis.order_block.completed` event

**Type:** `OrderBlockAnalysis`

| Field Used | Decision Purpose |
|------------|------------------|
| `order_blocks` (active) | Zone gate; entry zone candidate |
| `bias` | Directional bias |
| `confidence`, `strength` | Weighting |
| `evidence` | Reasons chain |

**Normalization:** Active bullish OB in discount territory → `bullish`. Active bearish OB in premium → `bearish`.

**Gate:** At least one active OB aligned with provisional direction within `max_zone_distance_pips` of entry candidate.

---

## Stage 5 — Fair Value Gap Evidence

**Source:** `FairValueGapEngine.analyze(...)` or `analysis.fvg.completed` event

**Type:** `FairValueGapAnalysis`

| Field Used | Decision Purpose |
|------------|------------------|
| `state.active_gaps` | Zone gate; entry zone candidate |
| `bias` | Directional bias |
| `confidence`, `strength` | Weighting |
| `evidence` | Reasons chain |

**Normalization:** Open bullish FVG below price → `bullish`. Open bearish FVG above price → `bearish`.

**Gate:** At least one open FVG aligned with direction, or FVG confluence waived when `min_zone_confluence` met by other zones.

---

## Stage 6 — Breaker Block Evidence

**Source:** `BreakerBlockEngine.analyze(...)` or `analysis.breaker.completed` event

**Type:** `BreakerBlockAnalysis`

| Field Used | Decision Purpose |
|------------|------------------|
| `breaker_blocks` (active) | Zone gate; entry zone candidate |
| `bias` | Directional bias |
| `confidence`, `strength` | Weighting |
| `evidence` | Reasons chain |

**Normalization:** Active bullish breaker in retest phase → `bullish`. Active bearish breaker in retest → `bearish`.

---

## Stage 7 — Mitigation Block Evidence

**Source:** `MitigationBlockEngine.analyze(...)` or `analysis.mitigation.completed` event

**Type:** `MitigationBlockAnalysis`

| Field Used | Decision Purpose |
|------------|------------------|
| `mitigation_blocks` (active) | Zone gate; entry zone candidate |
| `bias` | Directional bias |
| `confidence`, `strength` | Weighting |
| `evidence` | Reasons chain |

**Normalization:** Active bullish mitigation at discount → `bullish`. Active bearish mitigation at premium → `bearish`.

---

## Stage 8 — Premium / Discount Evidence

**Source:** `PremiumDiscountEngine.analyze(...)` or `analysis.premium_discount.completed` event

**Type:** `PremiumDiscountAnalysis`

| Field Used | Decision Purpose |
|------------|------------------|
| `price_location` | Premium/Discount gate |
| `bias` | Directional bias |
| `ote_zone` | Entry zone candidate |
| `institutional_context` | Reasons chain enrichment |
| `mtf_premium_alignment`, `mtf_discount_alignment` | Quality and confidence bonus |
| `dealing_range` | SL/TP boundary reference |
| `confidence`, `strength` | Weighting |

**Normalization:**

```
price_location=discount + bias=discount → bullish (long bias)
price_location=premium  + bias=premium  → bearish (short bias)
equilibrium             → neutral
undetermined            → excluded from weighting
```

**Gate:**

- `BUY` requires `price_location` in `{discount, equilibrium}` or active OTE long zone
- `SELL` requires `price_location` in `{premium, equilibrium}` or active OTE short zone

---

## Stage 9 — Market Sessions Evidence

**Source:** `MarketSessionsEngine.analyze(...)` or `analysis.session.completed` event

**Type:** `SessionAnalysis`

| Field Used | Decision Purpose |
|------------|------------------|
| `time_of_day_filter.is_allowed` | Session gate (hard block when false) |
| `market_availability` | Session gate |
| `active_kill_zones` | Session quality scoring |
| `quality`, `confidence`, `strength` | Weighting |
| `volatility_profile` | Warning generation |
| `evidence` | Reasons chain |

**Normalization:**

```
filter.is_allowed=true + active_kill_zone → bullish/bearish neutral (context only)
filter.is_allowed=false                 → session_bias=blocked
market_availability=closed              → session_bias=blocked
```

**Gate:**

```
if not session_analysis.time_of_day_filter.is_allowed:
    → NO_TRADE, INVALID_SESSION
if session_analysis.market_availability == "closed":
    → NO_TRADE, INVALID_SESSION
```

---

## Stage 10 — Evidence Bundle Assembly

After collection, the pipeline holds an `EvidenceBundle`:

```python
EvidenceBundle(
    symbol="GOLD.i#",
    timestamp_utc=...,
    current_price=Decimal("2345.50"),
    spread=Decimal("0.25"),
    structure=MarketStructure | None,
    liquidity=LiquidityAnalysis | None,
    order_blocks=OrderBlockAnalysis | None,
    fair_value_gaps=FairValueGapAnalysis | None,
    breaker_blocks=BreakerBlockAnalysis | None,
    mitigation_blocks=MitigationBlockAnalysis | None,
    premium_discount=PremiumDiscountAnalysis | None,
    sessions=SessionAnalysis | None,
    availability=EvidenceAvailability(...),
)
```

### Minimum Evidence Rule

```
available_count = count(availability.* == true AND NOT stale)
if available_count < config.min_required_engines:
    → NO_TRADE, INSUFFICIENT_EVIDENCE
```

Default `min_required_engines`: 5 (of 8 evidence engines).

---

## Stage 11 — Normalization & Weighting

Each available evidence source produces a `NormalizedEvidence` record. See [ARCHITECTURE.md § Evidence Normalization](./ARCHITECTURE.md#stage-3--evidence-normalization).

Weighted score vector:

```
scores = {
    "market_structure":      0.20 × norm.confidence × norm.strength,
    "market_liquidity":      0.15 × norm.confidence × norm.strength,
    "order_block":           0.12 × norm.confidence × norm.strength,
    "fair_value_gap":        0.10 × norm.confidence × norm.strength,
    "market_breaker":        0.08 × norm.confidence × norm.strength,
    "market_mitigation":     0.08 × norm.confidence × norm.strength,
    "market_premium_discount": 0.17 × norm.confidence × norm.strength,
    "market_sessions":       0.10 × norm.confidence × norm.strength,
}
```

---

## Stage 12 — Conflict Detection & Confidence

```
bullish_total = Σ scores where direction_bias == bullish
bearish_total = Σ scores where direction_bias == bearish
conflict_ratio = min(bullish, bearish) / max(bullish, bearish)
confidence = normalize(bullish_total + bearish_total) × 100 - penalties + bonuses
```

See [CONFIGURATION.md](./CONFIGURATION.md) for thresholds.

---

## Stage 13 — Validation Gate Chain

Gates execute in order. First failure short-circuits to `NO_TRADE`:

| Order | Gate | Error Code |
|-------|------|------------|
| 1 | Session | `INVALID_SESSION` |
| 2 | Premium/Discount | `INVALID_PREMIUM_DISCOUNT` |
| 3 | Liquidity | `INVALID_LIQUIDITY` |
| 4 | Structure | `INVALID_STRUCTURE` |
| 5 | Order Block | `INVALID_ORDER_BLOCK` |
| 6 | FVG | `INVALID_FVG` |
| 7 | Breaker | `INVALID_BREAKER` |
| 8 | Mitigation | `INVALID_MITIGATION` |

Zone gates (5–8) may be evaluated as a group when `zone_gate_mode: grouped` (default). Grouped mode requires `min_zone_confluence` of 2 aligned zones across any combination of OB/FVG/breaker/mitigation.

---

## Stage 14 — Entry, Stop Loss, Take Profit

### Entry Derivation

```
candidates = []
candidates += active_ob_zones_aligned(direction)
candidates += open_fvg_zones_aligned(direction)
candidates += active_breaker_zones_aligned(direction)
candidates += active_mitigation_zones_aligned(direction)
candidates += ote_zone(direction)  # from PremiumDiscountAnalysis

entry = rank_and_select(candidates, current_price, direction)
```

### Stop Loss Derivation

```
invalidation = nearest_invalidation_level(direction, structure, zones, liquidity)
stop_loss = invalidation - buffer  # BUY
stop_loss = invalidation + buffer  # SELL
```

### Take Profit Derivation

```
tp_candidates = opposing_liquidity_pools(direction)
tp_candidates += structure_targets(direction)
tp_candidates += fvg_fill_targets(direction)
take_profit = select_ordered(tp_candidates, min_rr=config.min_risk_reward)
```

---

## Stage 15 — Risk Validation

| Check | Input | Rule |
|-------|-------|------|
| R:R | entry, SL, TP[0] | `min_risk_reward ≤ rr ≤ max_risk_reward` |
| Spread | `spread` | `spread ≤ max_spread_pips` |
| Stop size | entry, SL | `|entry - SL| ≤ max_stop_size_pips` |
| Confidence | computed | `confidence ≥ min_confidence` |
| Session | `SessionAnalysis` | Allowed session/kill zone |
| News hook | external callback | Not blocked |

---

## Stage 16 — Output & Events

**Output:** `TradeDecision`

**Events:**

| State | Event |
|-------|-------|
| `BUY` / `SELL` | `DecisionCreated` → `DecisionPublished` |
| `NO_TRADE` | `DecisionCreated` → `DecisionRejected` |
| `INVALID` | `DecisionRejected` |
| Active decision superseded | `DecisionUpdated` or `DecisionRejected` |
| `valid_until_utc` elapsed | `DecisionExpired` |

Contract bus names maintained for legacy compatibility. See [EVENTS.md](./EVENTS.md).

---

## Orchestration Modes

### Mode A — Direct Call (Primary)

```python
decision = market_decision_engine.decide(
    symbol="GOLD.i#",
    timestamp_utc=now,
    current_price=price,
    spread=spread,
    structure=structure,
    liquidity=liquidity,
    order_blocks=order_blocks,
    fair_value_gaps=fvg,
    breaker_blocks=breaker,
    mitigation_blocks=mitigation,
    premium_discount=premium_discount,
    sessions=sessions,
)
```

Pipeline orchestrator runs Sprints 1–9, then passes envelopes to `decide()`.

### Mode B — Event Bus (Reactive)

Decision Engine subscribes to `analysis.*.completed` and `market.tick.received`. Internal state cache holds latest envelope per engine. Decision cycle triggers when:

1. All required engines have fresh completions, OR
2. Configured debounce interval elapsed with partial evidence, OR
3. Explicit `decision.evaluate` command received

Partial evidence → `WAIT` until `min_required_engines` met or `wait_timeout_seconds` → `NO_TRADE`.

---

## Data Freshness

| Engine | Default Max Age (seconds) |
|--------|---------------------------|
| Market Structure | 300 |
| Market Liquidity | 300 |
| Order Block | 300 |
| Fair Value Gap | 300 |
| Breaker Block | 300 |
| Mitigation Block | 300 |
| Premium / Discount | 300 |
| Market Sessions | 60 |
| Current Price | 30 |

Stale envelopes are excluded from weighting. Price older than 30 seconds → `WAIT` or `NO_DATA`.

---

## Performance Considerations

| Concern | Mitigation |
|---------|------------|
| Repeated normalization | Cache `NormalizedEvidence` per envelope hash |
| Gate chain latency | Short-circuit on first failure |
| Event storm | Debounce `decide()` triggers (default 5 seconds) |
| Memory | Evict stale cache entries per `max_evidence_age_seconds` |

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |
