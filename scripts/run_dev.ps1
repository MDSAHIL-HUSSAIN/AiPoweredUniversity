param(
    [switch]$RealLlm
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Run: python -m venv .venv"
}

if ($RealLlm) {
    $env:MOCK_LLM = "false"
} elseif (-not $env:MOCK_LLM) {
    $env:MOCK_LLM = "true"
}

$api = Start-Job -Name "university-api" -ScriptBlock {
    param($pythonPath, $root)
    Set-Location -LiteralPath $root
    & $pythonPath -m uvicorn main:app --reload --port 8000
} -ArgumentList $python, $projectRoot

$ui = Start-Job -Name "university-ui" -ScriptBlock {
    param($pythonPath, $root)
    Set-Location -LiteralPath $root
    & $pythonPath -m streamlit run streamlit_app.py
} -ArgumentList $python, $projectRoot

Write-Host "FastAPI:   http://localhost:8000/docs"
Write-Host "Streamlit: http://localhost:8501"
Write-Host "Press Ctrl+C to stop both services."

try {
    while ($api.State -eq "Running" -or $ui.State -eq "Running") {
        Receive-Job -Job $api, $ui
        Start-Sleep -Seconds 1
    }
    Receive-Job -Job $api, $ui
} finally {
    Stop-Job -Job $api, $ui -ErrorAction SilentlyContinue
    Remove-Job -Job $api, $ui -Force -ErrorAction SilentlyContinue
}
