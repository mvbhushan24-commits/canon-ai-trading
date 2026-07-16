$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

Write-Host "Linting backend (ruff)..."
& .\.venv\Scripts\python.exe -m ruff check backend tests

Write-Host "Type checking backend (mypy)..."
& .\.venv\Scripts\python.exe -m mypy backend

Write-Host "Type checking frontend..."
Set-Location frontend
npm run typecheck

Write-Host "Lint complete."
