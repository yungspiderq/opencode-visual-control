# Install MCP + skill for the current Windows user (no elevation needed).
# OpenCode 2 config is the default. Pass -Legacy for OpenCode 1.
param([switch]$Legacy)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw 'This installer is for Windows only.'
}
$source = $PSScriptRoot
$dest = Join-Path $env:LOCALAPPDATA 'OpenCodeVisualControl'
$settings = Join-Path $HOME '.config\opencode'
$skills = Join-Path $settings 'skills\computer-use'
New-Item -ItemType Directory -Force -Path $dest, $skills | Out-Null
foreach ($file in @('actions.py','host.py','bridge.py','mcp_server.py','screens.py','windows.py','requirements.txt')) {
  Copy-Item -Force (Join-Path $source $file) (Join-Path $dest $file)
}
Copy-Item -Force (Join-Path $source '.opencode\skills\computer-use\SKILL.md') (Join-Path $skills 'SKILL.md')

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { throw 'Python 3.10+ was not found in PATH. Install Python first.' }
$python = $pythonCmd.Source
& $python -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ required' }
$venv = Join-Path $dest '.venv'
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
  & $python -m venv $venv
  if ($LASTEXITCODE -ne 0) { throw 'Failed to create virtual environment' }
}
$exe = Join-Path $venv 'Scripts\python.exe'
& $exe -m pip install -r (Join-Path $dest 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Failed to install Python dependencies' }

$configPath = Join-Path $settings 'opencode.json'
if (Test-Path $configPath) {
  Copy-Item -Force $configPath ($configPath + '.visual-control.bak')
  $raw = Get-Content -Raw -Encoding UTF8 $configPath
  $config = ConvertFrom-Json $raw
} else { $config = [pscustomobject]@{} }
if (-not $config.mcp) { $config | Add-Member -NotePropertyName mcp -NotePropertyValue ([pscustomobject]@{}) -Force }
$entry = [pscustomobject]@{ type = 'local'; command = @($exe, (Join-Path $dest 'mcp_server.py')); timeout = 30000 }
if ($Legacy) {
  # OpenCode 1: mcp.<name> (rather than mcp.servers.<name>)
  $entry | Add-Member -NotePropertyName enabled -NotePropertyValue $true
  $config.mcp | Add-Member -NotePropertyName visual_computer -NotePropertyValue $entry -Force
} else {
  if (-not $config.mcp.servers) { $config.mcp | Add-Member -NotePropertyName servers -NotePropertyValue ([pscustomobject]@{}) -Force }
  $config.mcp.servers | Add-Member -NotePropertyName visual_computer -NotePropertyValue $entry -Force
}
$config | ConvertTo-Json -Depth 32 | Set-Content -Encoding UTF8 $configPath
Write-Host ''
Write-Host 'Installed OpenCode Visual Control.' -ForegroundColor Green
Write-Host "Config: $configPath"
Write-Host "Host:   $dest\host.py"
Write-Host 'Start it with .\start-host.ps1 from this repository. Then click RESUME and restart OpenCode.'
