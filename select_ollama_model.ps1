# ==============================================================================
# Script to detect hardware (RAM & GPU) and select the optimal Ollama AI model
# ==============================================================================
#
# |Ram	    | GPU	  | Modelo IA                   |
# | ------- | ------- | --------------------------- |
# | 8 Gb	| No	  | qwen2.5:1.5b o llama3.2:1b  |
# | 8 Gb	| Yes	  | qwen2.5:3b o qwen2.5:1.5b   |
# |16 Gb	| No	  | qwen2.5:3b o llama3.2:3b    |
# |16 Gb	| Yes	  | mistral:7b o llama3:8b      |
# |32 Gb	| No	  | llama3:8b o gemma2:9b       |
# |32 Gb	| Yes	  | qwen2.5:14b o phi3:14b      |
# |64 Gb	| No	  | llama3:8b o command-r:35b   |
# |64 Gb	| Yes	  | mixtral:8x7b o llama3.1:70b |
#
# The chosen model is written to OLLAMA_MODEL in .env, which docker compose
# reads. Order of precedence:
#   1. OLLAMA_MODEL already set (non-empty) in .env   -> kept, no question asked
#   2. OLLAMA_MODEL environment variable              -> kept, no question asked
#   3. otherwise the user picks a model and it is written to .env
# ==============================================================================

$SelectEnvFile = Join-Path $PSScriptRoot ".env"
$SelectEnvExample = Join-Path $PSScriptRoot ".env.example"

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
    return
}

# 1. Detect System RAM in Gigabytes
$TotalRamByte = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
$TotalRamGB = [Math]::Floor($TotalRamByte / 1GB)

# Normalize RAM to match the table thresholds (8, 16, 32, 64)
if ($TotalRamGB -ge 64) {
    $RamTier = 64
} elseif ($TotalRamGB -ge 32) {
    $RamTier = 32
} elseif ($TotalRamGB -ge 16) {
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

# 7. Write it to .env (created from .env.example if missing). Stored in .env,
#    so it survives the reboot between the two installer executions.
if (-not (Test-Path $SelectEnvFile) -and (Test-Path $SelectEnvExample)) {
    Copy-Item $SelectEnvExample $SelectEnvFile
    Write-Host "Created $SelectEnvFile from .env.example"
}
$lines = @()
if (Test-Path $SelectEnvFile) { $lines = @(Get-Content $SelectEnvFile) }
$found = $false
$lines = @($lines | ForEach-Object {
    if ($_ -match '^OLLAMA_MODEL=') { $found = $true; "OLLAMA_MODEL=$SelectedModel" } else { $_ }
})
if (-not $found) { $lines += "OLLAMA_MODEL=$SelectedModel" }
# UTF-8 without BOM
[System.IO.File]::WriteAllLines($SelectEnvFile, [string[]]$lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Written to .env: OLLAMA_MODEL=$SelectedModel"
Write-Host "=================================================="