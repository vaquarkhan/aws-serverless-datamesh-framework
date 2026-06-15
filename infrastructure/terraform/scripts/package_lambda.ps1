#Requires -Version 5.1
<#
.SYNOPSIS
    Build Lambda deployment package for Terraform (Windows).
.EXAMPLE
    .\infrastructure\terraform\scripts\package_lambda.ps1
#>
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$BuildDir = Join-Path $Root "infrastructure\terraform\build"
$Package = Join-Path $BuildDir "domain-writer.zip"
$Staging = Join-Path $BuildDir "staging"

$Extras = $env:SDM_EXTRAS
$InstallSpec = $Root.Path
if ($Extras) { $InstallSpec = "$($Root.Path)[$Extras]" }

Write-Host "==> Building Lambda package (extras=$($Extras ?? 'core'))"
if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
if (Test-Path $Package) { Remove-Item $Package -Force }
New-Item -ItemType Directory -Path $Staging -Force | Out-Null

python -m pip install $InstallSpec --target $Staging --upgrade
Copy-Item -Recurse (Join-Path $Root "examples") (Join-Path $Staging "examples")

Push-Location $Staging
Compress-Archive -Path * -DestinationPath $Package -Force
Pop-Location

Write-Host "==> Package ready: $Package"
