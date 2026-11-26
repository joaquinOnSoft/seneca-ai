#!/bin/bash

# ==============================================================================
# SENECA AI - Linux (Ubuntu) uninstaller
# ==============================================================================
#
# Run it from the project folder, as the installer:
#
#   sudo ./uninstall-ubuntu.sh             # uninstall
#   sudo ./uninstall-ubuntu.sh --dry-run   # only print what it would do
#
# 1. Removes the Seneca AI containers, their network and their images.
# 2. Asks (default: no) whether to delete the data volumes: conversations
#    (MongoDB), long-term memory (Qdrant) and downloaded models (Ollama,
#    Whisper). That information cannot be recovered.
# 3. Asks (default: no) whether to uninstall Docker.
#
# The project folder, .env and the secrets in docker/ are not deleted:
# delete the folder by hand when you no longer need it.
# ==============================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

# Host folders created by install-ubuntu.sh (used when docker compose cannot
# resolve the volume paths, e.g. when Docker is not installed)
DEFAULT_DATA_DIRS=(/opt/senecaai/volumes/ollama /opt/senecaai/volumes/mongo
                   /opt/senecaai/volumes/huggingface /opt/senecaai/volumes/qdrant)
DATA_ROOT=/opt/senecaai

# Run a command, or only print it with --dry-run
run() {
    if [ "$DRY_RUN" = true ]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

# Ask a yes/no question. Returns 0 (yes) only for y/yes/s/si; anything else,
# including ENTER, is "no".
confirm() {
    local answer
    read -r -p "$1 [y/N]: " answer
    case "$(echo "$answer" | tr '[:upper:]' '[:lower:]')" in
        y|yes|s|si|sí) return 0 ;;
        *) return 1 ;;
    esac
}

# Delete a data folder, refusing anything that is not a deep absolute path
remove_data_dir() {
    local dir="$1"
    case "$dir" in
        /*/*) ;;
        *) echo "Skipping suspicious path: '$dir'"; return ;;
    esac
    if [ -d "$dir" ]; then
        echo "Deleting $dir"
        run rm -rf -- "$dir"
    fi
}

if [ "$(id -u)" -ne 0 ] && [ "$DRY_RUN" = false ]; then
    echo "This script must be run with sudo: sudo ./uninstall-ubuntu.sh"
    exit 1
fi

echo "============================================================"
echo " SENECA AI - UNINSTALL"
[ "$DRY_RUN" = true ] && echo " (dry run: nothing will be changed)"
echo "============================================================"

# ------------------------------------------------------------------------------
# 0. Is Docker available?
# ------------------------------------------------------------------------------
DOCKER_OK=false
if command -v docker &> /dev/null; then
    if ! docker info &> /dev/null; then
        echo "Starting the Docker service..."
        systemctl start docker 2> /dev/null
    fi
    docker info &> /dev/null && DOCKER_OK=true
fi
if [ "$DOCKER_OK" = false ]; then
    echo "Docker is not installed or not running: the containers cannot be removed."
fi

# ------------------------------------------------------------------------------
# 1. Ask about the data volumes before removing anything
# ------------------------------------------------------------------------------
# Host folders behind the volumes, as docker compose resolves them from .env.
# Only the "device:" lines are read, so no other value of .env is printed.
DATA_DIRS=()
PROJECT_NAME="$(basename "$SCRIPT_DIR" | tr '[:upper:]' '[:lower:]')"
if [ "$DOCKER_OK" = true ]; then
    COMPOSE_CONFIG="$(docker compose config 2> /dev/null)"
    while IFS= read -r dir; do
        [ -n "$dir" ] && DATA_DIRS+=("$dir")
    done < <(echo "$COMPOSE_CONFIG" | sed -n "s/^ *device: *//p" | tr -d "\"'")
    name="$(echo "$COMPOSE_CONFIG" | sed -n 's/^name: *//p')"
    [ -n "$name" ] && PROJECT_NAME="$name"
    unset COMPOSE_CONFIG
fi
[ ${#DATA_DIRS[@]} -eq 0 ] && DATA_DIRS=("${DEFAULT_DATA_DIRS[@]}")

echo ""
echo "------------------------------------------------------------"
echo " WARNING: deleting the volumes deletes ALL the information"
echo " of Seneca AI and it CANNOT be recovered:"
echo "   - conversations and users (MongoDB)"
echo "   - long-term memory (Qdrant)"
echo "   - downloaded AI models (Ollama, Whisper)"
echo " Folders:"
for dir in "${DATA_DIRS[@]}"; do echo "   $dir"; done
echo "------------------------------------------------------------"
DELETE_VOLUMES=false
if confirm "Delete the volumes and all their data?"; then
    DELETE_VOLUMES=true
else
    echo "The volumes are kept. Installing Seneca AI again will reuse them."
fi

# ------------------------------------------------------------------------------
# 2. Remove the containers, the network and the images of the app
# ------------------------------------------------------------------------------
if [ "$DOCKER_OK" = true ]; then
    echo ""
    echo "Removing the Seneca AI containers, network and images..."
    DOWN_ARGS=(down --remove-orphans --rmi all)
    [ "$DELETE_VOLUMES" = true ] && DOWN_ARGS+=(--volumes)
    run docker compose "${DOWN_ARGS[@]}"
fi

if [ "$DELETE_VOLUMES" = true ]; then
    for dir in "${DATA_DIRS[@]}"; do remove_data_dir "$dir"; done
    # Remove the parent folders created by the installer, only if empty
    run rmdir --ignore-fail-on-non-empty "$DATA_ROOT/volumes" "$DATA_ROOT" 2> /dev/null
fi

# ------------------------------------------------------------------------------
# 3. Optionally uninstall Docker (default: no)
# ------------------------------------------------------------------------------
if command -v docker &> /dev/null; then
    echo ""
    echo "------------------------------------------------------------"
    echo " Docker may be used by other applications on this computer."
    if [ "$DOCKER_OK" = true ]; then
        # Containers of other applications (not of the Seneca AI compose project)
        OTHER_CONTAINERS=$(docker ps -a --format '{{.Label "com.docker.compose.project"}}' \
                           | grep -cvxF "$PROJECT_NAME")
        echo " Containers of other applications: $OTHER_CONTAINERS"
    fi
    echo "------------------------------------------------------------"
    if confirm "Uninstall Docker?"; then
        echo "Uninstalling Docker..."
        run apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
            docker-compose-plugin docker-ce-rootless-extras
        run apt-get autoremove -y
        run rm -f /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.gpg

        echo ""
        echo " Docker keeps the images, containers and volumes of ALL the"
        echo " applications in /var/lib/docker and /var/lib/containerd."
        if confirm "Delete them too (cannot be undone)?"; then
            run rm -rf /var/lib/docker /var/lib/containerd
        fi
    else
        echo "Docker is kept."
    fi
fi

echo ""
echo "============================================================"
echo " Seneca AI has been uninstalled."
echo " The project folder ($SCRIPT_DIR), with .env and the secrets"
echo " in docker/, was kept: delete it by hand if you no longer need it."
echo "============================================================"
