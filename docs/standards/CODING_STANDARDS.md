# Coding Standards

Canon AI Trading coding standards for all implementation sprints.

## General Principles

1. **Maintainability over speed**
2. **Minimal scope** — change only what the sprint requires
3. **Match existing conventions** — read surrounding code before writing
4. **Self-documenting code** — comments only for non-obvious logic
5. **External configuration** — no hardcoded secrets or trading parameters

## Python (Backend)

- Python 3.11+
- Type hints on all public functions and methods
- `ruff` for linting, `mypy` for type checking
- Four-space indentation
- Module docstrings for packages and engines
- Use `pydantic-settings` for configuration
- Async where FastAPI endpoints require it (future sprints)

### Engine Structure

Each engine under `backend/engines/<name>/`:

```
<engine_name>/
├── __init__.py
├── README.md          # Responsibility and I/O contract (future)
└── ...                # Implementation files (future sprints)
```

Engines must expose clean, typed inputs and outputs. No direct imports from sibling engines.

## TypeScript (Frontend)

- Strict TypeScript (`strict: true`)
- Functional React components
- Colocate types in `frontend/src/types/`
- Use `@/` path alias for imports from `src/`

## Testing

- Tests in `tests/unit/` and `tests/integration/`
- Use `pytest` for backend
- One test module per engine (future sprints)
- No tests that assert trivial behavior

## Git

- Meaningful commit messages focused on **why**
- Never commit `.env`, credentials, or database files
- One sprint's work per branch (recommended)

## Prohibited

- Hardcoded API keys, tokens, or passwords
- Cross-engine coupling
- Scope beyond the active sprint
- Architecture or stack changes without PO approval
