# FreeOrBit Nuitka onefile build (Windows). ASCII-only in this script to avoid PS 5.1 encoding issues.
#
# Deps: pip install -e ".[build]" and pip install capstone in project .venv (script prefers .venv\Scripts\python.exe).
# Output: ./build/FreeOrBit.exe
#
# capstone: ctypes needs capstone.dll beside the package; build copies DLL to freeorbit/resources/capstone/
#   via build_capstone_dll_path.py; runtime_bootstrap sets LIBCAPSTONE_PATH.
#
# Optional: .\build_nuitka.ps1 -OneFileNoCompression if onefile unpack runs out of memory.
#
param(
    [switch]$OneFileNoCompression
)

$ErrorActionPreference = "Stop"
# Project root: PSScriptRoot first; some hosts leave MyCommand.Path empty (Join-Path $null breaks Test-Path).
$Root = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Root)) {
    $cmdPath = $MyInvocation.MyCommand.Path
    if ($cmdPath) {
        $Root = Split-Path -Parent $cmdPath
    }
}
if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Get-Location).Path
}
try {
    $Root = (Resolve-Path -LiteralPath $Root).Path
} catch {
    $Root = (Get-Location).Path
}
Set-Location $Root

$env:PYTHONPATH = "src"

$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    $PyExe = $VenvPy
} else {
    $PyExe = "python"
}

$Ico = Join-Path $Root "FreeOrBit.ico"
if (-not (Test-Path $Ico)) {
    Write-Error "Icon not found: $Ico"
}

$PkgIco = Join-Path $Root "src\freeorbit\resources\FreeOrBit.ico"
if (-not (Test-Path $PkgIco)) {
    Write-Error "Package icon not found: $PkgIco (see pyproject package-data)"
}

$CapHelper = Join-Path -Path $Root -ChildPath "build_capstone_dll_path.py"
if ([string]::IsNullOrWhiteSpace($CapHelper)) {
    Write-Error "Invalid capstone helper path (Root=$Root)"
}
if (-not (Test-Path -LiteralPath $CapHelper)) {
    Write-Error "File not found: $CapHelper"
}
$CapDll = & $PyExe -u $CapHelper
$CapExit = $LASTEXITCODE
$CapDll = ([string]$CapDll).Trim()
if ([string]::IsNullOrWhiteSpace($CapDll)) {
    $code = if ($null -ne $CapExit) { $CapExit } else { "?" }
    Write-Error "Could not resolve capstone.dll path (exit $code, python $PyExe). Run: pip install capstone"
}

$NuitkaArgs = @(
    "-m", "nuitka",
    "main.py",
    "--assume-yes-for-downloads",
    "--remove-output",
    "--onefile",
    "--output-dir=build",
    "--output-filename=FreeOrBit.exe",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=$Ico",
    "--show-progress",
    "--jobs=0",
    "--lto=yes",
    "--python-flag=-O",
    "--enable-plugins=pyside6",
    "--noinclude-pytest-mode=nofollow",
    "--noinclude-unittest-mode=nofollow",
    "--noinclude-setuptools-mode=nofollow",
    "--noinclude-pydoc-mode=nofollow",
    "--noinclude-IPython-mode=nofollow",
    '--nofollow-import-to=*.tests',
    "--noinclude-data-files=capstone/include",
    "--noinclude-qt-plugins=assetimporters,canbus,designer,geometryloaders,geoservices,multimedia,networkinformation,position,qmllint,qmltooling,renderers,renderplugins,sceneparsers,scxmldatamodel,sensors,sqldrivers,texttospeech,webview",
    "--include-data-files=$CapDll=freeorbit/resources/capstone/capstone.dll",
    "--include-package=freeorbit",
    "--include-package-data=freeorbit",
    "--include-package=qtawesome",
    "--include-package=capstone",
    "--include-package-data=qtawesome",
    "--include-package=frida",
    "--include-package-data=frida"
)

if ($OneFileNoCompression) {
    $NuitkaArgs += "--onefile-no-compression"
}

Write-Host "Python: $PyExe"
$argLine = $NuitkaArgs -join " "
Write-Host "$PyExe $argLine"
& $PyExe @NuitkaArgs
