$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

Write-Host "Formatting backend (ruff)..."
& .\.venv\Scripts\python.exe -m ruff format backend tests

Write-Host "Format complete."
