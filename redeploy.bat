@echo off
setlocal

cls

set "COMPOSE_FILE=docker-compose.yaml;docker-compose.windows.yaml"

docker compose down -v
REM docker compose build --no-cache
REM docker compose up -d
docker-compose up -d --build --force-recreate

endlocal