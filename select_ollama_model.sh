#!/bin/bash

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
#   2. OLLAMA_MODEL environment variable              -> kept, no question asked
#   3. otherwise the user picks a model and it is written to .env
# This script is sourced by install-ubuntu.sh, so it uses `return`, not `exit`.
# ==============================================================================

SELECT_ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
SELECT_ENV_EXAMPLE="$(dirname "$SELECT_ENV_FILE")/.env.example"

ENV_FILE_MODEL=""
if [ -f "$SELECT_ENV_FILE" ]; then
    ENV_FILE_MODEL=$(grep -E '^OLLAMA_MODEL=' "$SELECT_ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs)
fi
if [ -n "$ENV_FILE_MODEL" ]; then
    echo "Ollama model taken from .env: OLLAMA_MODEL=${ENV_FILE_MODEL}"
    return 0 2>/dev/null || exit 0
fi
if [ -n "${OLLAMA_MODEL:-}" ]; then
    echo "Ollama model taken from the environment: OLLAMA_MODEL=${OLLAMA_MODEL}"
    return 0 2>/dev/null || exit 0
fi

# 1. Detect System RAM in Gigabytes
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$(( TOTAL_RAM_KB / 1000 / 1000 ))

# Normalize RAM to the table tiers (8, 16, 32, 64). Each threshold is 1 GB
# below its tier, because the reported RAM is a bit less than the installed RAM
# (memory reserved by the firmware, integrated GPU, rounding).
if [ "$TOTAL_RAM_GB" -ge 63 ]; then
    RAM_TIER=64
elif [ "$TOTAL_RAM_GB" -ge 31 ]; then
    RAM_TIER=32
elif [ "$TOTAL_RAM_GB" -ge 15 ]; then
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

# 6. Pick the model based on choice
if [ "$USER_CHOICE" = "A" ]; then
    SELECTED_MODEL=$MODEL_ALT
    echo "Selected Alternative Model."
else
    # Defaults to Recommended if 'R', empty (ENTER), or any other key is pressed
    SELECTED_MODEL=$MODEL_REC
    echo "Selected Recommended Model."
fi

# 7. Write it to .env (created from .env.example if missing)
if [ ! -f "$SELECT_ENV_FILE" ] && [ -f "$SELECT_ENV_EXAMPLE" ]; then
    cp "$SELECT_ENV_EXAMPLE" "$SELECT_ENV_FILE"
    echo "Created $SELECT_ENV_FILE from .env.example"
fi
if grep -qE '^OLLAMA_MODEL=' "$SELECT_ENV_FILE" 2>/dev/null; then
    sed -i "s|^OLLAMA_MODEL=.*|OLLAMA_MODEL=${SELECTED_MODEL}|" "$SELECT_ENV_FILE"
else
    echo "OLLAMA_MODEL=${SELECTED_MODEL}" >> "$SELECT_ENV_FILE"
fi
echo "Written to .env: OLLAMA_MODEL=${SELECTED_MODEL}"
echo "=================================================="