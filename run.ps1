$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"

$BundledPython = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

function Test-PythonCommand($Command) {
    try {
        & $Command --version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Get-PythonCommand {
    if ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-PythonCommand "py")) {
        return "py"
    }
    if ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-PythonCommand "python")) {
        return "python"
    }
    if ((Test-Path $BundledPython) -and (Test-PythonCommand $BundledPython)) {
        return $BundledPython
    }
    throw "Python tapilmadi. Python 3.11+ install et ve ya Codex runtime yolunu yoxla."
}

$Python = Get-PythonCommand

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" -m jobbot

