# Creates the FoodSpend MySQL database and a dedicated application user.
# Run from the project root:  powershell -ExecutionPolicy Bypass -File scripts\setup_mysql.ps1
# You are prompted for the MySQL root password locally; it is never written to disk.

param(
    [string]$MysqlExe = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    [string]$DbName = "foodspend",
    [string]$AppUser = "foodspend",
    [string]$DbHost = "127.0.0.1",
    [int]$Port = 3306
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $MysqlExe)) { throw "mysql.exe not found at $MysqlExe. Pass -MysqlExe <path>." }

$rootPlain = $null
for ($attempt = 1; $attempt -le 3 -and -not $rootPlain; $attempt++) {
    $rootPwd = Read-Host "MySQL root password (attempt $attempt of 3)" -AsSecureString
    $candidate = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($rootPwd))
    $env:MYSQL_PWD = $candidate
    & $MysqlExe -u root -h $DbHost -P $Port -e "SELECT 1" 2>$null | Out-Null
    $ok = $LASTEXITCODE -eq 0
    Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
    if ($ok) { $rootPlain = $candidate } else { Write-Warning "Access denied for root@$DbHost`:$Port." }
}
if (-not $rootPlain) {
    throw "Could not log in as root. Use the password set when MySQL was installed (MySQL Workbench may have it saved), or set DB_ENGINE=sqlite in backend\.env to continue without MySQL."
}

# Random password for the application user (alphanumeric, 24 chars)
$chars = (48..57) + (65..90) + (97..122)
$appPwd = -join ($chars | Get-Random -Count 24 | ForEach-Object { [char]$_ })

$sql = @"
CREATE DATABASE IF NOT EXISTS ``$DbName`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$AppUser'@'localhost' IDENTIFIED BY '$appPwd';
ALTER USER '$AppUser'@'localhost' IDENTIFIED BY '$appPwd';
GRANT ALL PRIVILEGES ON ``$DbName``.* TO '$AppUser'@'localhost';
GRANT ALL PRIVILEGES ON ``test_$DbName``.* TO '$AppUser'@'localhost';
FLUSH PRIVILEGES;
"@

$env:MYSQL_PWD = $rootPlain
try {
    $sql | & $MysqlExe -u root -h $DbHost -P $Port
    if ($LASTEXITCODE -ne 0) { throw "mysql exited with code $LASTEXITCODE" }
} finally {
    Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
}

$envFile = Join-Path $PSScriptRoot "..\backend\.env"
$secret = -join ((1..50) | ForEach-Object { [char]($chars | Get-Random) })
@"
DJANGO_SECRET_KEY=$secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DB_ENGINE=mysql
DB_NAME=$DbName
DB_USER=$AppUser
DB_PASSWORD=$appPwd
DB_HOST=$DbHost
DB_PORT=$Port
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
"@ | Set-Content -Path $envFile -Encoding utf8

Write-Host "Database '$DbName' and user '$AppUser' are ready. Wrote backend\.env (gitignored)."
