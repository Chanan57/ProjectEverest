# Project Everest: System Infrastructure Setup Script

Write-Host "Initializing Project Everest Infrastructure..." -ForegroundColor Cyan

# Check for Python 3.11+
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python 3\.(11|12|13)") {
    Write-Host "Python version check passed: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "Warning: Python 3.11+ is recommended. Found: $pythonVersion" -ForegroundColor Yellow
}

# Check for Node.js
$nodeVersion = node --version 2>&1
if ($nodeVersion -match "v1[8-9]|v2[0-9]") {
    Write-Host "Node.js version check passed: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "Warning: Node.js 18+ is recommended. Found: $nodeVersion" -ForegroundColor Yellow
}

# Create Virtual Environment for Core Engine
Write-Host "Setting up Python Virtual Environment..."
Set-Location -Path "$PSScriptRoot\..\core-engine"
python -m venv venv
Write-Host "Virtual environment created in /core-engine/venv" -ForegroundColor Green

# Install Python dependencies
Write-Host "Installing Python dependencies (this may take a minute)..."
.\venv\Scripts\pip install -r requirements.txt
Write-Host "Python dependencies installed." -ForegroundColor Green

# Install Node dependencies
Write-Host "Installing Node.js dependencies for Data Bridge..."
Set-Location -Path "$PSScriptRoot\..\data-bridge"
npm install

Write-Host "Infrastructure setup complete!" -ForegroundColor Green
