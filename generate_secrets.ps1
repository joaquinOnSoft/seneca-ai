# ==============================================================================
# Generate the Docker secrets used by the containers (only the missing ones).
#
#   docker\api\seneca_ai_api_key.txt      API key (X-SENECA-AI-API-KEY header)
#   docker\api\jwt_secret_key.txt         Signs the JWT access tokens
#   docker\mongo\mongo_root_username.txt  MongoDB root user
#   docker\mongo\mongo_root_password.txt  MongoDB root password
#
# Existing files are never overwritten:
#   - MongoDB only applies the root user/password when it initialises an EMPTY
#     data directory. A new password on an existing database would lock the
#     api container out.
#   - A new JWT secret would invalidate the tokens already issued.
#
# The API key is also copied to SENECA_AI_API_KEY in .env, so the desktop app
# uses the same key as the api container.
#
# None of these files is versioned (see .gitignore).
#
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File generate_secrets.ps1
# ==============================================================================

$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Random hexadecimal string: $Bytes bytes -> 2*$Bytes characters
function Get-RandomHex([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($buffer)
    $rng.Dispose()
    return ($buffer | ForEach-Object { $_.ToString("x2") }) -join ''
}

function New-SecretFile([string]$RelativePath, [string]$Value) {
    $file = Join-Path $Root $RelativePath
    if ((Test-Path $file) -and ((Get-Item $file).Length -gt 0)) {
        Write-Host "Secret already exists, kept: $file" -ForegroundColor Yellow
        return
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $file) -Force | Out-Null
    # No BOM and no trailing newline
    [System.IO.File]::WriteAllText($file, $Value)
    Write-Host "Generated secret: $file" -ForegroundColor Green
}

New-SecretFile "docker\api\seneca_ai_api_key.txt"     (Get-RandomHex 24)
New-SecretFile "docker\api\jwt_secret_key.txt"        (Get-RandomHex 32)
New-SecretFile "docker\mongo\mongo_root_username.txt" "senecaai_admin"
New-SecretFile "docker\mongo\mongo_root_password.txt" (Get-RandomHex 24)

# Keep SENECA_AI_API_KEY in .env in sync with the api container's key
$EnvFile = Join-Path $Root ".env"
$ApiKey  = ([System.IO.File]::ReadAllText((Join-Path $Root "docker\api\seneca_ai_api_key.txt"))).Trim()

if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Created $EnvFile from .env.example" -ForegroundColor Green
}

$lines = @(Get-Content $EnvFile)
$entry = "SENECA_AI_API_KEY=$ApiKey"
if ($lines -notcontains $entry) {
    $found = $false
    $lines = $lines | ForEach-Object {
        if ($_ -match '^SENECA_AI_API_KEY=') { $found = $true; $entry } else { $_ }
    }
    if (-not $found) { $lines = @($lines) + $entry }
    $lines | Set-Content $EnvFile -Encoding UTF8
    Write-Host "SENECA_AI_API_KEY updated in $EnvFile" -ForegroundColor Green
}
