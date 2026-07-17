# Signal Engine — Architecture Specification

**Engine ID:** `market_signal`  
**Sprint:** 11.1 (Architecture only)  
**Version:** 0.1.0-spec  
**Status:** Architecture specification — not implemented  
**Symbol:** XAUUSD / GOLD.i#  
**Architecture Status:** FROZEN (Sprints 1–10 unchanged)

---

## Purpose

The Signal Engine is the **canonical institutional trading signal layer** for the Canon AI Trading platform. It consumes validated `TradeDecision` outputs from the Decision Engine and converts qualified `BUY` and `SELL` decisions into lifecycle-managed **trading signals** for downstream delivery and monitoring.

The Signal Engine **never analyzes the market**. It performs no evidence collection, no zone detection, no structure analysis, and no directional inference. All analytical work is complete when the Decision Engine emits a decision. The Signal Engine validates, normalizes, scores, and publishes signals — nothing more.

Per the Constitution:

- **NO TRADE is success** — `NO_TRADE`, `WAIT`, `NO_DATA`, and `INVALID` decisions produce no signal.
- **Clean I/O** — single upstream input type (`TradeDecision`); single downstream output type (`TradingSignal`).
- **External configuration** — all thresholds and weights in YAML; nothing hardcoded.

---

## Responsibilities

| In Scope | Description |
|----------|-------------|
| Decision intake | Accept `TradeDecision` from orchestrator or `DecisionPublished` events |
| Decision validation | Verify decision state, schema, freshness, and required fields |
| Signal validation | Duplicate detection, confidence, session, risk, and expiry checks |
| Entry normalization | Resolve `EntrySpec` (point, zone, OTE) to `entry_price` |
| Take profit mapping | Map decision `take_profit` list to TP1, TP2, TP3 |
| Signal assembly | Build `TradingSignal` with full explainability fields |
| Signal quality scoring | Weighted quality model (separate from decision confidence) |
| Signal lifecycle | Track states from `CREATED` through terminal outcomes |
| Lifecycle updates | Apply price-threshold checks for trigger, TP, and SL (operational only) |
| Duplicate prevention | Detect and reject near-duplicate active signals |
| Event publishing | Emit signal lifecycle events |
| Signal history | Optional persistence for audit and dashboard |

| Out of Scope | Owner |
|--------------|-------|
| Market analysis | Sprints 1–9 engines |
| Trade decision synthesis | Decision Engine (Sprint 10) |
| Evidence weighting / conflict detection | Decision Engine |
| Order execution | Manual execution (v1.0) |
| Telegram formatting / delivery | Telegram Engine |
| Dashboard rendering | Presentation layer |
| Upstream engine consumption | Prohibited |
| Decision Engine modification | Sprint 10 (frozen) |

---

## Dependencies

### Upstream (Single Source)

| Engine | Module | Required | Consumes |
|--------|--------|----------|----------|
| Decision Engine | `backend.engines.market_decision` | **Yes** | `TradeDecision` |

### Input Boundary Rule

The Signal Engine imports **only** `TradeDecision` and related decision types from the Decision Engine public API. It does **not**:

- Import Sprints 1–9 engine modules
- Re-run decision pipeline stages
- Access SQLite, broker APIs, or raw candles
- Perform technical analysis on price data

Price supplied to lifecycle methods (`update_lifecycle`, `check_levels`) is used **exclusively** for threshold comparison against pre-computed signal levels. This is operational state tracking, not market analysis.

### Internal

| Dependency | Description |
|------------|-------------|
| Configuration | `config/settings.yaml` → `market_signal` section |
| Event publisher | In-memory pub/sub (consistent with Sprints 1–10) |
| Core utilities | `backend.core.config`, `backend.core.logging`, `backend.core.exceptions` |
| Signal store | SQLite (Sprint 11.2) — optional persistence for active and historical signals |

### Downstream (Future)

| Consumer | Uses |
|----------|------|
| Telegram Engine | `SignalActivated`, `signal.activated` |
| Dashboard | Full `TradingSignal` for visualization and lifecycle UI |
| Learning Engine | Historical signals for feedback (future) |
| Backtesting Engine | Signal replay (future) |

---

## Signal States

| State | Terminal | Tradeable | Description |
|-------|----------|-----------|-------------|
| `CREATED` | No | No | Signal assembled; pending activation |
| `ACTIVE` | No | Yes | Signal published and monitorable |
| `TRIGGERED` | No | Yes | Entry price reached |
| `PARTIALLY_FILLED` | No | Yes | Partial entry fill recorded |
| `TP1_HIT` | No | Yes | Take profit 1 reached |
| `TP2_HIT` | No | Yes | Take profit 2 reached |
| `TP3_HIT` | No | Yes | Take profit 3 reached |
| `BREAK_EVEN` | No | Yes | Stop moved to break-even |
| `TRAILING` | No | Yes | Trailing stop active |
| `STOP_LOSS` | Yes | No | Stop loss hit |
| `CLOSED` | Yes | No | Signal fully closed (any completion path) |
| `EXPIRED` | Yes | No | Expiry reached without trigger or completion |
| `CANCELLED` | Yes | No | Manual or system cancellation |

### State Transitions

```
Decision BUY/SELL ──(validation pass)──► CREATED
CREATED ──(activate)──► ACTIVE
ACTIVE ──(entry reached)──► TRIGGERED
TRIGGERED ──(partial fill)──► PARTIALLY_FILLED
TRIGGERED/PARTIALLY_FILLED ──(TP1)──► TP1_HIT
TP1_HIT ──(TP2)──► TP2_HIT
TP2_HIT ──(TP3)──► TP3_HIT
TRIGGERED+ ──(break-even rule)──► BREAK_EVEN
BREAK_EVEN ──(trailing enabled)──► TRAILING
Any open ──(SL hit)──► STOP_LOSS ──► CLOSED
Any open ──(manual close)──► CLOSED
Any open ──(cancel)──► CANCELLED
ACTIVE (untriggered) ──(expiry)──► EXPIRED
Validation fail ──► (no signal; rejection event only)
```

Terminal states (`STOP_LOSS`, `CLOSED`, `EXPIRED`, `CANCELLED`) emit `SignalClosed` or `SignalExpired` / `SignalCancelled` as appropriate.

---

## Architecture Components

```
backend/engines/market_signal/          (Sprint 11.2 — planned)
├── __init__.py                           # Public exports only
├── config.py                             # MarketSignalConfig + load_market_signal_config()
├── schemas.py                            # TradingSignal, SignalRejection, enums
├── exceptions.py                         # Prefixed error codes
├── validator.py                          # SignalInputValidator
├── engine.py                             # MarketSignalEngine orchestrator
├── decision_gate.py                      # DecisionValidator
├── duplicate.py                          # DuplicateDetector
├── confidence_gate.py                    # ConfidenceValidator
├── session_gate.py                       # SessionValidator (decision-derived)
├── risk_gate.py                          # RiskValidator (decision-derived)
├── expiry_gate.py                        # ExpiryValidator
├── normalizer.py                         # EntryNormalizer + TakeProfitMapper
├── quality.py                            # SignalQualityScorer
├── assembler.py                          # SignalAssembler
├── lifecycle.py                          # SignalLifecycleManager
├── events.py                             # SignalAnalysisEvent envelope
├── publisher.py                          # SignalEventPublisher
├── store.py                              # SignalStore (SQLite)
└── settings.yaml.example
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `MarketSignalEngine` | Public orchestrator; invokes pipeline and lifecycle |
| `SignalInputValidator` | Envelope schema, symbol, and config checks |
| `DecisionValidator` | Decision state, field completeness, freshness |
| `DuplicateDetector` | Compare against active signals; reject duplicates |
| `ConfidenceValidator` | Enforce `min_confidence` threshold |
| `SessionValidator` | Re-check session allowance from decision `risk_summary` |
| `RiskValidator` | Re-validate R:R, stop size, spread from decision |
| `ExpiryValidator` | Reject decisions past `valid_until_utc` |
| `EntryNormalizer` | Resolve `EntrySpec` to single `entry_price` |
| `TakeProfitMapper` | Map `take_profit[0..2]` to TP1/TP2/TP3 |
| `SignalQualityScorer` | Weighted quality model |
| `SignalAssembler` | Build `TradingSignal` from validated decision |
| `SignalLifecycleManager` | State transitions and level checks |
| `SignalEventPublisher` | Publish lifecycle events |
| `SignalStore` | Persist active and historical signals |

---

## Signal Pipeline

The pipeline executes sequentially. Any stage may reject signal creation with explicit error codes and reasons. Rejection produces no `TradingSignal`; a rejection record may be emitted for audit.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SIGNAL PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Input Validation                                                    │
│  2. Decision Validation                                                 │
│  3. Expiry Validation                                                   │
│  4. Confidence Validation                                               │
│  5. Session Validation                                                  │
│  6. Risk Validation                                                     │
│  7. Duplicate Detection                                                 │
│  8. Entry Normalization                                                 │
│  9. Take Profit Mapping                                                 │
│ 10. Signal Quality Scoring                                              │
│ 11. Signal Assembly                                                     │
│ 12. Signal Activation                                                   │
│ 13. Event Publishing                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Stage 1 — Input Validation

| Check | Failure | Error Code |
|-------|---------|------------|
| `TradeDecision` schema valid | Reject | `SIGNAL_VALIDATION_FAILED` |
| Symbol is `XAUUSD` / `GOLD.i#` | Reject | `SIGNAL_VALIDATION_FAILED` |
| `timestamp_utc` timezone-aware UTC | Reject | `SIGNAL_VALIDATION_FAILED` |
| Configuration loads and validates | Reject | `SIGNAL_VALIDATION_FAILED` |

### Stage 2 — Decision Validation

| Check | Failure | Error Code |
|-------|---------|------------|
| `state` is `BUY` or `SELL` | No signal (success for `NO_TRADE`/`WAIT`) | `INVALID_DECISION` |
| `direction` matches `state` | Reject | `INVALID_DECISION` |
| `entry` present and valid | Reject | `INVALID_DECISION` |
| `stop_loss` present | Reject | `INVALID_DECISION` |
| `take_profit` has ≥ 1 target | Reject | `INVALID_DECISION` |
| `risk_reward_ratio` present | Reject | `INVALID_DECISION` |
| `confidence` present (0–100) | Reject | `INVALID_DECISION` |
| `evidence_summary` non-empty | Reject (when required) | `INVALID_DECISION` |

**Non-tradeable decision states:**

| State | Behavior | Error Code |
|-------|----------|------------|
| `NO_TRADE` | No signal; log rejection reason from decision | — (success) |
| `WAIT` | No signal; await next decision | — (success) |
| `NO_DATA` | No signal | — (success) |
| `INVALID` | No signal | `INVALID_DECISION` |

### Stage 3 — Expiry Validation

| Check | Failure | Error Code |
|-------|---------|------------|
| `valid_until_utc` not elapsed | Reject | `SIGNAL_EXPIRED` |
| Decision age ≤ `max_decision_age_seconds` | Reject | `SIGNAL_EXPIRED` |

### Stage 4 — Confidence Validation

| Check | Failure | Error Code |
|-------|---------|------------|
| `confidence >= min_confidence` | Reject | `LOW_CONFIDENCE` |
| `quality_score >= min_decision_quality` (optional) | Reject | `LOW_CONFIDENCE` |

### Stage 5 — Session Validation

Re-validates session context **from decision fields only** — no session engine calls.

| Check | Source | Failure | Error Code |
|-------|--------|---------|------------|
| `risk_summary.session_allowed == true` | Decision | Reject | `SIGNAL_VALIDATION_FAILED` |
| Session not in `blocked_sessions` list | Config + decision metadata | Reject | `SIGNAL_VALIDATION_FAILED` |

### Stage 6 — Risk Validation

Re-validates risk **from decision fields only** — no new risk computation.

| Check | Source | Failure | Error Code |
|-------|--------|---------|------------|
| `risk_summary.min_rr_met == true` | Decision | Reject | `INVALID_RISK` |
| `risk_summary.spread_acceptable == true` | Decision | Reject | `INVALID_RISK` |
| `risk_summary.stop_size_acceptable == true` | Decision | Reject | `INVALID_RISK` |
| `risk_reward_ratio >= min_risk_reward` | Decision + config | Reject | `INVALID_RISK` |
| `risk_reward_ratio <= max_risk_reward` | Decision + config | Reject | `INVALID_RISK` |

### Stage 7 — Duplicate Detection

| Check | Failure | Error Code |
|-------|---------|------------|
| No active signal with same symbol + direction within `duplicate_window_minutes` | Reject | `DUPLICATE_SIGNAL` |
| Entry price within `duplicate_entry_tolerance_pips` of active signal | Reject | `DUPLICATE_SIGNAL` |
| Same `decision_id` already converted | Reject | `DUPLICATE_SIGNAL` |

### Stage 8 — Entry Normalization

Resolve `EntrySpec` to `entry_price`:

| `entry_type` | Resolution Rule |
|--------------|-----------------|
| `point` | Use `entry.price` |
| `zone` | Use midpoint `(zone_high + zone_low) / 2` or configured zone edge per direction |
| `ote` | Use OTE midpoint or configured OTE preference |

| Direction | Zone Edge Preference (configurable) |
|-----------|-------------------------------------|
| `BUY` | `zone_low` (aggressive) or midpoint (default) |
| `SELL` | `zone_high` (aggressive) or midpoint (default) |

### Stage 9 — Take Profit Mapping

| Decision Field | Signal Field |
|----------------|--------------|
| `take_profit[0]` | `take_profit_1` (**required**) |
| `take_profit[1]` | `take_profit_2` (optional) |
| `take_profit[2]` | `take_profit_3` (optional) |

When decision has fewer than 3 targets, TP2/TP3 remain `null`. Signal creation requires at least TP1.

### Stage 10 — Signal Quality Scoring

Separate from decision `confidence`. Weighted quality model — see [Quality Scoring](#quality-scoring) and [CONFIGURATION.md](./CONFIGURATION.md).

### Stage 11 — Signal Assembly

Assemble `TradingSignal`:

- Assign `signal_id` (UUID)
- Set `timestamp_utc` to signal creation time
- Copy `reasons`, `evidence_summary`, `risk_summary`, `warnings` from decision
- Set `expiry_time` from decision `valid_until_utc` or `signal_validity_minutes`
- Set initial `state` to `CREATED`
- Link `decision_id` in metadata

### Stage 12 — Signal Activation

When `auto_activate: true` (default):

- Transition `CREATED` → `ACTIVE`
- Register in active signal registry
- Persist to signal store (when enabled)

When `auto_activate: false`:

- Signal remains `CREATED` until explicit `activate_signal()` call

### Stage 13 — Event Publishing

| Outcome | Events Published |
|---------|------------------|
| Signal created + activated | `SignalCreated`, `SignalActivated` |
| Signal created (not auto-activated) | `SignalCreated` |
| Validation rejection | `SignalRejected` (internal audit; optional) |
| Lifecycle: entry hit | `SignalTriggered` |
| Lifecycle: expiry | `SignalExpired` |
| Lifecycle: cancel | `SignalCancelled` |
| Lifecycle: terminal close | `SignalClosed` |

---

## Primary Output: `TradingSignal`

| Field | Type | Description |
|-------|------|-------------|
| `signal_id` | `str` | UUID v4 |
| `decision_id` | `str` | Source decision UUID |
| `timestamp_utc` | `datetime` | Signal creation timestamp (UTC) |
| `symbol` | `str` | `XAUUSD` / `GOLD.i#` |
| `timeframe` | `str` | Primary timeframe (from config or decision metadata) |
| `direction` | `SignalDirection` | `BUY` or `SELL` |
| `state` | `SignalState` | Current lifecycle state |
| `entry_price` | `Decimal` | Resolved entry price |
| `stop_loss` | `Decimal` | Protective stop |
| `take_profit_1` | `Decimal` | Primary target |
| `take_profit_2` | `Decimal \| None` | Secondary target |
| `take_profit_3` | `Decimal \| None` | Tertiary target |
| `risk_reward` | `Decimal` | Primary target R:R |
| `confidence` | `int` | 0–100 from decision |
| `signal_quality` | `int` | 0–100 composite quality |
| `quality_tier` | `QualityTier` | `high`, `medium`, `low` |
| `reasons` | `list[str]` | Signal rationale (from decision) |
| `evidence_summary` | `list[EvidenceSummaryItem]` | From decision |
| `risk_summary` | `RiskSummary` | From decision |
| `warnings` | `list[str]` | Non-blocking concerns |
| `expiry_time` | `datetime` | Signal validity deadline (UTC) |
| `metadata` | `SignalMetadata` | Pipeline version, config hash, duration_ms |

---

## Quality Scoring

Signal quality is a **configurable weighted score** (0–100) evaluating how well the source decision translates into an actionable institutional signal. The Signal Engine does not re-analyze evidence; it scores **signal readiness** from decision-derived fields.

### Quality Dimensions

| Dimension | Default Weight | Source | Scoring Logic |
|-----------|----------------|--------|---------------|
| Decision confidence | 0.25 | `TradeDecision.confidence` | Normalized 0–100 |
| Decision quality | 0.20 | `TradeDecision.quality_score` | Normalized 0–100 |
| Risk clarity | 0.15 | `risk_summary` rule outcomes | % of rules passed × 100 |
| Entry precision | 0.10 | `EntrySpec` type | `point`=100, `ote`=85, `zone`=70 |
| Target structure | 0.10 | TP count | 1 TP=60, 2 TP=80, 3 TP=100 |
| Evidence completeness | 0.10 | `evidence_summary` | Available engines / 8 × 100 |
| Explainability | 0.10 | `reasons` count | min(count × 20, 100) |

### Formula

```
signal_quality = round(Σ(dimension_weight × dimension_score))
quality_tier = high (≥80) | medium (≥60) | low (<60)
```

### Quality Gate (Optional)

When `quality.min_signal_quality` is configured, signals below threshold are rejected with `LOW_CONFIDENCE` (quality sub-reason in blocking message).

### Adjustments

| Adjustment | Condition | Effect |
|------------|-----------|--------|
| Duplicate proximity penalty | Near-duplicate detected but allowed via config | −10 |
| Stale decision penalty | Decision age > 50% of validity window | −5 to −15 |
| Warning penalty | Each decision warning | −2 (max −10) |
| Multi-TP bonus | 3 take profit targets | +5 |

Final score clamped to [0, 100].

---

## Error Codes

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `SIGNAL_VALIDATION_FAILED` | Input, schema, or session validation failure | No signal; rejection logged |
| `SIGNAL_EXPIRED` | Decision or signal past validity | No signal |
| `LOW_CONFIDENCE` | Confidence or quality below threshold | No signal |
| `DUPLICATE_SIGNAL` | Duplicate active signal detected | No signal |
| `INVALID_DECISION` | Decision state not `BUY`/`SELL` or missing fields | No signal |
| `INVALID_RISK` | Risk re-validation failed | No signal |

All error codes use prefix `MSE_` in implementation (e.g. `MSE_DUPLICATE_SIGNAL`). Architecture documents use the canonical names above.

---

## Lifecycle Operations (Operational — Not Analysis)

The lifecycle manager compares supplied price against pre-computed signal levels. No indicators, patterns, or evidence synthesis occur.

| Operation | Input | Transition |
|-----------|-------|------------|
| `check_entry(current_price)` | Price vs `entry_price` | `ACTIVE` → `TRIGGERED` |
| `check_take_profits(current_price)` | Price vs TP levels | → `TP1_HIT`, `TP2_HIT`, `TP3_HIT` |
| `check_stop_loss(current_price)` | Price vs `stop_loss` | → `STOP_LOSS` → `CLOSED` |
| `apply_break_even()` | Rule trigger | → `BREAK_EVEN` |
| `apply_trailing(current_price)` | Trailing config | → `TRAILING`; update stop |
| `expire_signals(now)` | UTC datetime | `ACTIVE` (untriggered) → `EXPIRED` |
| `cancel_signal(signal_id, reason)` | Manual/system | → `CANCELLED` |
| `close_signal(signal_id, reason)` | Manual | → `CLOSED` |

Price is supplied by the orchestrator or `market.tick.received` handler — the Signal Engine does not subscribe to market data for analysis purposes.

---

## Acceptance Criteria (Sprint 11.2)

- [ ] `MarketSignalEngine.create_signal(decision)` returns `TradingSignal` or `SignalRejection`
- [ ] Only `BUY`/`SELL` decisions produce signals; `NO_TRADE`/`WAIT` produce none
- [ ] Every signal includes full explainability fields from source decision
- [ ] Duplicate detection prevents redundant active signals
- [ ] Signal quality score computed from configurable weights
- [ ] All error codes mapped to explicit rejection reasons
- [ ] Events published per [EVENTS.md](./EVENTS.md)
- [ ] Configuration loaded from YAML with no hardcoded thresholds
- [ ] Decision Engine consumed via public types only
- [ ] No market analysis performed; no upstream engine imports
- [ ] No modifications to Sprints 1–10 code or docs

---

## Sprint 11.2 Implementation Plan

Sprint 11.2 implements this architecture in `backend/engines/market_signal/`. No architecture changes without Product Owner approval.

### Phase 1 — Foundation

| Task | Module | Deliverable |
|------|--------|-------------|
| Config model | `config.py` | `MarketSignalConfig` Pydantic model |
| Schemas | `schemas.py` | `TradingSignal`, `SignalRejection`, enums |
| Exceptions | `exceptions.py` | `MSE_*` error codes |
| Input validator | `validator.py` | `SignalInputValidator` |
| Settings example | `settings.yaml.example` | Documented defaults |

### Phase 2 — Validation Pipeline

| Task | Module | Deliverable |
|------|--------|-------------|
| Decision gate | `decision_gate.py` | `DecisionValidator.validate(...)` |
| Duplicate detection | `duplicate.py` | `DuplicateDetector.detect(...)` |
| Confidence gate | `confidence_gate.py` | `ConfidenceValidator.validate(...)` |
| Session gate | `session_gate.py` | Decision-derived session check |
| Risk gate | `risk_gate.py` | Decision-derived risk check |
| Expiry gate | `expiry_gate.py` | `ExpiryValidator.validate(...)` |

### Phase 3 — Signal Assembly

| Task | Module | Deliverable |
|------|--------|-------------|
| Entry normalizer | `normalizer.py` | `EntryNormalizer.normalize(...)` |
| TP mapper | `normalizer.py` | `TakeProfitMapper.map(...)` |
| Quality scorer | `quality.py` | `SignalQualityScorer.score(...)` |
| Assembler | `assembler.py` | `SignalAssembler.assemble(...)` |

### Phase 4 — Lifecycle & Events

| Task | Module | Deliverable |
|------|--------|-------------|
| Lifecycle manager | `lifecycle.py` | `SignalLifecycleManager` |
| Events | `events.py`, `publisher.py` | Full event lifecycle |
| Signal store | `store.py` | SQLite persistence |
| Engine orchestrator | `engine.py` | `MarketSignalEngine` |
| Package exports | `__init__.py` | Public API surface |

### Phase 5 — Integration

| Task | Deliverable |
|------|-------------|
| Event bus subscription | Subscribe to `decision.signal.published` |
| Config integration | `config/settings.yaml` `market_signal` section |
| Telegram migration path | Document `signal.activated` consumer wiring |
| Dashboard signal panel | Signal lifecycle API for UI |

### Explicitly Out of Sprint 11.2 Scope

- Sprint 11.3 verification and test suite
- Automatic order execution
- Market analysis or upstream engine calls
- Decision Engine modifications
- Telegram Engine full migration (compatibility aliases maintained)

---

## Recommendations (Not Implemented)

| # | Recommendation | Rationale |
|---|----------------|-----------|
| R1 | Migrate Telegram Engine to consume `signal.activated` instead of `decision.signal.published` | Clean separation: Decision decides, Signal converts, Telegram delivers |
| R2 | Add `signal.rejected` audit event for dashboard analytics | Track rejection reasons without polluting signal stream |
| R3 | Add signal replay API for backtesting | Enables historical signal validation |
| R4 | Unify `timeframe` sourcing from decision metadata | Avoid config/decision mismatch |

---

## Related Documents

| Document | Path |
|----------|------|
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |
| Decision Engine | [../market-decision/ARCHITECTURE.md](../market-decision/ARCHITECTURE.md) |
| Constitution | [../CONSTITUTION.md](../CONSTITUTION.md) |
