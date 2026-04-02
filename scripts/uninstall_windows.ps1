$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python wurde nicht gefunden."
}

Push-Location $repoRoot
try {
    $env:PYTHONPATH = "src"
    python -m fbox.install.uninstall_main
}
finally {
    Pop-Location
}
