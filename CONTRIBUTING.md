# Contributing to Canon AI Trading

Thank you for contributing. This project follows strict sprint-based development governed by the [Constitution](docs/CONSTITUTION.md).

## Roles

| Role | May contribute |
|------|----------------|
| Product Owner | Sprint scope, priorities, approvals |
| System Architect | Architecture documentation |
| Implementation Engineer | Code within approved sprint scope |

## Development Workflow

1. Confirm the active sprint with the Product Owner
2. Implement **one engine only** per sprint
3. Keep configuration external (`.env`, YAML)
4. Never commit secrets, credentials, or database files
5. Run tests and linting before submitting work

## Local Setup

```powershell
cd "C:\AI Trading"
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cd frontend
npm install
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run-backend.ps1` | Start FastAPI dev server |
| `scripts/run-frontend.ps1` | Start Vite dev server |
| `scripts/test.ps1` | Run backend tests |
| `scripts/lint.ps1` | Run linters |
| `scripts/format.ps1` | Format code |
| `scripts/docker-build.ps1` | Build Docker images |

## Coding Standards

See [CODING_STANDARDS.md](docs/CODING_STANDARDS.md).

## Scope Rules

- Do not expand beyond the active sprint
- Do not change architecture or technology stack without PO approval
- Document recommendations; do not implement unapproved changes

## Pull Request Checklist

- [ ] Sprint scope respected
- [ ] No hardcoded secrets
- [ ] Tests pass (`scripts/test.ps1`)
- [ ] Linting passes (`scripts/lint.ps1`)
- [ ] Documentation updated if structure changed
