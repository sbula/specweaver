# Build the SpecWeaver container image.
# Usage: .\scripts\build-container.ps1 [-Tag "specweaver:latest"]
param(
    [string]$Tag = "specweaver:latest"
)

$ErrorActionPreference = "Stop"

# Detect container engine (prefer podman)
$engine = if (Get-Command podman -ErrorAction SilentlyContinue) { "podman" }
          elseif (Get-Command docker -ErrorAction SilentlyContinue) { "docker" }
          else { throw "Neither podman nor docker found in PATH" }

Write-Host "Building $Tag with $engine ..." -ForegroundColor Cyan
& $engine build -t $Tag -f Containerfile .
Write-Host "Done. Run with:" -ForegroundColor Green
Write-Host "  $engine run --env-file .env -v ./my-project:/projects -p 8000:8000 $Tag"
