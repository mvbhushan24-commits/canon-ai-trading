# Canon AI Trading — Constitution

**Highest authority for this project.** If any prompt conflicts with this document, follow the Constitution.

## Governance

| Role | Responsibility |
|------|----------------|
| Product Owner | Product decisions, sprint approval, architecture approval |
| System Architect | Frozen architecture definition |
| Implementation Engineer | Code, tests, docs — no redesign |

## Implementation Rules

1. **One Sprint only** — complete the requested sprint and stop.
2. **One Engine only** — each sprint implements one engine with one responsibility.
3. **Architecture is frozen** — do not change stack, modules, or merge engines.
4. **External configuration** — nothing hardcoded; secrets in environment only.
5. **Clean I/O** — every engine exposes explicit inputs and outputs.
6. **NO TRADE is success** — insufficient evidence must not force a signal.

## Prohibited Actions (Implementation Engineer)

- Change architecture or technology stack
- Add frameworks or remove modules
- Merge engines or invent features
- Change trading logic or introduce paid APIs
- Replace approved libraries
- Expand scope beyond the requested sprint

## Approved Technology Stack

- Python, FastAPI, React + Vite + TypeScript
- SQLite, Lightweight Charts
- XMGlobal via MetaTrader 5
- Telegram Bot API
- Docker, Git

Only free or already-approved technologies may be used.

## Recommendations Process

If improvements are identified:

1. Document as a recommendation
2. Do **not** implement
3. Wait for Product Owner approval

## Version 1.0 Scope

- Analysis and Telegram alerts
- Manual trade execution only
- Maximize signal quality, transparency, explainability, and consistency
