# FreeOrBit Nuitka 单文件打包（Windows）
#
# 依赖: pip install nuitka ordered-set zstandard
# 输出: ./build/FreeOrBit.exe
#
# --- 体积优化（在不影响功能的前提下尽量缩小）---
# - 默认启用 onefile 内压缩（较 --onefile-no-compression 明显更小；首次运行解压略多占内存）。
# - --lto=yes：链接期优化（编译略慢，可略减体积/略提运行性能）。
# - --python-flag=-O：去除 assert 等，略减字节码体积。
# - --include-package-data=qtawesome：确保图标字体等资源打入（与「缩小」不矛盾，避免缺文件）。
#
# 若打包或运行解压时内存不足，请使用：
#   .\build_nuitka.ps1 -OneFileNoCompression
#
# --- i18n / 配置 / 资源路径（Nuitka onefile 下）---
# - 界面文案：全部编译进 Python 字节码（freeorbit.i18n），无外部 .json/.qm 语言文件。
# - QSettings：语言与其它 Qt 设置写入「组织名/应用名」对应位置（Windows 通常为注册表或
#   %APPDATA%，由 QApplication 的 organizationName/applicationName 决定），与 exe 所在路径、
#   onefile 临时解压目录无关；升级或移动安装包不会丢失语言偏好（除非清注册表/配置）。
# - 窗口图标：通过 --include-data-files 安装到包内 freeorbit/resources/FreeOrBit.ico，
#   运行时由 icon_assets.app_icon() 用 freeorbit.__file__ 解析，与 frozen/开发一致。
# - 用户数据（打开/保存的文件）仍为用户自选路径，与打包无关。
#
param(
    # 禁用 onefile 内压缩：exe 更大，但解压峰值内存更低（旧环境曾 OOM 时可开）
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
    "--onefile",
    "--output-dir=build",
    "--output-filename=FreeOrBit.exe",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=$Ico",
    "--show-progress",
    "--lto=yes",
    "--python-flag=-O",
    "--enable-plugins=pyside6",
    "--include-package=freeorbit",
    "--include-package=qt_material",
    "--include-package=qtawesome",
    "--include-package-data=qt_material",
    "--include-package-data=qtawesome",
    "--include-data-files=$DataIco=freeorbit/resources/FreeOrBit.ico"
)

if ($OneFileNoCompression) {
    $NuitkaArgs += "--onefile-no-compression"
}

Write-Host "python $($NuitkaArgs -join ' ')"
& python @NuitkaArgs
