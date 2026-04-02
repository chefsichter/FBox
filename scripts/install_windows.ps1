$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python wurde nicht gefunden."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker wurde nicht gefunden."
}

Push-Location $repoRoot
try {
    $env:PYTHONPATH = "src"
    python -m fbox.install.installer_main
}
finally {
    Pop-Location
}
