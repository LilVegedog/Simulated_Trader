<#
Stops and removes the FinAlly container. The named data volume is left intact.
Usage: scripts\stop_windows.ps1
#>
$ErrorActionPreference = "Stop"
$ContainerName = "finally"

$exists = docker ps -a --filter "name=^/$ContainerName$" --format "{{.Names}}"
if ($exists -ne $ContainerName) {
    Write-Host "FinAlly is not running."
    exit 0
}

docker rm -f $ContainerName | Out-Null
Write-Host "FinAlly stopped. Data volume 'finally-data' was preserved."
