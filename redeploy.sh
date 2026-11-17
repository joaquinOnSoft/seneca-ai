#!/bin/bash

clear

# Generate the Docker secrets that do not exist yet (API key, JWT secret,
# MongoDB user and password) and sync the API key into .env
source ./generate_secrets.sh

docker compose down -v
docker compose build --no-cache
docker compose up -d