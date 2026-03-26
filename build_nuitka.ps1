# FreeOrBit Nuitka 单文件打包（Windows）
# 本文件须保存为「带 BOM 的 UTF-8」，否则在 Windows PowerShell 5.1 下会按系统 ANSI 误解析中文，导致 $PSScriptRoot 等失效。
#
# 依赖: 建议在项目 .venv 中: pip install -e ".[build]" ; pip install capstone
#      脚本会优先使用 .venv\Scripts\python.exe，与 pip 安装环境一致。
# 输出: ./build/FreeOrBit.exe
#
# --- capstone（关键）---
# ctypes 加载的 capstone.dll 不能仅靠 --include-package-data=capstone 在 onefile 下被正确解析。
# 构建时从当前 Python 环境的 capstone 包复制 capstone.dll 到目标路径
#   freeorbit/resources/capstone/capstone.dll
# 运行时由 runtime_bootstrap.ensure_capstone_dll_path() 设置 LIBCAPSTONE_PATH（与 icon 同包路径语义）。
# 不再使用 pkg-resources 插件（会增大体积且对 capstone 帮助有限）。
#
# --- 体积---
# - onefile：安装 zstandard 后才启用压缩（否则 Nuitka 会警告并生成更大 exe）；见 pyproject [build]。
# - --lto=yes、--python-flag=-O、anti-bloat；排除 capstone C 头目录、未使用的 Qt 插件、setuptools/pydoc 跟随。
# - --nofollow-import-to=*.tests
#
# 若打包或解压内存不足: .\build_nuitka.ps1 -OneFileNoCompression
#
param(
    [switch]$OneFileNoCompression
)

$ErrorActionPreference = "Stop"
# $PSScriptRoot 在 -File 执行时可靠；部分宿主下 MyCommand.Path 为空会导致 $Root 为 null
if ($PSScriptRoot) {
    $Root = $PSScriptRoot
} else {
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Get-Location).Path
}
Set-Location $Root

$env:PYTHONPATH = "src"

# 优先使用项目 .venv（与 pip install capstone 的环境一致），避免 PATH 指向全局 Python 导致找不到 capstone
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    $PyExe = $VenvPy
} else {
    $PyExe = "python"
}

$Ico = Join-Path $Root "FreeOrBit.ico"
if (-not (Test-Path $Ico)) {
    Write-Error ('未找到图标文件: {0}' -f $Ico)
}

$PkgIco = Join-Path $Root "src\freeorbit\resources\FreeOrBit.ico"
if (-not (Test-Path $PkgIco)) {
    Write-Error ('未找到包内图标: {0}（与 pyproject package-data 一致）' -f $PkgIco)
}

# 当前环境中 capstone 自带的 capstone.dll（需已在上述 Python 中 pip install capstone）
# 路径由独立 .py 输出（避免 PowerShell 对 -c 引号与编码差异导致捕获为空）。
$CapHelper = Join-Path $Root "build_capstone_dll_path.py"
if (-not (Test-Path $CapHelper)) {
    Write-Error ('未找到: {0}' -f $CapHelper)
}
$CapDll = & $PyExe -u $CapHelper
$CapExit = $LASTEXITCODE
$CapDll = ([string]$CapDll).Trim()
if ([string]::IsNullOrWhiteSpace($CapDll)) {
    $code = if ($null -ne $CapExit) { $CapExit } else { "?" }
    Write-Error ('无法解析 capstone.dll 路径（退出码 {0}，解释器 {1}）。请确认已安装: & "{1}" -m pip install capstone' -f $code, $PyExe)
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
    # anti-bloat 为 Nuitka 默认启用，无需再写进 --enable-plugins（否则会告警）
    "--enable-plugins=pyside6",
    "--noinclude-pytest-mode=nofollow",
    "--noinclude-unittest-mode=nofollow",
    "--noinclude-setuptools-mode=nofollow",
    "--noinclude-pydoc-mode=nofollow",
    "--noinclude-IPython-mode=nofollow",
    '--nofollow-import-to=*.tests',
    # capstone：仅需 lib/capstone.dll，C 头约数百 KB 无运行价值
    "--noinclude-data-files=capstone/include",
    # 纯 QWidget + 文件/图标：排除 Qt 未使用插件（名称与 PySide6/plugins 目录一致）
    "--noinclude-qt-plugins=assetimporters,canbus,designer,geometryloaders,geoservices,multimedia,networkinformation,position,qmllint,qmltooling,renderers,renderplugins,sceneparsers,scxmldatamodel,sensors,sqldrivers,texttospeech,webview",
    # 唯一可信的 DLL 落点：与 freeorbit.__file__/resources 同树，供 runtime_bootstrap 解析
    "--include-data-files=$CapDll=freeorbit/resources/capstone/capstone.dll",
    "--include-package=freeorbit",
    "--include-package-data=freeorbit",
    "--include-package=qtawesome",
    "--include-package=capstone",
    "--include-package-data=qtawesome"
)

if ($OneFileNoCompression) {
    $NuitkaArgs += "--onefile-no-compression"
}

Write-Host "使用: $PyExe"
Write-Host "$PyExe $($NuitkaArgs -join ' ')"
& $PyExe @NuitkaArgs
