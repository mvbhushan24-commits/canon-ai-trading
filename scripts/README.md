# Development Scripts

Cross-platform scripts for local development. Prefer PowerShell on Windows.

| Script | Purpose |
|--------|---------|
| `run-backend.ps1` / `run-backend.sh` | Start FastAPI dev server |
| `run-frontend.ps1` / `run-frontend.sh` | Start Vite dev server |
| `test.ps1` / `test.sh` | Run backend test suite |
| `lint.ps1` | Run ruff, mypy, and frontend typecheck |
| `format.ps1` | Format Python code with ruff |
| `docker-build.ps1` | Build Docker images via docker compose |

## Usage (Windows)

```powershell
.\scripts\run-backend.ps1
.\scripts\run-frontend.ps1
.\scripts\test.ps1
.\scripts\lint.ps1
.\scripts\format.ps1
.\scripts\docker-build.ps1
```
