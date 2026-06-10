#!/bin/bash

# ==============================================================================
# Script to detect hardware (RAM & GPU) and select the optimal Ollama AI model
# ==============================================================================
#
# |Ram	  | GPU	  | Modelo IA                   |
# | ----- | ----- | --------------------------- |
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
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$(( TOTAL_RAM_KB / 1000 / 1000 ))

# Normalize RAM to match the table thresholds (8, 16, 32, 64)
if [ "$TOTAL_RAM_GB" -ge 64 ]; then
    RAM_TIER=64
elif [ "$TOTAL_RAM_GB" -ge 32 ]; then
    RAM_TIER=32
elif [ "$TOTAL_RAM_GB" -ge 16 ]; then
    RAM_TIER=16
else
    # Defaulting to 8GB tier as the minimum baseline
    RAM_TIER=8
fi

# 2. Detect GPU presence (Looking for NVIDIA or AMD controllers)
if lspci | grep -E -i "(nvidia|vga|3d)" | grep -E -i "(nvidia|amd|advanced micro devices)" > /dev/null 2>&1; then
    GPU_PRESENT="SI"
else
    GPU_PRESENT="No"
fi

# 3. Determine models based on hardware matrix
MODEL_REC=""
MODEL_ALT=""

if [ "$RAM_TIER" -eq 8 ]; then
    if [ "$GPU_PRESENT" = "No" ]; then
        MODEL_REC="qwen2.5:1.5b"
        MODEL_ALT="llama3.2:1b"
    else
        MODEL_REC="qwen2.5:3b"
        MODEL_ALT="qwen2.5:1.5b"
    fi
elif [ "$RAM_TIER" -eq 16 ]; then
    if [ "$GPU_PRESENT" = "No" ]; then
        MODEL_REC="qwen2.5:3b"
        MODEL_ALT="llama3.2:3b"
    else
        MODEL_REC="mistral:7b"
        MODEL_ALT="llama3:8b"
    fi
elif [ "$RAM_TIER" -eq 32 ]; then
    if [ "$GPU_PRESENT" = "No" ]; then
        MODEL_REC="llama3:8b"
        MODEL_ALT="gemma2:9b"
    else
        MODEL_REC="qwen2.5:14b"
        MODEL_ALT="phi3:14b"
    fi
elif [ "$RAM_TIER" -eq 64 ]; then
    if [ "$GPU_PRESENT" = "No" ]; then
        MODEL_REC="llama3:8b"
        MODEL_ALT="command-r:35b"
    else
        MODEL_REC="mixtral:8x7b"
        MODEL_ALT="llama3.1:70b"
    fi
fi

# 4. Display hardware status and recommendations to the user
echo "=================================================="
echo "      HARDWARE DETECTION & RECOMMENDATION"
echo "=================================================="
echo "Detected RAM : ${TOTAL_RAM_GB} GB (Mapped to ${RAM_TIER} GB tier)"
echo "GPU Present  : ${GPU_PRESENT}"
echo "--------------------------------------------------"
echo "Recommended Model: ${MODEL_REC}"
echo "Alternative Model: ${MODEL_ALT}"
echo "=================================================="
echo ""

# 5. Prompt user for selection
# shellcheck disable=SC2162
read -p "Do you want to install the recommended model (${MODEL_REC}) [R] or the alternative (${MODEL_ALT}) [A]? (Default: R): " USER_CHOICE

# Convert input to uppercase
USER_CHOICE=$(echo "$USER_CHOICE" | tr '[:lower:]' '[:upper:]')

# 6. Assign the environment variable based on choice
if [ "$USER_CHOICE" = "A" ]; then
    export OLLAMA_AI_MODEL=$MODEL_ALT
    echo "Selected Alternative Model."
else
    # Defaults to Recommended if 'R', empty (ENTER), or any other key is pressed
    export OLLAMA_AI_MODEL=$MODEL_REC
    echo "Selected Recommended Model."
fi

# 7. Confirm the exported environment variable
echo "Environment variable set: OLLAMA_AI_MODEL=${OLLAMA_AI_MODEL}"
echo "=================================================="