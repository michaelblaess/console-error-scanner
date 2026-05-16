#Requires -Version 5.1
# run.ps1 - starts console-error-scanner from source.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Please run .\bootstrap.ps1 first." -ForegroundColor Red
    exit 1
}

& ".venv\Scripts\python.exe" -m console_error_scanner @args
