# monitor.ps1
# Project Everest — Infrastructure Safety Net
# Monitors Node.js (Data Bridge) and Python (Core Engine) processes.
# Restarts if crashed or using excessive memory, and sends Telegram alerts.

Write-Host "Starting Infrastructure Monitor..." -ForegroundColor Cyan

$nodeScript = "..\data-bridge\index.js"
$pythonScript = "..\core-engine\main.py"

# Memory thresholds in Bytes (e.g., 500MB)
$memLimitBytes = 500 * 1024 * 1024

# Extract Telegram config from .env (fallback to .env.example)
$envFile = "..\.env"
if (-Not (Test-Path $envFile)) {
    Write-Host ".env not found, using .env.example" -ForegroundColor Yellow
    $envFile = "..\.env.example"
}

$envContent = Get-Content $envFile
$botToken = ($envContent -match "^TELEGRAM_BOT_TOKEN=" -replace "^TELEGRAM_BOT_TOKEN=","")
$chatId = ($envContent -match "^TELEGRAM_CHAT_ID=" -replace "^TELEGRAM_CHAT_ID=","")

# Safety net: Remove quotes if they exist
$botToken = $botToken.Replace("`"","").Replace("'","")
$chatId = $chatId.Replace("`"","").Replace("'","")

function Send-TelegramAlert {
    param([string]$message)
    if (-not $botToken -or -not $chatId -or $botToken -match "your_bot_token_here") {
        Write-Host "Telegram credentials missing/default. Skipping alert: $message" -ForegroundColor Yellow
        return
    }

    $url = "https://api.telegram.org/bot$botToken/sendMessage"
    $payload = @{
        chat_id = $chatId
        text = "🚨 *INFRASTRUCTURE ALERT*`n━━━━━━━━━━━━━━━━━━`n$message"
        parse_mode = "Markdown"
    } | ConvertTo-Json

    try {
        Invoke-RestMethod -Uri $url -Method Post -Body $payload -ContentType "application/json" | Out-Null
        Write-Host "Alert sent to Telegram." -ForegroundColor Blue
    } catch {
        Write-Host "Failed to send Telegram alert: $_" -ForegroundColor Red
    }
}

function Start-ServiceProcess {
    param([string]$name, [string]$command)
    Write-Host "Starting $name process..." -ForegroundColor Green
    if ($name -eq "Node.js") {
        Start-Process -FilePath "node" -ArgumentList $command -WindowStyle Minimized
    } else {
        # Using the virtual environment python
        Start-Process -FilePath "..\core-engine\venv\Scripts\python.exe" -ArgumentList $command -WindowStyle Minimized
    }
    Send-TelegramAlert "$name service started/restarted."
}

# Initial startup (Optional: remove if you run them separately)
# For the monitoring script, we assume it's responsible for keeping them alive.
$nodeProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "index.js" }
if (-not $nodeProcs) { Start-ServiceProcess "Node.js" $nodeScript }

$pyProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "main.py" }
if (-not $pyProcs) { Start-ServiceProcess "Python Engine" $pythonScript }

# Monitoring loop
while ($true) {
    Start-Sleep -Seconds 10
    
    # Check Node.js
    $nodeRunning = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "index.js" }
    if (-not $nodeRunning) {
        Write-Host "WARNING: Node.js process missing. Restarting..." -ForegroundColor Red
        Send-TelegramAlert "Data Bridge (Node.js) crashed. Attempting restart."
        Start-ServiceProcess "Node.js" $nodeScript
    } else {
        foreach ($proc in $nodeRunning) {
            if ($proc.WorkingSet64 -gt $memLimitBytes) {
                Write-Host "WARNING: Node.js excessive memory ($($proc.WorkingSet64 / 1MB) MB). Restarting..." -ForegroundColor Red
                Send-TelegramAlert "Data Bridge memory exceeded limit ($($proc.WorkingSet64 / 1MB) MB). Restarting process."
                Stop-Process -Id $proc.Id -Force
                Start-ServiceProcess "Node.js" $nodeScript
            }
        }
    }

    # Check Python
    $pyRunning = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "main.py" }
    if (-not $pyRunning) {
        Write-Host "WARNING: Python Engine process missing. Restarting..." -ForegroundColor Red
        Send-TelegramAlert "Core Engine (Python) crashed. Attempting restart."
        Start-ServiceProcess "Python Engine" $pythonScript
    } else {
        foreach ($proc in $pyRunning) {
            if ($proc.WorkingSet64 -gt $memLimitBytes) {
                Write-Host "WARNING: Python Engine excessive memory ($($proc.WorkingSet64 / 1MB) MB). Restarting..." -ForegroundColor Red
                Send-TelegramAlert "Core Engine memory exceeded limit ($($proc.WorkingSet64 / 1MB) MB). Restarting process."
                Stop-Process -Id $proc.Id -Force
                Start-ServiceProcess "Python Engine" $pythonScript
            }
        }
    }
}
