[CmdletBinding()]
param(
    [string]$HostName = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 2006,
    [string]$PostgresUser = "postgres"
)

$ErrorActionPreference = "Stop"

function New-HexSecret {
    param(
        [Parameter(Mandatory)]
        [ValidateRange(16, 128)]
        [int]$Bytes
    )

    $buffer = New-Object byte[] $Bytes
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($buffer)
    }
    finally {
        $generator.Dispose()
    }

    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

function Find-PostgresTool {
    param(
        [Parameter(Mandatory)]
        [string]$Name
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "D:\Program Files\PostgreSQL\18\bin\$Name.exe",
        "C:\Program Files\PostgreSQL\18\bin\$Name.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "Could not find $Name.exe. Install PostgreSQL command-line tools."
}

function Set-EnvValue {
    param(
        [Parameter(Mandatory)]
        [string]$Content,
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$Value
    )

    $pattern = "(?m)^$([Regex]::Escape($Name))=.*$"
    $line = "$Name=$Value"
    if ([Regex]::IsMatch($Content, $pattern)) {
        return [Regex]::Replace($Content, $pattern, $line)
    }
    return "$Content$([Environment]::NewLine)$line$([Environment]::NewLine)"
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = Join-Path $projectRoot ".env"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$psql = Find-PostgresTool -Name "psql"
$pgIsReady = Find-PostgresTool -Name "pg_isready"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "The project virtual environment is missing. Run: python -m venv .venv"
}

& $pgIsReady -h $HostName -p $Port -t 3
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL is not accepting connections at ${HostName}:$Port."
}

$securePassword = Read-Host "PostgreSQL password for '$PostgresUser'" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
    $securePassword
)
$appPassword = New-HexSecret -Bytes 32
$jwtSecret = New-HexSecret -Bytes 64

try {
    $adminPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        $passwordPointer
    )
    $env:PGPASSWORD = $adminPassword

    $sql = @"
SELECT 'CREATE ROLE check_out_app LOGIN'
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'check_out_app'
)
\gexec
ALTER ROLE check_out_app WITH LOGIN PASSWORD '$appPassword';

SELECT 'CREATE DATABASE check_out_db OWNER check_out_app'
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'check_out_db'
)
\gexec
ALTER DATABASE check_out_db OWNER TO check_out_app;
"@

    $sql | & $psql `
        -h $HostName `
        -p $Port `
        -U $PostgresUser `
        -d postgres `
        -v ON_ERROR_STOP=1 `
        -f -
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL provisioning failed. Check the administrator password."
    }
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $adminPassword = $null
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
}

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot ".env.example") -Destination $envPath
}

$envContent = Get-Content -Raw -LiteralPath $envPath
$databaseUrl = (
    "postgresql+psycopg://check_out_app:${appPassword}@" +
    "${HostName}:$Port/check_out_db"
)
$envContent = Set-EnvValue `
    -Content $envContent `
    -Name "DATABASE_URL" `
    -Value $databaseUrl
$envContent = Set-EnvValue `
    -Content $envContent `
    -Name "SECRET_KEY" `
    -Value $jwtSecret

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($envPath, $envContent, $utf8NoBom)

Push-Location $projectRoot
try {
    & $pythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Alembic migration failed."
    }
}
finally {
    Pop-Location
}

Write-Host "PostgreSQL is configured and migrations are current." -ForegroundColor Green
Write-Host "Next, run: python -m app.cli create-admin"
Write-Host "Then start: python -m uvicorn app.main:app --reload"
