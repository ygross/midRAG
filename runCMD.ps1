# Start the Pediatric RAG Flask server
# Reads ANTHROPIC_API_KEY from .env and passes it to the subprocess

$root = $PSScriptRoot

# Load .env
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#][^=]*)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
        }
    }
    Write-Host "Loaded .env"
}

$key = $env:ANTHROPIC_API_KEY
if (-not $key) { Write-Warning "ANTHROPIC_API_KEY not found in .env" }

# Start Flask
$procArgs = @{
    FilePath         = "python"
    ArgumentList     = "app.py"
    WorkingDirectory = $root
    WindowStyle      = "Normal"
    Environment      = @{
        ANTHROPIC_API_KEY = $key
        PYTHONUTF8        = "1"
        PYTHONIOENCODING  = "utf-8"
    }
}
Write-Host "Starting RAG server at http://localhost:5000"
Start-Process @procArgs
