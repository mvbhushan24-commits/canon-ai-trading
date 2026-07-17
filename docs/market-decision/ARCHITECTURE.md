# Decision Engine — Architecture Specification

**Engine ID:** `market_decision`  
**Sprint:** 10.1 (Architecture only)  
**Version:** 0.1.0-spec  
**Status:** Architecture specification — not implemented  
**Symbol:** XAUUSD / GOLD.i#  
**Architecture Status:** FROZEN (Sprints 1–9 unchanged)

---

## Purpose

The Decision Engine is the **canonical institutional trade decision layer** for the Canon AI Trading platform. It consumes completed evidence from every upstream analysis engine — Market Structure, Liquidity, Order Blocks, Fair Value Gaps, Breaker Blocks, Mitigation Blocks, Premium / Discount, and Market Sessions — and produces **one** explainable trade decision.

Valid directional outcomes are `BUY` and `SELL`. When evidence is insufficient, conflicting, or fails risk validation, the engine returns `NO_TRADE`. This is a **successful outcome**, not a failure.

Per the Constitution:

- **NO TRADE is success** — the engine must never force trades.
- **Clean I/O** — explicit typed inputs and outputs only.
- **External configuration** — all thresholds and weights in YAML; nothing hardcoded.

---

## Responsibilities

| In Scope | Description |
|----------|-------------|
| Input validation | Validate symbol, price, evidence freshness, and configuration |
| Evidence collection | Aggregate upstream analysis envelopes into a unified evidence bundle |
| Evidence normalization | Map per-engine biases, confidences, and zones to a common decision vocabulary |
| Conflict detection | Identify directional disagreement across evidence sources |
| Evidence weighting | Apply configurable per-engine weights to normalized evidence |
| Confidence scoring | Compute 0–100 composite confidence from weighted evidence |
| Risk validation | Enforce minimum/maximum R:R, spread, stop size, and confidence thresholds |
| Session validation | Gate decisions against session, kill zone, and time-of-day filters |
| Premium/Discount validation | Require price location alignment for directional bias |
| Liquidity validation | Confirm liquidity sweep/grab context supports the proposed direction |
| Structure validation | Confirm BOS/CHoCH/trend alignment supports the proposed direction |
| Entry validation | Derive and validate entry zone from confluent institutional zones |
| Stop Loss generation | Compute protective stop beyond invalidation structure |
| Take Profit generation | Compute one or more targets at liquidity / structure levels |
| Risk Reward validation | Reject signals where R:R falls outside configured bounds |
| Final decision generation | Emit `BUY`, `SELL`, `NO_TRADE`, `WAIT`, `NO_DATA`, or `INVALID` |
| Decision quality scoring | Weighted quality model for downstream filtering |
| Event publishing | Emit decision lifecycle events |
| Explainability | Populate reasons, evidence summary, risk summary, and warnings |
| State continuity | Track prior decisions for expiry and update logic |

| Out of Scope | Owner |
|--------------|-------|
| Market data ingestion | Market Data Engine (Sprint 1) |
| Structure / liquidity / zone detection | Sprints 2–8 engines |
| Session / kill zone resolution | Market Sessions Engine (Sprint 9) |
| Order execution | Manual execution (v1.0) |
| Position management | Future sprint |
| Telegram delivery | Telegram Engine |
| Dashboard rendering | Presentation layer |
| AI inference | Future sprint |
| Upstream engine refactoring | Future consolidation sprint |

---

## Dependencies

### Upstream (Evidence Engines)

| Engine | Module | Required | Consumes |
|--------|--------|----------|----------|
| Market Data | `backend.engines.market_data` | **Yes** | `current_price`, `spread` (from tick or latest candle) |
| Market Structure | `backend.engines.market_structure` | Recommended | `MarketStructure` |
| Market Liquidity | `backend.engines.market_liquidity` | Recommended | `LiquidityAnalysis` |
| Order Block | `backend.engines.market_order_block` | Recommended | `OrderBlockAnalysis` |
| Fair Value Gap | `backend.engines.market_fvg` | Recommended | `FairValueGapAnalysis` |
| Breaker Block | `backend.engines.market_breaker` | Recommended | `BreakerBlockAnalysis` |
| Mitigation Block | `backend.engines.market_mitigation` | Recommended | `MitigationBlockAnalysis` |
| Premium / Discount | `backend.engines.market_premium_discount` | Recommended | `PremiumDiscountAnalysis` |
| Market Sessions | `backend.engines.market_sessions` | Recommended | `SessionAnalysis` |

### Input Boundary Rule

The Decision Engine imports **only** the nine upstream type categories listed above from public APIs. It does **not**:

- Import sibling engine internals (`detector.py`, `validator.py`, etc.)
- Re-run upstream detection on raw candles
- Access SQLite or broker APIs directly

Callers or the event bus are responsible for supplying completed analysis envelopes. When an envelope is absent, the engine records the engine as `unavailable` in the evidence summary and applies configured minimum-evidence rules.

### Internal

| Dependency | Description |
|------------|-------------|
| Configuration | `config/settings.yaml` → `market_decision` section |
| Event publisher | In-memory pub/sub (consistent with Sprints 1–9) |
| Core utilities | `backend.core.config`, `backend.core.logging`, `backend.core.exceptions` |
| Decision history store | SQLite (Sprint 10.2) — optional persistence for audit trail |

### Downstream (Future)

| Consumer | Uses |
|----------|------|
| Telegram Engine | `DecisionPublished`, `decision.signal.published` |
| Dashboard | Full `TradeDecision` for visualization |
| Learning Engine | Historical decisions for feedback (future) |
| Backtesting Engine | Decision replay (future) |

---

## Decision States

| State | Terminal | Tradeable | Description |
|-------|----------|-----------|-------------|
| `NO_DATA` | No | No | `current_price` or required bootstrap inputs missing |
| `WAIT` | No | No | Partial evidence; upstream engines still completing or stale |
| `BUY` | Yes | Yes | Qualified long with entry, SL, TP, and passing risk rules |
| `SELL` | Yes | Yes | Qualified short with entry, SL, TP, and passing risk rules |
| `NO_TRADE` | Yes | No | Insufficient evidence, conflict, or risk-blocked — **success** |
| `INVALID` | Yes | No | Validation or configuration failure; error codes populated |

### State Transitions

```
NO_DATA ──(price available)──► WAIT
WAIT ──(evidence complete)──► [pipeline evaluation]
                               ├──► BUY
                               ├──► SELL
                               ├──► NO_TRADE
                               └──► INVALID
BUY/SELL ──(expiry)──► DecisionExpired event; state archived
BUY/SELL ──(evidence change)──► DecisionUpdated or DecisionRejected
```

---

## Architecture Components

```
backend/engines/market_decision/          (Sprint 10.2 — planned)
├── __init__.py                           # Public exports only
├── config.py                             # MarketDecisionConfig + load_market_decision_config()
├── schemas.py                            # TradeDecision, EvidenceBundle, enums
├── exceptions.py                         # Prefixed error codes
├── validator.py                          # DecisionInputValidator
├── engine.py                             # MarketDecisionEngine orchestrator
├── collector.py                          # EvidenceCollector
├── normalizer.py                         # EvidenceNormalizer
├── conflict.py                           # ConflictDetector
├── weighter.py                           # EvidenceWeighter
├── confidence.py                         # ConfidenceScorer
├── session_gate.py                       # SessionValidator
├── structure_gate.py                     # StructureValidator
├── liquidity_gate.py                     # LiquidityValidator
├── premium_discount_gate.py              # PremiumDiscountValidator
├── zone_gates.py                         # OrderBlock/FVG/Breaker/Mitigation validators
├── entry.py                              # EntryValidator + EntryGenerator
├── stop_loss.py                          # StopLossGenerator
├── take_profit.py                        # TakeProfitGenerator
├── risk.py                               # RiskValidator + RiskRewardValidator
├── quality.py                            # DecisionQualityScorer
├── decision.py                           # FinalDecisionGenerator
├── events.py                             # DecisionAnalysisEvent envelope
├── publisher.py                          # DecisionEventPublisher
├── lifecycle.py                          # Decision expiry and update tracking
└── settings.yaml.example
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `MarketDecisionEngine` | Public orchestrator; invokes pipeline stages in order |
| `DecisionInputValidator` | Symbol, price, timestamp, config, and envelope schema checks |
| `EvidenceCollector` | Assemble `EvidenceBundle` from upstream envelopes |
| `EvidenceNormalizer` | Map per-engine outputs to `NormalizedEvidence` records |
| `ConflictDetector` | Detect directional conflicts; compute conflict severity |
| `EvidenceWeighter` | Apply per-engine weights; produce weighted score vector |
| `ConfidenceScorer` | Aggregate weighted evidence into 0–100 confidence |
| `SessionValidator` | Session, kill zone, calendar, and time-of-day gating |
| `StructureValidator` | Trend, BOS, CHoCH alignment with proposed direction |
| `LiquidityValidator` | Sweep/grab/zone context alignment |
| `PremiumDiscountValidator` | Premium/discount/OTE location alignment |
| `ZoneValidators` | OB, FVG, breaker, mitigation confluence checks |
| `EntryValidator` | Validate entry zone against confluent zones and current price |
| `StopLossGenerator` | Derive SL beyond structure invalidation |
| `TakeProfitGenerator` | Derive TP at liquidity pools and structure targets |
| `RiskValidator` | Spread, stop size, session restrictions, news hook |
| `RiskRewardValidator` | Minimum and maximum R:R enforcement |
| `DecisionQualityScorer` | Weighted quality model (separate from confidence) |
| `FinalDecisionGenerator` | Emit terminal `TradeDecision` with full explainability |
| `DecisionEventPublisher` | Publish lifecycle events |

---

## Decision Pipeline

The pipeline executes sequentially. Any stage may short-circuit to `NO_TRADE`, `WAIT`, or `INVALID` with explicit reasons. Stages never override a prior `INVALID` outcome.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DECISION PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Input Validation                                                    │
│  2. Evidence Collection                                                 │
│  3. Evidence Normalization                                              │
│  4. Conflict Detection                                                  │
│  5. Evidence Weighting                                                  │
│  6. Confidence Scoring                                                  │
│  7. Provisional Direction Resolution                                    │
│  8. Session Validation                                                  │
│  9. Premium/Discount Validation                                         │
│ 10. Liquidity Validation                                                │
│ 11. Structure Validation                                                │
│ 12. Zone Validation (OB / FVG / Breaker / Mitigation)                   │
│ 13. Entry Validation & Generation                                       │
│ 14. Stop Loss Generation                                                │
│ 15. Take Profit Generation                                              │
│ 16. Risk Reward Validation                                              │
│ 17. Risk Validation (spread, stop size, news hook)                      │
│ 18. Decision Quality Scoring                                            │
│ 19. Final Decision Generation                                           │
│ 20. Event Publishing                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Stage 1 — Input Validation

| Check | Failure State | Error Code |
|-------|---------------|------------|
| Symbol is `XAUUSD` / `GOLD.i#` | `INVALID` | `DECISION_VALIDATION_FAILED` |
| `timestamp_utc` is timezone-aware UTC | `INVALID` | `DECISION_VALIDATION_FAILED` |
| `current_price` present and > 0 | `NO_DATA` | — |
| Configuration loads and validates | `INVALID` | `DECISION_VALIDATION_FAILED` |
| Evidence envelopes pass schema validation | `INVALID` | Per-domain `INVALID_*` codes |

### Stage 2 — Evidence Collection

Build `EvidenceBundle` containing:

| Key | Source Type | Availability Flag |
|-----|-------------|-------------------|
| `structure` | `MarketStructure` | `structure_available` |
| `liquidity` | `LiquidityAnalysis` | `liquidity_available` |
| `order_blocks` | `OrderBlockAnalysis` | `order_block_available` |
| `fair_value_gaps` | `FairValueGapAnalysis` | `fvg_available` |
| `breaker_blocks` | `BreakerBlockAnalysis` | `breaker_available` |
| `mitigation_blocks` | `MitigationBlockAnalysis` | `mitigation_available` |
| `premium_discount` | `PremiumDiscountAnalysis` | `premium_discount_available` |
| `sessions` | `SessionAnalysis` | `sessions_available` |
| `current_price` | `Decimal` | Always required |
| `spread` | `Decimal \| None` | Optional |

If `min_required_engines` not met → `NO_TRADE` with `INSUFFICIENT_EVIDENCE`.

If envelopes present but exceed `max_evidence_age_seconds` → mark stale, exclude from weighting, note in warnings.

### Stage 3 — Evidence Normalization

Each upstream engine maps to a `NormalizedEvidence` record:

| Field | Type | Description |
|-------|------|-------------|
| `engine_id` | `str` | Source engine identifier |
| `direction_bias` | `DirectionBias` | `bullish`, `bearish`, `neutral`, `undetermined` |
| `confidence` | `Decimal` | 0.0–1.0 from upstream (or derived) |
| `strength` | `Decimal` | 0.0–1.0 composite strength |
| `quality_tier` | `str` | Upstream quality tier when available |
| `key_levels` | `list[PriceLevel]` | Relevant zones, pools, targets |
| `invalidation_level` | `Decimal \| None` | Level that voids the bias |
| `evidence` | `list[str]` | Upstream reasoning snippets |
| `available` | `bool` | Whether envelope was present and fresh |
| `stale` | `bool` | Whether envelope exceeded max age |

#### Normalization Rules (Summary)

| Engine | Bullish Signal | Bearish Signal | Neutral |
|--------|----------------|----------------|---------|
| Market Structure | HH/HL trend, bullish BOS | LH/LL trend, bearish BOS | Range / undetermined |
| Liquidity | Sell-side swept, bullish grab | Buy-side swept, bearish grab | No recent sweep/grab |
| Order Block | Active bullish OB at discount | Active bearish OB at premium | No active OB |
| FVG | Open bullish FVG below price | Open bearish FVG above price | No open gap |
| Breaker | Bullish breaker retest | Bearish breaker retest | No active breaker |
| Mitigation | Bullish mitigation at discount | Bearish mitigation at premium | No active mitigation |
| Premium/Discount | Discount + OTE long context | Premium + OTE short context | Equilibrium / undetermined |
| Sessions | Kill zone active + filter allowed | Kill zone active + filter allowed | Filter blocked / closed |

### Stage 4 — Conflict Detection

Compute `ConflictReport`:

| Metric | Description |
|--------|-------------|
| `bullish_weight` | Sum of bullish-normalized evidence weights |
| `bearish_weight` | Sum of bearish-normalized evidence weights |
| `conflict_ratio` | `min(bull,bear) / max(bull,bear)` when both > 0 |
| `dominant_direction` | Direction with higher weighted sum |
| `conflicting_engines` | Engine pairs with opposing biases |
| `severity` | `none`, `low`, `medium`, `high` |

When `conflict_ratio >= conflict_reject_threshold` → `NO_TRADE` with `CONFLICTING_EVIDENCE`.

When `conflict_ratio >= conflict_warn_threshold` → continue but add warnings and reduce confidence.

### Stage 5 — Evidence Weighting

Apply configurable weights (see [CONFIGURATION.md](./CONFIGURATION.md)):

| Engine | Default Weight |
|--------|----------------|
| Market Structure | 0.20 |
| Liquidity | 0.15 |
| Order Blocks | 0.12 |
| Fair Value Gaps | 0.10 |
| Breaker Blocks | 0.08 |
| Mitigation Blocks | 0.08 |
| Premium / Discount | 0.17 |
| Sessions | 0.10 |

Weighted contribution per engine:

```
contribution = weight × confidence × strength × availability_factor
```

`availability_factor` is `0.0` when unavailable, `0.5` when stale (configurable), `1.0` when fresh.

### Stage 6 — Confidence Scoring

Composite confidence (0–100):

```
raw_score = Σ(contribution_i) / Σ(weight_i)    # normalized to 0.0–1.0
confidence = round(raw_score × 100)

# Adjustments
confidence -= conflict_penalty(conflict_severity)
confidence -= stale_penalty(stale_engine_count)
confidence += confluence_bonus(zone_alignment_count)
confidence = clamp(confidence, 0, 100)
```

When `confidence < min_confidence` → `NO_TRADE` with `LOW_CONFIDENCE`.

### Stage 7 — Provisional Direction Resolution

If confidence passes threshold:

```
if bullish_weight > bearish_weight AND bullish_weight >= min_directional_weight:
    provisional_direction = BUY
elif bearish_weight > bullish_weight AND bearish_weight >= min_directional_weight:
    provisional_direction = SELL
else:
    provisional_direction = NONE → NO_TRADE
```

### Stages 8–12 — Domain Validation Gates

Each gate validates the provisional direction against its domain. Failure produces `NO_TRADE` with domain-specific error code and blocking reason.

| Stage | Gate | Pass Criteria (Summary) |
|-------|------|-------------------------|
| 8 | Session | `time_of_day_filter.is_allowed`, market open, kill zone quality ≥ threshold |
| 9 | Premium/Discount | Long in discount (or OTE); short in premium (or OTE) |
| 10 | Liquidity | Recent sweep/grab supports direction; no opposing pool immediately ahead |
| 11 | Structure | Trend and recent BOS/CHoCH align with direction |
| 12 | Zones | At least `min_zone_confluence` institutional zones align |

### Stage 13 — Entry Validation & Generation

Derive entry from confluent zones:

1. Collect candidate zones from OB, FVG, breaker, mitigation, OTE
2. Filter to zones on correct side of `current_price` for direction
3. Rank by weighted proximity, quality, and MTF alignment
4. Select primary entry zone (price or narrow band)
5. Validate entry is reachable (not beyond `max_entry_distance_pips`)

Failure → `NO_TRADE` with entry blocking reason.

### Stage 14 — Stop Loss Generation

| Direction | Stop Placement Rule |
|-----------|---------------------|
| `BUY` | Below nearest invalidation: OB low, swing low, or liquidity low |
| `SELL` | Above nearest invalidation: OB high, swing high, or liquidity high |

Apply `stop_buffer_pips` beyond invalidation level. Validate stop distance ≤ `max_stop_size_pips`. Failure → `NO_TRADE` with `INVALID_RISK`.

### Stage 15 — Take Profit Generation

Generate one or more targets:

| Priority | Target Source |
|----------|---------------|
| 1 | Opposing liquidity pool (EQH/EQL, buy-side/sell-side) |
| 2 | Structure level (recent swing, dealing range boundary) |
| 3 | FVG fill target |
| 4 | Configured R:R multiple fallback |

Minimum one TP required for `BUY`/`SELL`. Multiple TPs ordered by distance.

### Stage 16 — Risk Reward Validation

```
risk = |entry - stop_loss|
reward = |take_profit[0] - entry|     # primary target
rr = reward / risk
```

| Rule | Default | Failure |
|------|---------|---------|
| `min_risk_reward` | 2.0 | `NO_TRADE` / `INVALID_RISK` |
| `max_risk_reward` | 8.0 | `NO_TRADE` / `INVALID_RISK` |

### Stage 17 — Risk Validation

| Rule | Default | Failure |
|------|---------|---------|
| `max_spread_pips` | 3.0 | `NO_TRADE` / `INVALID_RISK` |
| `max_stop_size_pips` | 50.0 | `NO_TRADE` / `INVALID_RISK` |
| `min_confidence` | 65 | `NO_TRADE` / `LOW_CONFIDENCE` |
| Session restrictions | Per config | `NO_TRADE` / `INVALID_SESSION` |
| News restriction hook | External callback | `NO_TRADE` when hook returns blocked |

#### News Restriction Hook

```python
NewsRestrictionHook = Callable[[str, datetime], NewsRestrictionResult]
```

| Field | Type | Description |
|-------|------|-------------|
| `blocked` | `bool` | Whether trading is blocked |
| `reason` | `str` | Human-readable block reason |
| `expires_utc` | `datetime \| None` | When block lifts |

Hook is injected via configuration reference. Default: no block. Sprint 10.2 implements the interface; News & Macro Engine integration is a future sprint.

### Stage 18 — Decision Quality Scoring

Separate from confidence. Weighted quality model:

| Dimension | Weight | Source |
|-----------|--------|--------|
| Evidence completeness | 0.20 | Available engines / total engines |
| Zone confluence | 0.20 | Aligned OB+FVG+breaker+mitigation count |
| Structure clarity | 0.15 | Trend strength, recent BOS |
| Liquidity confirmation | 0.15 | Sweep/grab recency and quality |
| Premium/Discount alignment | 0.15 | OTE + MTF alignment |
| Session quality | 0.15 | Kill zone quality, overlap bonus |

```
quality_score = Σ(dimension_weight × dimension_score)   # 0–100
quality_tier = high (≥80) | medium (≥60) | low (<60)
```

Quality tier is informational. Low quality does not auto-reject unless `min_quality_score` configured.

### Stage 19 — Final Decision Generation

Assemble `TradeDecision` (see [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md)):

- Set `state` to `BUY` or `SELL` when all gates pass
- Set `state` to `NO_TRADE` when any gate fails
- Populate `reasons`, `evidence_summary`, `risk_summary`, `warnings`
- Assign `decision_id` (UUID)
- Set `valid_until_utc` from `decision_validity_minutes`

### Stage 20 — Event Publishing

| Outcome | Events Published |
|---------|------------------|
| `BUY` / `SELL` | `DecisionCreated`, `DecisionPublished` |
| `NO_TRADE` | `DecisionCreated`, `DecisionRejected` |
| `WAIT` | None (or `DecisionUpdated` if transitioning from prior state) |
| `INVALID` | `DecisionRejected` |
| Evidence change on active decision | `DecisionUpdated` or `DecisionRejected` |
| Expiry | `DecisionExpired` |

---

## Primary Output: `TradeDecision`

| Field | Type | Description |
|-------|------|-------------|
| `decision_id` | `str` | UUID |
| `symbol` | `str` | `XAUUSD` / `GOLD.i#` |
| `timestamp_utc` | `datetime` | Decision timestamp (UTC) |
| `state` | `DecisionState` | `NO_DATA`, `WAIT`, `BUY`, `SELL`, `NO_TRADE`, `INVALID` |
| `direction` | `TradeDirection` | `BUY`, `SELL`, `NONE` |
| `entry` | `EntrySpec` | Entry price or zone |
| `stop_loss` | `Decimal \| None` | Protective stop |
| `take_profit` | `list[Decimal]` | Profit targets (ordered) |
| `risk_reward_ratio` | `Decimal \| None` | Primary target R:R |
| `confidence` | `int` | 0–100 |
| `quality_score` | `int` | 0–100 |
| `quality_tier` | `QualityTier` | `high`, `medium`, `low` |
| `reasons` | `list[str]` | Decision rationale chain |
| `blocking_reasons` | `list[str]` | Why `NO_TRADE` / `INVALID` / `WAIT` |
| `evidence_summary` | `list[EvidenceSummaryItem]` | Per-engine weighted summary |
| `risk_summary` | `RiskSummary` | Spread, stop, R:R, session outcomes |
| `warnings` | `list[str]` | Non-blocking concerns |
| `error_codes` | `list[str]` | Populated on `INVALID` or blocking failures |
| `valid_until_utc` | `datetime \| None` | Decision expiry |
| `metadata` | `DecisionMetadata` | Pipeline version, config hash, duration_ms |

---

## Error Codes

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `DECISION_VALIDATION_FAILED` | Input or config validation failure | `INVALID`; no trade decision |
| `INSUFFICIENT_EVIDENCE` | Fewer than `min_required_engines` available | `NO_TRADE` |
| `CONFLICTING_EVIDENCE` | Conflict ratio exceeds reject threshold | `NO_TRADE` |
| `LOW_CONFIDENCE` | Confidence below `min_confidence` | `NO_TRADE` |
| `INVALID_SESSION` | Session filter blocked or market closed | `NO_TRADE` |
| `INVALID_STRUCTURE` | Structure gate failed | `NO_TRADE` |
| `INVALID_LIQUIDITY` | Liquidity gate failed | `NO_TRADE` |
| `INVALID_ORDER_BLOCK` | Order block confluence insufficient | `NO_TRADE` |
| `INVALID_FVG` | FVG confluence insufficient | `NO_TRADE` |
| `INVALID_BREAKER` | Breaker confluence insufficient | `NO_TRADE` |
| `INVALID_MITIGATION` | Mitigation confluence insufficient | `NO_TRADE` |
| `INVALID_PREMIUM_DISCOUNT` | Price location misaligned with direction | `NO_TRADE` |
| `INVALID_RISK` | R:R, spread, or stop size out of bounds | `NO_TRADE` |

All error codes use prefix `MDE_` in implementation (e.g. `MDE_INSUFFICIENT_EVIDENCE`). Architecture documents use the canonical names above.

---

## Acceptance Criteria (Sprint 10.2)

- [ ] `MarketDecisionEngine.decide(...)` returns `TradeDecision` for all input combinations
- [ ] `NO_TRADE` emitted when evidence insufficient — never forces `BUY`/`SELL`
- [ ] Every decision includes `reasons` and `evidence_summary`
- [ ] `BUY`/`SELL` decisions include entry, stop loss, take profit, and R:R
- [ ] Confidence is 0–100 integer with configurable weights
- [ ] All error codes mapped to explicit blocking reasons
- [ ] Events published per [EVENTS.md](./EVENTS.md)
- [ ] Configuration loaded from YAML with no hardcoded thresholds
- [ ] Upstream engines consumed via public types only
- [ ] No modifications to Sprints 1–9 code or docs

---

## Sprint 10.2 Implementation Plan

Sprint 10.2 implements this architecture in `backend/engines/market_decision/`. No architecture changes without Product Owner approval.

### Phase 1 — Foundation

| Task | Module | Deliverable |
|------|--------|-------------|
| Config model | `config.py` | `MarketDecisionConfig` Pydantic model |
| Schemas | `schemas.py` | `TradeDecision`, `EvidenceBundle`, enums |
| Exceptions | `exceptions.py` | `MDE_*` error codes |
| Input validator | `validator.py` | `DecisionInputValidator` |
| Settings example | `settings.yaml.example` | Documented defaults |

### Phase 2 — Evidence Pipeline

| Task | Module | Deliverable |
|------|--------|-------------|
| Evidence collection | `collector.py` | `EvidenceCollector.collect(...)` |
| Normalization | `normalizer.py` | Per-engine `NormalizedEvidence` mappers |
| Conflict detection | `conflict.py` | `ConflictDetector.detect(...)` |
| Weighting | `weighter.py` | `EvidenceWeighter.weight(...)` |
| Confidence | `confidence.py` | `ConfidenceScorer.score(...)` |

### Phase 3 — Validation Gates

| Task | Module | Deliverable |
|------|--------|-------------|
| Session gate | `session_gate.py` | Session/kill zone validation |
| Structure gate | `structure_gate.py` | Trend/BOS alignment |
| Liquidity gate | `liquidity_gate.py` | Sweep/grab alignment |
| Premium/Discount gate | `premium_discount_gate.py` | Location alignment |
| Zone gates | `zone_gates.py` | OB, FVG, breaker, mitigation |

### Phase 4 — Trade Level Generation

| Task | Module | Deliverable |
|------|--------|-------------|
| Entry | `entry.py` | Entry zone derivation and validation |
| Stop loss | `stop_loss.py` | SL beyond invalidation |
| Take profit | `take_profit.py` | TP at liquidity/structure |
| Risk | `risk.py` | R:R, spread, stop size, news hook |
| Quality | `quality.py` | Decision quality scorer |
| Final decision | `decision.py` | `FinalDecisionGenerator.generate(...)` |

### Phase 5 — Orchestration & Events

| Task | Module | Deliverable |
|------|--------|-------------|
| Engine orchestrator | `engine.py` | `MarketDecisionEngine` |
| Events | `events.py`, `publisher.py` | Full event lifecycle |
| Lifecycle | `lifecycle.py` | Expiry and update tracking |
| Package exports | `__init__.py` | Public API surface |

### Phase 6 — Integration

| Task | Deliverable |
|------|-------------|
| Pipeline orchestrator wiring | Connect Sprints 1–9 outputs to `decide()` |
| Event bus subscriptions | Subscribe to `analysis.*.completed` |
| Config integration | `config/settings.yaml` `market_decision` section |
| SQLite audit table | Optional `decisions` table for history |

### Explicitly Out of Sprint 10.2 Scope

- Sprint 10.3 verification and test suite
- Telegram Engine integration
- Dashboard integration
- News & Macro Engine implementation
- Risk Engine implementation (risk rules are internal to Decision Engine in v1.0)
- Order execution

---

## Recommendations (Not Implemented)

| # | Recommendation | Rationale |
|---|----------------|-----------|
| R1 | Unify engine ID `decision` → `market_decision` in event bus aliases | Consistency with `market_sessions`, `market_breaker` naming |
| R2 | Add optional Risk Engine as upstream input in future sprint | Legacy contract requires `RiskAssessment`; v1.0 uses internal risk rules |
| R3 | Add decision replay API for backtesting | Enables Sprint 11+ backtesting engine |
| R4 | Consolidate `backend/engines/decision/` placeholder into `market_decision/` | Remove Sprint 0 stub ambiguity |

---

## Related Documents

| Document | Path |
|----------|------|
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |
| Constitution | [../CONSTITUTION.md](../CONSTITUTION.md) |
