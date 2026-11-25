# Runs the full live evaluation. Asks for the Anthropic API key at a hidden prompt if it is not
# already set; the key is kept only in this process and is not saved or printed.
#   powershell -ExecutionPolicy Bypass -File .\run_live_eval.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $HOME ".venvs\triage\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe" }
if (-not (Test-Path $py)) { $py = "python" }

if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "Get a key at https://console.anthropic.com/settings/keys if you do not have one."
    $secure = Read-Host "Paste your Anthropic API key and press Enter (input is hidden)" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $env:ANTHROPIC_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
if (-not $env:ANTHROPIC_API_KEY) { Write-Host "No key entered; stopping."; exit 1 }

& $py run_eval.py
