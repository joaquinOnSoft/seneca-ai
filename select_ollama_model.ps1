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
# ==============================================================================

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

# 6. Assign the environment variable based on choice
if ($UserChoice -eq "A") {
    $env:OLLAMA_AI_MODEL = $ModelAlt
    Write-Host "Selected Alternative Model."
} else {
    # Defaults to Recommended if 'R', empty (ENTER), or any other key is pressed
    $env:OLLAMA_AI_MODEL = $ModelRec
    Write-Host "Selected Recommended Model."
}

# 7. Confirm the exported environment variable
Write-Host "Environment variable set: OLLAMA_AI_MODEL=$env:OLLAMA_AI_MODEL"
Write-Host "=================================================="