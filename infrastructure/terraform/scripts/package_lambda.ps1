#Requires -Version 5.1
<#
.SYNOPSIS
    Build Lambda deployment package for Terraform (Windows).
.PARAMETER PipelineSrc
    Path to compiled pipeline directory (handler.py at zip root). Omit for platform demo zip.
.EXAMPLE
    .\infrastructure\terraform\scripts\package_lambda.ps1
.EXAMPLE
    .\infrastructure\terraform\scripts\package_lambda.ps1 -PipelineSrc my-mesh\generated\orders\bronze
#>
param(
    [string]$PipelineSrc = $env:SDM_PIPELINE_SRC
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$BuildDir = Join-Path $Root "infrastructure\terraform\build"
$Package = Join-Path $BuildDir "domain-writer.zip"
$Staging = Join-Path $BuildDir "staging"

$Extras = $env:SDM_EXTRAS
$InstallSpec = $Root.Path
if ($Extras) { $InstallSpec = "$($Root.Path)[$Extras]" }

Write-Host "==> Building Lambda package (extras=$($Extras ?? 'core'), pipeline=$($PipelineSrc ?? 'platform'))"
if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
if (Test-Path $Package) { Remove-Item $Package -Force }
New-Item -ItemType Directory -Path $Staging -Force | Out-Null

python -m pip install $InstallSpec --target $Staging --upgrade

Copy-Item (Join-Path $Root "VERSION") (Join-Path $Staging "VERSION")
$SdmPkg = Join-Path $Staging "serverless_data_mesh"
if (Test-Path $SdmPkg) {
    Copy-Item (Join-Path $Root "VERSION") (Join-Path $SdmPkg "VERSION")
}

if ($PipelineSrc) {
    Write-Host "==> Overlaying compiled pipeline from $PipelineSrc"
    foreach ($f in @("handler.py", "readers.py", "pipeline_config.py")) {
        $src = Join-Path $PipelineSrc $f
        if (Test-Path $src) { Copy-Item $src (Join-Path $Staging $f) }
    }
} else {
    Copy-Item -Recurse (Join-Path $Root "examples") (Join-Path $Staging "examples")
}

Push-Location $Staging
Compress-Archive -Path * -DestinationPath $Package -Force
Pop-Location

$handler = if ($PipelineSrc) { "handler.lambda_handler" } else { "examples.domain_writer.handler.lambda_handler" }
Write-Host "==> Package ready: $Package"
Write-Host "    Handler: $handler"
