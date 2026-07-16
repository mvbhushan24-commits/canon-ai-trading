# Learning Engine — Interface Contract

**Engine ID:** `learning`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD  
**Version Scope:** Post v1.0 — contract defined for future sprint planning

---

## 1. Purpose

Analyze historical decision outcomes and backtest results to identify patterns in signal quality, engine confluence effectiveness, and NO TRADE accuracy — producing recommendations for configuration tuning only.

---

## 2. Responsibilities

- Consume historical decisions and backtest results
- Analyze which engine combinations produced highest-quality signals
- Identify conditions where NO TRADE decisions were correct
- Produce configuration tuning recommendations
- Generate learning reports with evidence
- Never auto-modify engine logic or configuration without Product Owner approval

**Out of scope:** Auto-modifying trading logic, auto-deploying config changes, live signal generation, model training with paid APIs.

**Constitutional constraint:** Recommendations only — no autonomous product decisions.

**Note:** This engine is outside v1.0 scope. Contract is defined for architectural completeness only.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `decisions` | `TradingDecision[]` | Yes | Historical decisions from SQLite |
| `backtest_results` | `BacktestResult[]` | No | From Backtesting Engine |
| `delivery_results` | `TelegramDeliveryResult[]` | No | Delivery log for correlation |
| `from_utc` | `datetime` | Yes | Analysis period start |
| `to_utc` | `datetime` | Yes | Analysis period end |
| `learning_scope` | `enum` | No | `decisions`, `backtest`, `combined` |

---

## 4. Outputs

### LearningReport

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | `string` | Unique report identifier |
| `from_utc` | `datetime` | Analysis period start |
| `to_utc` | `datetime` | Analysis period end |
| `total_decisions_analyzed` | `integer` | Decision count |
| `signal_accuracy` | `decimal` | Percentage of correct signals |
| `no_trade_accuracy` | `decimal` | Percentage of correct NO TRADE calls |
| `engine_effectiveness` | `EngineEffectiveness[]` | Per-engine contribution analysis |
| `confluence_insights` | `ConfluenceInsight[]` | Confluence pattern findings |
| `recommendations` | `Recommendation[]` | Config tuning recommendations |
| `evidence` | `string[]` | Human-readable findings |
| `generated_at_utc` | `datetime` | Report generation time |

### EngineEffectiveness

| Field | Type | Description |
|-------|------|-------------|
| `engine_id` | `string` | Engine identifier |
| `contribution_score` | `decimal` | 0.0–1.0 effectiveness score |
| `true_positive_rate` | `decimal` | Correct bias when signal issued |
| `sample_size` | `integer` | Decisions where engine contributed |

### ConfluenceInsight

| Field | Type | Description |
|-------|------|-------------|
| `pattern` | `string` | Description of confluence pattern |
| `occurrence_count` | `integer` | Times pattern occurred |
| `success_rate` | `decimal` | Pattern success rate |
| `recommended_action` | `string` | Suggested config adjustment |

### Recommendation

| Field | Type | Description |
|-------|------|-------------|
| `recommendation_id` | `string` | Unique recommendation ID |
| `type` | `enum` | `config_change`, `engine_weight`, `threshold_adjustment` |
| `target_key` | `string` | Configuration key to adjust |
| `current_value` | `string` | Current configured value |
| `suggested_value` | `string` | Suggested new value |
| `rationale` | `string` | Evidence-based reasoning |
| `confidence` | `decimal` | 0.0–1.0 recommendation confidence |
| `requires_po_approval` | `boolean` | Always `true` |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| SQLite | Internal | Historical decisions and results |
| Decision Engine | Upstream | Historical decision schema |
| Backtesting Engine | Upstream | Optional backtest results |
| Telegram Engine | Upstream | Optional delivery log |
| Configuration | Internal | Learning parameters |
| Event Bus | Internal | Publish/consume events |

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `learning.report.generated` | Report complete | `LearningReport` |
| `learning.recommendation.created` | New recommendation | `Recommendation` |
| `learning.analysis.started` | Analysis run begins | Run configuration |
| `learning.analysis.failed` | Analysis failed | Error details |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `backtest.completed` | Backtesting Engine | Include backtest in analysis |
| `decision.completed` | Decision Engine | Accumulate decision history |
| `system.learning.requested` | Orchestrator / API | Start learning analysis |
| `system.config.updated` | Config service | Reload learning parameters |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `LEARNING_MIN_DECISIONS` | YAML | `50` | Minimum decisions for analysis |
| `LEARNING_ANALYSIS_PERIOD_DAYS` | YAML | `30` | Default analysis window |
| `LEARNING_AUTO_APPLY` | YAML | `false` | Must always be `false` without PO approval |
| `LEARNING_ENABLED` | YAML | `false` | Engine toggle |

`LEARNING_AUTO_APPLY` must never be set to `true` without explicit Product Owner approval and Constitutional amendment.

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `LE_INSUFFICIENT_DATA` | Fewer decisions than minimum | Fail run; emit error |
| `LE_PERIOD_INVALID` | Invalid analysis period | Reject input; emit error |
| `LE_AUTO_APPLY_BLOCKED` | Auto-apply attempted | Block; emit error; require PO approval |
| `LE_REPORT_GENERATION_FAILED` | Report generation error | Emit failed event |

---

## 10. Success Criteria

- Every recommendation includes `requires_po_approval: true`
- No configuration is auto-modified — recommendations only
- NO TRADE accuracy is measured and reported as a positive metric
- Engine effectiveness scores are evidence-backed
- Learning reports are consumable by Dashboard (future sprint)
- No paid APIs or external ML services are used without PO approval
- Contract is complete for future implementation planning

---

**Implementation sprint:** Post v1.0 — TBD by Product Owner
