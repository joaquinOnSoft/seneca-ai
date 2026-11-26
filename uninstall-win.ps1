# ============================================================
# SENECA AI - Windows Uninstaller
# ============================================================
#
# Run it from the project folder in a terminal opened with
# "Run as administrator", as the installer:
#
#   .\uninstall-win.ps1            # uninstall
#   .\uninstall-win.ps1 -DryRun    # only print what it would do
#
# 1. Removes the Seneca AI containers, their network and their images,
#    and the installer's leftovers (post-reboot scheduled task, marker file).
# 2. Asks (default: no) whether to delete the data volumes: conversations
#    (MongoDB), long-term memory (Qdrant) and downloaded models (Ollama,
#    Whisper). That information cannot be recovered.
# 3. Asks (default: no) whether to uninstall Docker Desktop.
#
# The project folder, .env and the secrets in docker\ are not deleted:
# delete the folder by hand when you no longer need it. Python and WSL,
# which the installer may have installed, are kept too.
# ============================================================

param(
    [switch]$DryRun
)

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$MarkerFile = Join-Path $ScriptDir "installer-2nd-execution.txt"
$TaskName   = "SenecaAI_Install_PostReboot"
$DataRoot   = "C:\ProgramData\senecaai"
# Host folders created by install-win.ps1 (used when docker compose cannot
# resolve the volume paths, e.g. when Docker is not installed)
$DefaultDataDirs = @("$DataRoot\volumes\ollama", "$DataRoot\volumes\mongo",
                     "$DataRoot\volumes\huggingface", "$DataRoot\volumes\qdrant")

# Docker Compose arguments: base file + Windows override (as the installer)
$ComposeArgs = @("compose", "-f", "docker-compose.yaml", "-f", "docker-compose.windows.yaml")

# ============================================================
# FUNCTION: Run a command, or only print it with -DryRun
# ============================================================
function Invoke-Step {
    param([scriptblock]$Command, [string]$Description)
    if ($DryRun) {
        Write-Host "[dry-run] $Description" -ForegroundColor DarkGray
    } else {
        & $Command
    }
}

# ============================================================
# FUNCTION: Ask a yes/no question. Only y/yes/s/si mean yes;
# anything else, including ENTER, means no.
# ============================================================
function Confirm-Choice {
    param([string]$Question)
    $answer = Read-Host -Prompt "$Question [y/N]"
    return ($answer.Trim().ToLower() -in @("y", "yes", "s", "si", "sí"))
}

# ============================================================
# FUNCTION: Delete a data folder, refusing anything that is not
# a deep absolute path (e.g. C:\a\b)
# ============================================================
function Remove-DataDir {
    param([string]$Dir)
    $full = [System.IO.Path]::GetFullPath($Dir)
    if ($full -notmatch '^[A-Za-z]:\\[^\\]+\\.+') {
        Write-Host "Skipping suspicious path: '$Dir'" -ForegroundColor Yellow
        return
    }
    if (Test-Path $full) {
        Write-Host "Deleting $full" -ForegroundColor Yellow
        Invoke-Step { Remove-Item -Path $full -Recurse -Force } "Remove-Item -Recurse -Force '$full'"
    }
}

# ============================================================
# FUNCTION: Start Docker Desktop if needed and wait until ready.
# Returns $true when the Docker daemon answers.
# ============================================================
function Start-DockerEngine {
    param([int]$TimeoutSeconds = 120)

    & docker info *> $null
    if ($LASTEXITCODE -eq 0) { return $true }

    Write-Host "Starting Docker..." -ForegroundColor Cyan
    $service = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne "Running") {
        Start-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
    }
    $desktopExe = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktopExe) {
        Start-Process -FilePath $desktopExe -WindowStyle Minimized
    }

    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 3
        $elapsed += 3
        Write-Host "  ...still waiting ($elapsed s)" -ForegroundColor DarkGray
    }
    return $false
}

# ============================================================
# 0. Administrative privileges and Docker
# ============================================================
if (-not $DryRun -and -not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "This script must be run as Administrator!"
    Write-Host "Please restart PowerShell as Administrator and try again." -ForegroundColor Red
    Exit 1
}

Set-Location $ScriptDir

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " SENECA AI - UNINSTALL" -ForegroundColor Cyan
if ($DryRun) { Write-Host " (dry run: nothing will be changed)" -ForegroundColor Cyan }
Write-Host "============================================================" -ForegroundColor Cyan

$DockerInstalled = [bool](Get-Command docker -ErrorAction SilentlyContinue)
$DockerOk = $false
if ($DockerInstalled) { $DockerOk = Start-DockerEngine }
if (-not $DockerOk) {
    Write-Host "Docker is not installed or not running: the containers cannot be removed." -ForegroundColor Yellow
}

# ============================================================
# 1. Ask about the data volumes before removing anything
# ============================================================
# Host folders behind the volumes, as docker compose resolves them from .env.
# Only the "device:" and "name:" lines are read, so no other value of .env is printed.
$DataDirs = @()
$ProjectName = (Split-Path $ScriptDir -Leaf).ToLower()
if ($DockerOk) {
    $config = & docker @ComposeArgs config 2>$null
    $DataDirs = @($config | Select-String '^\s*device:\s*(.+)$' | ForEach-Object {
        $_.Matches[0].Groups[1].Value.Trim().Trim('"', "'") -replace '/', '\'
    })
    $nameLine = $config | Select-String '^name:\s*(.+)$' | Select-Object -First 1
    if ($nameLine) { $ProjectName = $nameLine.Matches[0].Groups[1].Value.Trim() }
    Remove-Variable config
}
if ($DataDirs.Count -eq 0) { $DataDirs = $DefaultDataDirs }

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Yellow
Write-Host " WARNING: deleting the volumes deletes ALL the information" -ForegroundColor Yellow
Write-Host " of Seneca AI and it CANNOT be recovered:" -ForegroundColor Yellow
Write-Host "   - conversations and users (MongoDB)" -ForegroundColor Yellow
Write-Host "   - long-term memory (Qdrant)" -ForegroundColor Yellow
Write-Host "   - downloaded AI models (Ollama, Whisper)" -ForegroundColor Yellow
Write-Host " Folders:" -ForegroundColor Yellow
$DataDirs | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
Write-Host "------------------------------------------------------------" -ForegroundColor Yellow
$DeleteVolumes = Confirm-Choice "Delete the volumes and all their data?"
if (-not $DeleteVolumes) {
    Write-Host "The volumes are kept. Installing Seneca AI again will reuse them." -ForegroundColor Green
}

# ============================================================
# 2. Remove the containers, the network, the images and the
#    installer's leftovers
# ============================================================
if ($DockerOk) {
    Write-Host ""
    Write-Host "Removing the Seneca AI containers, network and images..." -ForegroundColor Cyan
    $downArgs = $ComposeArgs + @("down", "--remove-orphans", "--rmi", "all")
    if ($DeleteVolumes) { $downArgs += "--volumes" }
    Invoke-Step { & docker @downArgs } "docker $($downArgs -join ' ')"
}

if ((Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue) -and
    (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    Write-Host "Removing the scheduled task '$TaskName'..." -ForegroundColor Cyan
    Invoke-Step { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false } "Unregister-ScheduledTask $TaskName"
}
if (Test-Path $MarkerFile) {
    Invoke-Step { Remove-Item -Path $MarkerFile -Force } "Remove-Item '$MarkerFile'"
}

if ($DeleteVolumes) {
    $DataDirs | ForEach-Object { Remove-DataDir $_ }
    # Remove the parent folders created by the installer, only if empty
    foreach ($dir in @("$DataRoot\volumes", $DataRoot)) {
        if ((Test-Path $dir) -and -not (Get-ChildItem -Path $dir -Force)) {
            Invoke-Step { Remove-Item -Path $dir -Force } "Remove-Item '$dir'"
        }
    }
}

# ============================================================
# 3. Optionally uninstall Docker Desktop (default: no)
# ============================================================
if ($DockerInstalled) {
    Write-Host ""
    Write-Host "------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host " Docker may be used by other applications on this computer." -ForegroundColor Yellow
    if ($DockerOk) {
        # Containers of other applications (not of the Seneca AI compose project)
        $others = @(& docker ps -a --format '{{.Label "com.docker.compose.project"}}' |
                    Where-Object { $_ -ne $ProjectName }).Count
        Write-Host " Containers of other applications: $others" -ForegroundColor Yellow
    }
    Write-Host " Uninstalling Docker Desktop also deletes the images, containers" -ForegroundColor Yellow
    Write-Host " and volumes of ALL the applications that use it." -ForegroundColor Yellow
    Write-Host "------------------------------------------------------------" -ForegroundColor Yellow
    if (Confirm-Choice "Uninstall Docker Desktop?") {
        Write-Host "Uninstalling Docker Desktop..." -ForegroundColor Cyan
        Invoke-Step { winget uninstall --id Docker.DockerDesktop --exact --accept-source-agreements } `
            "winget uninstall --id Docker.DockerDesktop --exact"
        Write-Host "WSL is kept: other applications may use it." -ForegroundColor DarkGray
    } else {
        Write-Host "Docker is kept." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Seneca AI has been uninstalled." -ForegroundColor Green
Write-Host " The project folder ($ScriptDir), with .env and the secrets" -ForegroundColor Green
Write-Host " in docker\, was kept: delete it by hand if you no longer need it." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
