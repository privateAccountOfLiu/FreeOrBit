# FreeOrBit Nuitka 单文件打包（Windows）
# 依赖: pip install nuitka ordered-set zstandard
# 输出目录: ./build/
# 默认使用 --onefile-no-compression，避免 zstd 压缩大体积时内存不足；若需更小体积且机器内存充足，可去掉该参数。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:PYTHONPATH = "src"

$Ico = Join-Path $Root "FreeOrBit.ico"
if (-not (Test-Path $Ico)) {
    Write-Error "未找到图标文件: $Ico"
}

$DataIco = Join-Path $Root "src\freeorbit\resources\FreeOrBit.ico"
if (-not (Test-Path $DataIco)) {
    Write-Error "未找到包内图标: $DataIco"
}

$NuitkaArgs = @(
    "-m", "nuitka",
    "main.py",
    "--assume-yes-for-downloads",
    "--onefile",
    "--onefile-no-compression",
    "--output-dir=build",
    "--output-filename=FreeOrBit.exe",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=$Ico",
    "--enable-plugins=pyside6",
    "--include-package=freeorbit",
    "--include-package=qt_material",
    "--include-package=qtawesome",
    "--include-package-data=qt_material",
    "--include-data-files=$DataIco=freeorbit/resources/FreeOrBit.ico"
)

Write-Host "python $($NuitkaArgs -join ' ')"
& python @NuitkaArgs
