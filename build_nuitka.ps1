# FreeOrBit Nuitka 单文件打包（Windows）
#
# 依赖: pip install -e . ; pip install nuitka ordered-set zstandard
# 输出: ./build/FreeOrBit.exe
#
# --- 体积与性能（在功能完整的前提下尽量缩小）---
# - 默认启用 onefile 内压缩（较 -OneFileNoCompression 明显更小；首次运行解压略多占内存）。
# - --lto=yes：链接期优化。
# - --python-flag=-O：去除 assert，略减字节码体积。
# - --enable-plugin=anti-bloat：避免打入 pytest 等测试栈。
# - --include-package=capstone + --include-package-data=capstone：反汇编依赖 capstone 及 lib 下原生 DLL。
# - --nofollow-import-to=*.tests：跳过依赖树中的 tests 子包（若被间接引用）。
# - --include-package-data=qtawesome：图标字体（QtAwesome）。
#
# 若打包或运行解压时内存不足，请使用:
#   .\build_nuitka.ps1 -OneFileNoCompression
#
# --- 静态资源与路径（Nuitka onefile）---
# - 界面文案：编译进 freeorbit.i18n，无外部语言文件。
# - QSettings：与 exe 路径、onefile 临时目录无关（组织名/应用名）。
# - 窗口图标：根目录 FreeOrBit.ico + 包内 src\freeorbit\resources\FreeOrBit.ico 通过 --include-data-files
#   映射到 freeorbit/resources/FreeOrBit.ico，与 icon_assets.app_icon() 一致。
# - 内置模板：随 --include-package=freeorbit 打入 resources/templates/*.py（与 pyproject package-data 一致）。
#
param(
    [switch]$OneFileNoCompression
)

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
    "--remove-output",
    "--onefile",
    "--output-dir=build",
    "--output-filename=FreeOrBit.exe",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=$Ico",
    "--show-progress",
    "--lto=yes",
    "--python-flag=-O",
    "--enable-plugins=pyside6,anti-bloat",
    "--noinclude-pytest-mode=nofollow",
    "--noinclude-unittest-mode=nofollow",
    '--nofollow-import-to=*.tests',
    "--include-package=freeorbit",
    "--include-package=qtawesome",
    "--include-package=capstone",
    "--include-package-data=qtawesome",
    "--include-package-data=capstone",
    "--include-data-files=$DataIco=freeorbit/resources/FreeOrBit.ico"
)

if ($OneFileNoCompression) {
    $NuitkaArgs += "--onefile-no-compression"
}

Write-Host "python $($NuitkaArgs -join ' ')"
& python @NuitkaArgs
