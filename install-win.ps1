# ============================================================
# SENECA AI - Windows Installer
# ============================================================

# Determine script's own directory (for consistent file paths)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$MarkerFile = Join-Path $ScriptDir "installer-2nd-execution.txt"

# ============================================================
# FUNCTION: Start Docker Engine service and wait until ready
# ============================================================
function Start-DockerEngine {
    param (
        [int]$TimeoutSeconds = 120
    )

    Write-Host "--------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Starting Docker Engine service..." -ForegroundColor Cyan

    # Try to start the Docker service directly (works without opening Docker Desktop GUI)
    $dockerService = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue

    if ($dockerService) {
        if ($dockerService.Status -ne "Running") {
            Start-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
            Write-Host "Service 'com.docker.service' start command sent." -ForegroundColor Green
        } else {
            Write-Host "Service 'com.docker.service' is already running." -ForegroundColor Green
        }
    } else {
        # Fallback: launch Docker Desktop minimized (service name may differ on some installs)
        Write-Host "Windows service 'com.docker.service' not found. Launching Docker Desktop as fallback..." -ForegroundColor Yellow
        $dockerDesktopExe = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
        if (Test-Path $dockerDesktopExe) {
            Start-Process -FilePath $dockerDesktopExe -WindowStyle Minimized
        } else {
            Write-Host "ERROR: Docker Desktop executable not found at '$dockerDesktopExe'." -ForegroundColor Red
            Write-Host "Please ensure Docker Desktop is installed and re-run the script." -ForegroundColor Yellow
            Exit 1
        }
    }

    # Wait until the Docker daemon responds to 'docker info'
    Write-Host "Waiting for Docker daemon to become ready (timeout: ${TimeoutSeconds}s)..." -ForegroundColor Cyan
    $elapsed = 0
    $ready   = $false
    while ($elapsed -lt $TimeoutSeconds) {
        $result = & docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 3
        $elapsed += 3
        Write-Host "  ...still waiting ($elapsed s)" -ForegroundColor DarkGray
    }

    if ($ready) {
        Write-Host "Docker daemon is ready." -ForegroundColor Green
    } else {
        Write-Host "ERROR: Docker daemon did not become ready within ${TimeoutSeconds} seconds." -ForegroundColor Red
        Write-Host "Check that Docker Desktop is properly installed and WSL 2 is enabled." -ForegroundColor Yellow
        Exit 1
    }
    Write-Host "--------------------------------------------------------"
}

# ============================================================
# BRANCH: Second execution (post-reboot)
# ============================================================
if (Test-Path $MarkerFile) {

    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " SECOND EXECUTION DETECTED (post-reboot)" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan

    # Remove the marker file
    Remove-Item -Path $MarkerFile -Force
    Write-Host "Marker file removed." -ForegroundColor Green

    # 1. Check for Administrative Privileges
    if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Warning "This script must be run as Administrator!"
        Write-Host "Please restart PowerShell as Administrator and try again." -ForegroundColor Red
        Exit
    }

    # Refresh PATH so docker is visible if it was just installed
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")

    # Verify Docker is now available
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "--------------------------------------------------------" -ForegroundColor Red
        Write-Host "ERROR: Docker is still not available after reboot." -ForegroundColor Red
        Write-Host "Please ensure Docker Desktop has been launched and is running, then re-run this script." -ForegroundColor Yellow
        Write-Host "--------------------------------------------------------"
        Exit 1
    }

    Write-Host "Docker detected: $(docker --version)" -ForegroundColor Green

    # Start Docker Engine service and wait until the daemon is ready
    Start-DockerEngine

    # 7. Builds, (re)creates, starts, and attaches to containers for the service.
    Write-Host "--------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Building and starting containers..." -ForegroundColor Cyan
    Set-Location $ScriptDir
    docker compose up --build

    # 8. Run containers in background
    docker compose up -d

    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " Installation complete!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green

    Exit
}

# ============================================================
# BRANCH: First execution (normal installation)
# ============================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " SENECA AI - FIRST EXECUTION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 0. Script to detect hardware (RAM & GPU) and select the optimal Ollama AI model
& (Join-Path $ScriptDir "select_ollama_model.ps1")

# 1. Check for Administrative Privileges
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "This script must be run as Administrator!"
    Write-Host "Please restart PowerShell as Administrator and try again." -ForegroundColor Red
    Exit
}

# 1.5. Check and install Python if not present (before directory preparation)
Write-Host "--------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Checking Python installation..." -ForegroundColor Cyan

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}

if ($pythonCmd) {
    Write-Host "Python is already installed: $($pythonCmd.Source)" -ForegroundColor Green
    Write-Host "Version: $(& $pythonCmd.Source --version 2>&1)" -ForegroundColor Green
} else {
    Write-Host "Python not found. Installing via Winget..." -ForegroundColor Cyan
    winget install Python.Python.3 --accept-source-agreements --accept-package-agreements

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Winget installation failed. Attempting fallback download..." -ForegroundColor Yellow
        $PythonInstaller = "$env:TEMP\python_installer.exe"
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe" `
                          -OutFile $PythonInstaller -UseBasicParsing
        Start-Process -FilePath $PythonInstaller `
                      -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1" `
                      -Wait
        Remove-Item $PythonInstaller -Force
    }

    # Refresh PATH so python is available in this session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")

    # Verify installation
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) { $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue }

    if ($pythonCmd) {
        Write-Host "Python installed successfully: $(& $pythonCmd.Source --version 2>&1)" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Python installation could not be verified. Continuing anyway..." -ForegroundColor Yellow
    }
}
Write-Host "--------------------------------------------------------"

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
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "--------------------------------------------------------" -ForegroundColor Green
    Write-Host "Docker is already installed on this system."
    Write-Host "Current version: $(docker --version)"
    Write-Host "Skipping Docker installation steps."
    Write-Host "--------------------------------------------------------"

    # Docker already present — start engine and go straight to containers
    Start-DockerEngine
    Write-Host "Building and starting containers..." -ForegroundColor Cyan
    Set-Location $ScriptDir
    docker compose up --build
    docker compose up -d

    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " Installation complete!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Exit
}

Write-Host "Docker not found. Starting installation..." -ForegroundColor Cyan

# 4. Prerequisites (Ensure WSL 2 is enabled, as Docker Desktop requires it)
Write-Host "Ensuring WSL 2 (Windows Subsystem for Linux) is enabled..." -ForegroundColor Cyan
wsl --install --no-distribution

# 5. Install Docker Desktop using Winget
Write-Host "Installing Docker Desktop via Winget..." -ForegroundColor Cyan
winget install Docker.DockerDesktop --accept-source-agreements --accept-package-agreements

# 6. Verification
Write-Host "--------------------------------------------------------" -ForegroundColor Green
Write-Host "Installation command sent successfully!" -ForegroundColor Green
Write-Host "NOTE: Windows requires a system restart to complete the WSL 2 and Docker installation." -ForegroundColor Yellow
Write-Host "Please restart your computer. The installation will resume automatically after login." -ForegroundColor Yellow
Write-Host "--------------------------------------------------------"

# --- Schedule this script to run once after the next reboot ---
$ScriptPath  = $MyInvocation.MyCommand.Definition
$TaskName    = "SenecaAI_Install_PostReboot"
$Action      = New-ScheduledTaskAction `
                   -Execute "powershell.exe" `
                   -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Normal -File `"$ScriptPath`""
$Trigger     = New-ScheduledTaskTrigger -AtLogOn
$Principal   = New-ScheduledTaskPrincipal `
                   -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
                   -RunLevel Highest
$Settings    = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Remove any previous instance of the task
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $Action `
    -Trigger   $Trigger `
    -Principal $Principal `
    -Settings  $Settings `
    -Force | Out-Null

Write-Host "Scheduled task '$TaskName' created — will run once after next login." -ForegroundColor Green

# --- Create the marker file so the next execution knows it's post-reboot ---
New-Item -ItemType File -Path $MarkerFile -Force | Out-Null
Write-Host "Marker file created: $MarkerFile" -ForegroundColor Green

Write-Host "============================================================" -ForegroundColor Yellow
Write-Host " Please RESTART your computer now to complete the setup." -ForegroundColor Yellow
Write-Host " The script will resume automatically after you log in." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow

Exit