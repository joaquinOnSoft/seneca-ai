# ==============================================================================
# Script to detect hardware (RAM & GPU) and select the optimal Ollama AI model
# ==============================================================================
#
# | Detected RAM | Tier  | GPU | AI model                     |
# | ------------ | ----- | --- | ---------------------------- |
# | < 15 GB      | 8 GB  | No  | qwen2.5:1.5b or llama3.2:1b  |
# | < 15 GB      | 8 GB  | Yes | qwen2.5:3b or qwen2.5:1.5b   |
# | 15 - 30 GB   | 16 GB | No  | qwen2.5:3b or llama3.2:3b    |
# | 15 - 30 GB   | 16 GB | Yes | mistral:7b or llama3:8b      |
# | 31 - 62 GB   | 32 GB | No  | llama3:8b or gemma2:9b       |
# | 31 - 62 GB   | 32 GB | Yes | qwen2.5:14b or phi3:14b      |
# | >= 63 GB     | 64 GB | No  | llama3:8b or command-r:35b   |
# | >= 63 GB     | 64 GB | Yes | mixtral:8x7b or llama3.1:70b |
#
# Each tier starts 1 GB below its size, because the OS reports a bit less RAM
# than the installed RAM.
#
# The chosen model is written to OLLAMA_MODEL in .env, which docker compose
# reads. Order of precedence:
#   1. OLLAMA_MODEL already set (non-empty) in .env   -> kept, no question asked
#   2. OLLAMA_MODEL environment variable              -> written to .env, no question asked
#   3. otherwise the user picks a model and it is written to .env
# The model is always stored in .env, so it survives the reboot between the
# two installer executions (the second one starts the containers).
# ==============================================================================

$SelectEnvFile = Join-Path $PSScriptRoot ".env"
$SelectEnvExample = Join-Path $PSScriptRoot ".env.example"

# Write OLLAMA_MODEL=<Model> to .env (created from .env.example if missing)
function Write-OllamaModelToEnv([string]$Model) {
    if (-not (Test-Path $SelectEnvFile) -and (Test-Path $SelectEnvExample)) {
        Copy-Item $SelectEnvExample $SelectEnvFile
        Write-Host "Created $SelectEnvFile from .env.example"
    }
    $lines = @()
    if (Test-Path $SelectEnvFile) { $lines = @(Get-Content $SelectEnvFile) }
    $found = $false
    $lines = @($lines | ForEach-Object {
        if ($_ -match '^OLLAMA_MODEL=') { $found = $true; "OLLAMA_MODEL=$Model" } else { $_ }
    })
    if (-not $found) { $lines += "OLLAMA_MODEL=$Model" }
    # UTF-8 without BOM
    [System.IO.File]::WriteAllLines($SelectEnvFile, [string[]]$lines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Written to .env: OLLAMA_MODEL=$Model"
}

$EnvFileModel = ""
if (Test-Path $SelectEnvFile) {
    $line = Get-Content $SelectEnvFile | Where-Object { $_ -match '^OLLAMA_MODEL=' } | Select-Object -Last 1
    if ($line) { $EnvFileModel = ($line -replace '^OLLAMA_MODEL=', '').Trim().Trim('"').Trim("'") }
}
if ($EnvFileModel) {
    Write-Host "Ollama model taken from .env: OLLAMA_MODEL=$EnvFileModel"
    return
}
if ($env:OLLAMA_MODEL) {
    Write-Host "Ollama model taken from the environment: OLLAMA_MODEL=$env:OLLAMA_MODEL"
    Write-OllamaModelToEnv $env:OLLAMA_MODEL
    return
}

# 1. Detect System RAM in Gigabytes
$TotalRamByte = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
$TotalRamGB = [Math]::Floor($TotalRamByte / 1GB)

# Normalize RAM to the table tiers (8, 16, 32, 64). Each threshold is 1 GB
# below its tier, because the reported RAM is a bit less than the installed RAM
# (memory reserved by the firmware, integrated GPU, rounding).
if ($TotalRamGB -ge 63) {
    $RamTier = 64
} elseif ($TotalRamGB -ge 31) {
    $RamTier = 32
} elseif ($TotalRamGB -ge 15) {
    $RamTier = 16
} else {
    # Defaulting to 8GB tier as the minimum baseline
    $RamTier = 8
}

# 2. Detect GPU presence (Looking for NVIDIA, AMD, or Intel Arc dedicated controllers)
# Note: Filters out basic integrated graphics by checking for dedicated/3D controllers
$GpuCheck = Get-CimInstance Win32_VideoController | Where-Object {
    $_.Name -match "NVIDIA" -or $_.Name -match "AMD" -or $_.Name -match "Radeon" -or $_.Name -match "Arc"
}

if ($GpuCheck) {
    $GpuPresent = "SI"
} else {
    $GpuPresent = "No"
}

# 3. Determine models based on hardware matrix
$ModelRec = ""
$ModelAlt = ""

if ($RamTier -eq 8) {
    if ($GpuPresent -eq "No") {
        $ModelRec = "qwen2.5:1.5b"
        $ModelAlt = "llama3.2:1b"
    } else {
        $ModelRec = "qwen2.5:3b"
        $ModelAlt = "qwen2.5:1.5b"
    }
} elseif ($RamTier -eq 16) {
    if ($GpuPresent -eq "No") {
        $ModelRec = "qwen2.5:3b"
        $ModelAlt = "llama3.2:3b"
    } else {
        $ModelRec = "mistral:7b"
        $ModelAlt = "llama3:8b"
    }
} elseif ($RamTier -eq 32) {
    if ($GpuPresent -eq "No") {
        $ModelRec = "llama3:8b"
        $ModelAlt = "gemma2:9b"
    } else {
        $ModelRec = "qwen2.5:14b"
        $ModelAlt = "phi3:14b"
    }
} elseif ($RamTier -eq 64) {
    if ($GpuPresent -eq "No") {
        $ModelRec = "llama3:8b"
        $ModelAlt = "command-r:35b"
    } else {
        $ModelRec = "mixtral:8x7b"
        $ModelAlt = "llama3.1:70b"
    }
}

# 4. Display hardware status and recommendations to the user
Write-Host "=================================================="
Write-Host "      HARDWARE DETECTION & RECOMMENDATION"
Write-Host "=================================================="
Write-Host "Detected RAM : ${TotalRamGB} GB (Mapped to ${RamTier} GB tier)"
Write-Host "GPU Present  : ${GpuPresent}"
Write-Host "--------------------------------------------------"
Write-Host "Recommended Model: ${ModelRec}"
Write-Host "Alternative Model: ${ModelAlt}"
Write-Host "=================================================="
Write-Host ""

# 5. Prompt user for selection
$PromptMessage = "Do you want to install the recommended model (${ModelRec}) [R] or the alternative (${ModelAlt}) [A]? (Default: R): "
$UserChoice = Read-Host -Prompt $PromptMessage

# Convert input to uppercase
$UserChoice = $UserChoice.ToUpper()

# 6. Pick the model based on choice
if ($UserChoice -eq "A") {
    $SelectedModel = $ModelAlt
    Write-Host "Selected Alternative Model."
} else {
    # Defaults to Recommended if 'R', empty (ENTER), or any other key is pressed
    $SelectedModel = $ModelRec
    Write-Host "Selected Recommended Model."
}

# 7. Write it to .env
Write-OllamaModelToEnv $SelectedModel
Write-Host "=================================================="