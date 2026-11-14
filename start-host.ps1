$ErrorActionPreference = 'Stop'
$homeDir = Join-Path $env:LOCALAPPDATA 'OpenCodeVisualControl'
$python = Join-Path $homeDir '.venv\Scripts\python.exe'
$entry = Join-Path $homeDir 'host.py'
if (-not (Test-Path $python) -or -not (Test-Path $entry)) {
  throw 'Not installed. Run .\install.ps1 first.'
}
Write-Host 'Starting local, visible desktop controller. Click RESUME in the overlay to authorize.'
& $python $entry
