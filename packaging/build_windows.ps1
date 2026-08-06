param(
    [string]$MvsRoot = "D:\MVS",
    [string]$MvsRuntime = "C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$mvsImport = Join-Path $MvsRoot "Development\Samples\Python\MvImport"
$distRoot = Join-Path $projectRoot "dist"
$workRoot = Join-Path $projectRoot "build\pyinstaller"
$appName = "AngleMeasurement"
$version = "0.3.1"
$deliveryName = "$appName-v$version-win64"
$deliveryDir = Join-Path $distRoot $deliveryName
$zipPath = Join-Path $distRoot "$deliveryName.zip"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python was not found: $python"
}
if (-not (Test-Path -LiteralPath (Join-Path $mvsImport "MvCameraControl_class.py") -PathType Leaf)) {
    throw "MVS Python SDK was not found: $mvsImport"
}
if (-not (Test-Path -LiteralPath (Join-Path $MvsRuntime "MvCameraControl.dll") -PathType Leaf)) {
    throw "MVS x64 runtime was not found: $MvsRuntime"
}

Push-Location $projectRoot
try {
    if (-not $SkipTests) {
        & $python -m pytest
        if ($LASTEXITCODE -ne 0) { throw "Tests failed; packaging stopped." }
    }

    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name $appName `
        --distpath $distRoot `
        --workpath $workRoot `
        --specpath (Join-Path $projectRoot "build") `
        --paths (Join-Path $projectRoot "src") `
        --add-data "$mvsImport;mvs_sdk" `
        --hidden-import "angle_measurement.ui.launcher" `
        --exclude-module "PySide6.QtWebEngineCore" `
        --exclude-module "PySide6.QtWebEngineWidgets" `
        --exclude-module "PySide6.QtMultimedia" `
        (Join-Path $PSScriptRoot "angle_measurement_app.py")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

    $pyInstallerDir = Join-Path $distRoot $appName
    if (Test-Path -LiteralPath $deliveryDir) {
        Remove-Item -LiteralPath $deliveryDir -Recurse -Force
    }
    Move-Item -LiteralPath $pyInstallerDir -Destination $deliveryDir

    Copy-Item -LiteralPath (Join-Path $projectRoot "configs") -Destination $deliveryDir -Recurse
    New-Item -ItemType Directory -Path (Join-Path $deliveryDir "data\output") -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "DELIVERY_README.txt") -Destination (Join-Path $deliveryDir "README-CN.txt")
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "Launch.cmd") -Destination $deliveryDir
    Copy-Item -LiteralPath (Join-Path $projectRoot "docs\guides\operator-guide.md") -Destination (Join-Path $deliveryDir "OPERATOR-GUIDE-CN.md")
    Copy-Item -LiteralPath (Join-Path $MvsRoot "License\CLIENT_MVS_Win_license_notice.txt") -Destination (Join-Path $deliveryDir "MVS-THIRD-PARTY-NOTICES.txt")
    & $python -m pip freeze | Set-Content -LiteralPath (Join-Path $deliveryDir "PYTHON-DEPENDENCIES.txt") -Encoding UTF8

    # Keep the official MVS user-mode runtime beside the EXE so WinDLL can
    # resolve MvCameraControl.dll and its transitive dependencies offline.
    Copy-Item -Path (Join-Path $MvsRuntime "*") -Destination $deliveryDir -Recurse -Force

    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -LiteralPath $deliveryDir -DestinationPath $zipPath -CompressionLevel Optimal
    $hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
    "$($hash.Hash)  $([IO.Path]::GetFileName($zipPath))" | Set-Content -LiteralPath "$zipPath.sha256.txt" -Encoding ASCII
    Write-Output "DELIVERY_DIR=$deliveryDir"
    Write-Output "ZIP=$zipPath"
    Write-Output "SHA256=$($hash.Hash)"
}
finally {
    Pop-Location
}
