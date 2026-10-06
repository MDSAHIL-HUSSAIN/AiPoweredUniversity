param(
    [switch]$RealLlm,
    [switch]$RealRetrieval
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

# Lightweight mode still uses Member 2's complete ingestion/retrieval interfaces,
# with in-memory vectors and deterministic embeddings for quick local startup.
if ($RealRetrieval) {
    $env:CHROMA_DISABLED = "false"
} elseif (-not $env:CHROMA_DISABLED) {
    $env:CHROMA_DISABLED = "true"
}

$api = Start-Job -Name "university-api" -ScriptBlock {
    param($pythonPath, $root)
    Set-Location -LiteralPath $root
    & $pythonPath -m uvicorn main:app --reload --port 8000
} -ArgumentList $python, $projectRoot

$ui = Start-Job -Name "university-ui" -ScriptBlock {
    param($pythonPath, $root)
    Set-Location -LiteralPath $root
    & $pythonPath -m streamlit run streamlit_app.py `
        --server.headless true `
        --browser.gatherUsageStats false
} -ArgumentList $python, $projectRoot

Write-Host "FastAPI:   http://localhost:8000/docs"
Write-Host "Streamlit: http://localhost:8501"
Write-Host "Press Ctrl+C to stop both services."

try {
    while ($api.State -eq "Running" -or $ui.State -eq "Running") {
        Receive-Job -Job $api, $ui -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    Receive-Job -Job $api, $ui -ErrorAction Continue
} finally {
    Stop-Job -Job $api, $ui -ErrorAction SilentlyContinue
    Remove-Job -Job $api, $ui -Force -ErrorAction SilentlyContinue
}
