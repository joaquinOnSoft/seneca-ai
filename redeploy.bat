@echo off
setlocal

cls

set "COMPOSE_FILE=docker-compose.yaml;docker-compose.windows.yaml"

REM Generate the Docker secrets that do not exist yet (API key, JWT secret,
REM MongoDB user and password) and sync the API key into .env
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0generate_secrets.ps1"

docker compose down -v
REM docker compose build --no-cache
REM docker compose up -d
docker compose up -d --build --force-recreate

endlocal