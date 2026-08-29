<#
Builds (if needed) and runs the FinAlly Docker container.
Usage: scripts\start_windows.ps1 [-Build]
#>
param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ImageName = "finally"
$ContainerName = "finally"
$Port = 8000

Set-Location $RepoRoot

if (-not (Test-Path ".env")) {
    Write-Host "No .env file found. Copy .env.example to .env and add your OPENROUTER_API_KEY." -ForegroundColor Yellow
    exit 1
}

$imageId = docker images -q $ImageName
if ($Build -or [string]::IsNullOrWhiteSpace($imageId)) {
    Write-Host "Building Docker image..."
    docker build -t $ImageName .
}

$running = docker ps --filter "name=^/$ContainerName$" --format "{{.Names}}"
if ($running -eq $ContainerName) {
    Write-Host "FinAlly is already running at http://localhost:$Port"
    exit 0
}

$existing = docker ps -a --filter "name=^/$ContainerName$" --format "{{.Names}}"
if ($existing -eq $ContainerName) {
    docker rm -f $ContainerName | Out-Null
}

function Test-ContainerRunning {
    $names = docker ps --filter "name=^/$ContainerName$" --filter "status=running" --format "{{.Names}}"
    return $names -eq $ContainerName
}

Write-Host "Starting FinAlly container..."
docker run -d --name $ContainerName -v finally-data:/app/db -p "${Port}:8000" --env-file .env $ImageName | Out-Null
$runExitCode = $LASTEXITCODE

if ($runExitCode -ne 0) {
    Write-Host "docker run failed (exit code $runExitCode) -- see the error above." -ForegroundColor Red
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $proc = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        Write-Host "Port $Port is already in use by process '$($proc.ProcessName)' (PID $($listener.OwningProcess)). Stop it and try again." -ForegroundColor Red
    }
    exit 1
}

Start-Sleep -Seconds 1
if (-not (Test-ContainerRunning)) {
    Write-Host "FinAlly container exited immediately after starting. Check: docker logs $ContainerName" -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for FinAlly to become healthy..."
$deadline = (Get-Date).AddSeconds(60)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    if (-not (Test-ContainerRunning)) {
        Write-Host "FinAlly container stopped while waiting for it to become healthy. Check: docker logs $ContainerName" -ForegroundColor Red
        exit 1
    }
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port/api/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 2
}

if (-not $healthy) {
    Write-Host "FinAlly did not become healthy in time. Check logs with: docker logs $ContainerName" -ForegroundColor Red
    exit 1
}

Write-Host "FinAlly is running at http://localhost:$Port" -ForegroundColor Green
Start-Process "http://localhost:$Port"
