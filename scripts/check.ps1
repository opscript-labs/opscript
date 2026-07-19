$ErrorActionPreference = "Stop"

$uv = "$HOME\.local\bin\uv.exe"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "web"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Description,
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory
    )

    Write-Host $Description -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            Write-Host "$Description failed" -ForegroundColor Red
            throw "$Description failed"
        }
    }
    finally {
        Pop-Location
    }
}

Invoke-CheckedCommand `
    -Description "Running tests..." `
    -FilePath $uv `
    -Arguments @("run", "pytest", "-q") `
    -WorkingDirectory $repoRoot

Invoke-CheckedCommand `
    -Description "Running lint..." `
    -FilePath $uv `
    -Arguments @("run", "ruff", "check", ".") `
    -WorkingDirectory $repoRoot

Invoke-CheckedCommand `
    -Description "Installing frontend dependencies..." `
    -FilePath "npm" `
    -Arguments @("ci") `
    -WorkingDirectory $frontendRoot

Invoke-CheckedCommand `
    -Description "Running frontend tests..." `
    -FilePath "npm" `
    -Arguments @("run", "test:run") `
    -WorkingDirectory $frontendRoot

Invoke-CheckedCommand `
    -Description "Running frontend type check..." `
    -FilePath "npm" `
    -Arguments @("run", "typecheck") `
    -WorkingDirectory $frontendRoot

Invoke-CheckedCommand `
    -Description "Building frontend..." `
    -FilePath "npm" `
    -Arguments @("run", "build") `
    -WorkingDirectory $frontendRoot

Write-Host "All checks passed!" -ForegroundColor Green
