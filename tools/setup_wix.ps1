$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$wixFolder = Join-Path $projectRoot 'build\wix'
$archive = Join-Path $projectRoot 'build\wix314-binaries.zip'
New-Item -ItemType Directory -Force -Path $wixFolder | Out-Null
Invoke-WebRequest -Uri 'https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip' -OutFile $archive -UseBasicParsing
Expand-Archive -LiteralPath $archive -DestinationPath $wixFolder -Force
Write-Host "WiX ready: $wixFolder"
