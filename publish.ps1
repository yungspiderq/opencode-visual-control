# Create a NEW repository on the GitHub account logged into the GitHub CLI.
param([string]$Name = 'opencode-visual-control', [switch]$Private)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  throw 'GitHub CLI (gh) is missing. Install from https://cli.github.com/ then run gh auth login.'
}
& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Sign in first with gh auth login.' }
if (-not (Test-Path '.git')) {
  & git init -b main
  & git add .
  & git commit -m 'Initial Windows visual computer control integration'
}
$visibility = if ($Private) { '--private' } else { '--public' }
& gh repo create $Name $visibility --source . --remote origin --push
if ($LASTEXITCODE -ne 0) { throw 'GitHub did not create or push the repository. Check the message above.' }
Write-Host 'Repository published successfully.' -ForegroundColor Green
& gh repo view --web
