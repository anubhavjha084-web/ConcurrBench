# ---------------------------------------------------------------
# One-click launch for ConcurrencyBugBench (Windows PowerShell)
# ---------------------------------------------------------------
Write-Host "Building and starting the benchmark container..." -ForegroundColor Cyan
docker compose up --build
