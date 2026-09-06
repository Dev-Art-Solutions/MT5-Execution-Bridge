#Requires -Version 5.1
<#
.SYNOPSIS
    Checks repository hygiene and default-safe configuration.
.DESCRIPTION
    Does NOT replace actual runtime testing (docs/TEST_PLAN.md). This only
    checks static repository state: required files exist, no private or
    secret files are tracked by Git, and the shipped defaults are safe
    (dry-run, live execution disabled, localhost-only).
#>

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$failures = @()

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        $script:failures += $Message
    }
}

$requiredFiles = @(
    "pyproject.toml", "README.md", "PORTFOLIO_CASE_STUDY.md", "CHANGELOG.md",
    "LICENSE", ".env.example", ".gitignore",
    "app/main.py", "app/config.py",
    "client/bridge_client.py",
    "docs/ARCHITECTURE.md", "docs/SECURITY.md"
)
foreach ($file in $requiredFiles) {
    Assert-True (Test-Path $file) "Missing required file: $file"
}

$trackedFiles = git ls-files

Assert-True (-not ($trackedFiles -contains ".env")) ".env must not be tracked by Git"

$planCandidates = $trackedFiles | Where-Object { $_ -match "CLAUDE.*PLAN\.md$" }
Assert-True ($planCandidates.Count -eq 0) "Private implementation plan must not be tracked by Git: $($planCandidates -join ', ')"

Assert-True (-not ($trackedFiles | Where-Object { $_ -like "*.private.md" })) "*.private.md files must not be tracked by Git"

if (Test-Path ".env.example") {
    $envExample = Get-Content ".env.example" -Raw
    Assert-True ($envExample -match "DRY_RUN=true") ".env.example must default to DRY_RUN=true"
    Assert-True ($envExample -match "LIVE_EXECUTION_ENABLED=false") ".env.example must default to LIVE_EXECUTION_ENABLED=false"
    Assert-True ($envExample -match "HOST=127\.0\.0\.1") ".env.example must default to HOST=127.0.0.1"
    Assert-True ($envExample -match "ALLOW_REMOTE_BINDING=false") ".env.example must default to ALLOW_REMOTE_BINDING=false"
} else {
    $failures += ".env.example not found; cannot verify safe defaults"
}

# Matched per line (not -Raw) so `\s*` can never cross a newline into an
# unrelated later token -- that previously produced false positives like
# "MT5_PASSWORD=" (empty placeholder) matching across blank lines into the
# next variable, and `password=self._settings.mt5_password` (a kwarg fed
# from config, not a literal) matching because a `=` and letters followed
# it somewhere on the line. Only an actual quoted literal counts as a hit.
$secretPatterns = @(
    "(password|passwd|pwd)\s*[:=]\s*[`"'][^`"'\s]{4,}[`"']",
    "BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY",
    "api[_-]?key\s*[:=]\s*[`"'][^`"'\s]{10,}[`"']"
)
foreach ($file in $trackedFiles) {
    if ($file -eq "scripts/validate-repository.ps1") { continue }
    if (-not (Test-Path $file -PathType Leaf)) { continue }
    if ($file -match "\.(png|jpg|jpeg|gif|ico|db)$") { continue }
    $lines = Get-Content $file -ErrorAction SilentlyContinue
    if (-not $lines) { continue }
    foreach ($pattern in $secretPatterns) {
        $hit = $lines | Select-String -Pattern $pattern | Select-Object -First 1
        if ($hit) {
            $failures += "Possible secret pattern '$pattern' found in tracked file: ${file}:$($hit.LineNumber)"
        }
    }
}

if ($failures.Count -eq 0) {
    Write-Host "Repository validation passed." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Repository validation FAILED:" -ForegroundColor Red
    foreach ($f in $failures) { Write-Host " - $f" -ForegroundColor Red }
    exit 1
}
