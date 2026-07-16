$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

Write-Host "Building Docker images..."
docker compose build

Write-Host "Docker build complete."
