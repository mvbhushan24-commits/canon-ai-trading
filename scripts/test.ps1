$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt
}

& .\.venv\Scripts\python.exe -m pytest tests/ -v "$args"
