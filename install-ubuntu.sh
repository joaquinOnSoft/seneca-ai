#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# 0. Script to detect hardware (RAM & GPU) and select the optimal Ollama AI model
source ./select_ollama_model.sh

# Identify the actual user (in case the script is run with sudo)
REAL_USER=${SUDO_USER:-$USER}

# 1. Directory Preparation (This runs regardless of Docker installation)
echo "Preparing directories for Ollama, MongoDB, Qdrant and the Hugging Face cache..."

sudo mkdir -p /opt/senecaai/volumes/ollama
sudo mkdir -p /opt/senecaai/volumes/mongo
sudo mkdir -p /opt/senecaai/volumes/huggingface
sudo mkdir -p /opt/senecaai/volumes/qdrant
sudo chown -R "$REAL_USER":"$REAL_USER" /opt/senecaai

# 2. Check if Docker is already installed
if command -v docker &> /dev/null; then
    echo "--------------------------------------------------------"
    echo "Docker is already installed on this system."
    echo "Current version: $(docker --version)"
    echo "Skipping Docker installation steps."
    echo "--------------------------------------------------------"
else
    echo "Docker not found. Starting installation..."

    echo "Preparing your Ubuntu system..."
    sudo apt update && sudo apt upgrade -y

    echo "Installing prerequisites..."
    sudo apt install -y ca-certificates curl gnupg

    # Docker Installation (Official updated method)
    echo "Step 1: Adding Docker's official GPG key..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo "Step 2: Adding Docker's official APT repository..."
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt update

    echo "Step 3: Installing Docker and its components..."
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Verification and Post-Installation
    echo "Step 4: Verifying the installation..."
    docker --version
    sudo systemctl is-active docker

    echo "Step 5: Configuring permissions for user $REAL_USER..."
    sudo usermod -aG docker "$REAL_USER"
    # Note: "newgrp docker" is not used here because it opens a new shell and
    # blocks the script. The group applies after logging out and back in.
    echo "Log out and back in to use docker without sudo."

    echo "--------------------------------------------------------"
    echo "Docker installation completed successfully!"
    echo "--------------------------------------------------------"
fi

# Generate the Docker secrets that do not exist yet (API key, JWT secret,
# MongoDB user and password) and sync the API key into .env
source ./generate_secrets.sh

# 3. Build the images and start the containers in the background (detached),
#    so the script finishes instead of staying attached to the containers' logs.
#    Right after a fresh Docker install the current shell is not yet in the
#    "docker" group, so fall back to sudo in that case.
if docker info &> /dev/null; then
    DOCKER="docker"
else
    DOCKER="sudo docker"
fi
$DOCKER compose up -d --build

echo "--------------------------------------------------------"
echo "Seneca AI containers started in the background."
echo "  Status: docker compose ps"
echo "  Logs:   docker compose logs -f"
echo "--------------------------------------------------------"
