<#
.SYNOPSIS
    Launch Ko's Labyrinth (Ambroflow engine) — standalone, no Atelier stack needed.

.PARAMETER Update
    Pull the latest code from git before launching.

.PARAMETER Reinstall
    Re-run pip after pulling (use when requirements.txt has new entries).

.EXAMPLE
    .\play.ps1              # just play
    .\play.ps1 -Update      # pull + play
    .\play.ps1 -Update -Reinstall   # pull + sync deps + play
#>
param(
    [switch]$Update,
    [switch]$Reinstall
)

$ErrorActionPreference = "Stop"
$Root   = $PSScriptRoot
$Python = "$Root\.venv\Scripts\python.exe"
$Pip    = "$Root\.venv\Scripts\pip.exe"

# ── Sanity check ──────────────────────────────────────────────────────────────
if (-not (Test-Path $Python)) {
    Write-Host ""
    Write-Host "  No virtual environment found." -ForegroundColor Red
    Write-Host "  Bootstrap it once with:" -ForegroundColor Yellow
    Write-Host "    cd $Root" -ForegroundColor White
    Write-Host "    python -m venv .venv" -ForegroundColor White
    Write-Host "    .venv\Scripts\pip install -r requirements.txt" -ForegroundColor White
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Optional git pull ─────────────────────────────────────────────────────────
if ($Update) {
    Write-Host ""
    Write-Host "  Pulling latest code..." -ForegroundColor Cyan
    try {
        Push-Location $Root
        $result = git pull 2>&1
        Write-Host "  $result" -ForegroundColor Gray
        Pop-Location
    } catch {
        Write-Host "  git pull failed (offline?) — launching existing version." -ForegroundColor Yellow
    }
}

# ── Optional dep sync ─────────────────────────────────────────────────────────
if ($Reinstall) {
    Write-Host "  Syncing dependencies..." -ForegroundColor Cyan
    & $Pip install -r "$Root\requirements.txt" --quiet
}

# ── Status header ─────────────────────────────────────────────────────────────
Write-Host ""
try {
    $branch = git -C $Root rev-parse --abbrev-ref HEAD 2>$null
    $commit = git -C $Root log -1 --format="%h  %s" 2>$null
    Write-Host "  Ko's Labyrinth  --  Ambroflow Engine" -ForegroundColor Green
    Write-Host "  branch: $branch   $commit" -ForegroundColor DarkGray
} catch {
    Write-Host "  Ko's Labyrinth  --  Ambroflow Engine" -ForegroundColor Green
}
Write-Host ""

# ── Launch ────────────────────────────────────────────────────────────────────
$env:PYTHONPATH = $Root
Set-Location $Root
& $Python -m ambroflow