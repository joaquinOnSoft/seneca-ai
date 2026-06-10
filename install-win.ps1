# 0. Script to detect hardware (RAM & GPU) and select the optimal Ollama AI model
& .\select_ollama_model.ps1

# 1. Check for Administrative Privileges
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "This script must be run as Administrator!"
    Write-Host "Please restart PowerShell as Administrator and try again." -ForegroundColor Red
    Exit
}

# 2. Directory Preparation
# In Windows, a common equivalent for shared app data/volumes is C:\ProgramData
$OllamaPath = "C:\ProgramData\senecaai\volumes\ollama"

Write-Host "Preparing directories for Ollama..." -ForegroundColor Cyan
if (-not (Test-Path $OllamaPath)) {
    New-Item -ItemType Directory -Path $OllamaPath -Force | Out-Null
    Write-Host "Created directory: $OllamaPath" -ForegroundColor Green
} else {
    Write-Host "Directory already exists: $OllamaPath" -ForegroundColor Yellow
}

# 3. Check if Docker is already installed
# We check both the command and the typical Docker Desktop installation
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "--------------------------------------------------------" -ForegroundColor Green
    Write-Host "Docker is already installed on this system."
    Write-Host "Current version: $(docker --version)"
    Write-Host "Skipping Docker installation steps."
    Write-Host "--------------------------------------------------------"
} else {
    Write-Host "Docker not found. Starting installation..." -ForegroundColor Cyan

    # 4. Prerequisites (Ensure WSL 2 is enabled, as Docker Desktop requires it)
    Write-Host "Ensuring WSL 2 (Windows Subsystem for Linux) is enabled..." -ForegroundColor Cyan
    wsl --install --no-distribution

    # 5. Install Docker Desktop using Winget
    Write-Host "Installing Docker Desktop via Winget..." -ForegroundColor Cyan
    # --accept-source-agreements and --accept-package-agreements make it silent/automated
    winget install Docker.DockerDesktop --accept-source-agreements --accept-package-agreements

    # 6. Verification
    Write-Host "--------------------------------------------------------" -ForegroundColor Green
    Write-Host "Installation command sent successfully!" -ForegroundColor Green
    Write-Host "NOTE: Windows requires a system restart to complete the WSL 2 and Docker installation." -ForegroundColor Yellow
    Write-Host "Please restart your computer, then launch 'Docker Desktop' from the Start Menu." -ForegroundColor Yellow
    Write-Host "--------------------------------------------------------"
}

# 7. Builds, (re)creates, starts, and attaches to containers for the service.
docker compose up --build

# 8. Run containers in background
docker compose up -d