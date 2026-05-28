#!/bin/bash
set -e

MODEL="${OLLAMA_MODEL:-hadad/LFM2.5-1.2B:Q4_K_M}"

echo "================================================"
echo "  Ollama container starting"
echo "  Model : ${MODEL}"
echo "================================================"

# 1. Run ollama in the background
ollama serve &
OLLAMA_PID=$!

# 2. Wait for the API to respond (max. 60 s)
echo "[1/3] Waiting for Ollama API..."
RETRIES=0
until curl -sf http://localhost:11434/api/version > /dev/null 2>&1; do
    sleep 2
    RETRIES=$((RETRIES + 1))
    [ "$RETRIES" -ge 30 ] && { echo "ERROR: Ollama did not start."; exit 1; }
done
echo "[1/3] API ready."

# 3. Download the model only if it is not on the volume
echo "[2/3] Checking model..."
if ollama list 2>/dev/null | grep -qF "${MODEL%%:*}"; then
    echo "[2/3] Model already present, skipping pull."
else
    echo "[2/3] Pulling ${MODEL} — may take several minutes..."
    ollama pull "${MODEL}"
    echo "[2/3] Pull complete."
fi

echo "[3/3] Ready · listening on :11434"
echo "================================================"

# 4. Traer ollama serve al primer plano
wait $OLLAMA_PID
