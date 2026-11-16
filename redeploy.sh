#!/bin/bash

clear

# Generate the JWT signing secret used by the api container (only once)
JWT_SECRET_FILE="docker/api/jwt_secret_key.txt"
if [ ! -s "$JWT_SECRET_FILE" ]; then
    echo "Generating JWT secret in $JWT_SECRET_FILE..."
    (umask 077 && head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$JWT_SECRET_FILE")
fi

docker compose down -v
docker compose build --no-cache
docker compose up -d