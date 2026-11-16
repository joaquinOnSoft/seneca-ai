@echo off
setlocal

cls

set "COMPOSE_FILE=docker-compose.yaml;docker-compose.windows.yaml"

REM Generate the JWT signing secret used by the api container (only once)
set "JWT_SECRET_FILE=%~dp0docker\api\jwt_secret_key.txt"
if not exist "%JWT_SECRET_FILE%" (
    echo Generating JWT secret in %JWT_SECRET_FILE%...
    powershell -NoProfile -Command "$b = New-Object byte[] 32; $r = [Security.Cryptography.RandomNumberGenerator]::Create(); $r.GetBytes($b); $r.Dispose(); [IO.File]::WriteAllText('%JWT_SECRET_FILE%', (($b | ForEach-Object { $_.ToString('x2') }) -join ''))"
)

docker compose down -v
REM docker compose build --no-cache
REM docker compose up -d
docker-compose up -d --build --force-recreate

endlocal