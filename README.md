# FreeOrBit

基于 PySide6 的十六进制 / 二进制编辑器（开发中）。

## 运行要求

- Python 3.10+
- 依赖见 `pyproject.toml`（PySide6、qt-material、QtAwesome）

## 从源码运行

在项目根目录执行：

```bash
pip install -e ".[dev]"
python main.py
```

或使用模块方式（需已将 `src` 加入 `PYTHONPATH` 或已安装包）：

```bash
python -m freeorbit
```

## 脚本 API

用户脚本的全局 API 说明见根目录 [`python_script_api.html`](python_script_api.html)。

## 打包（Windows）

先安装项目依赖（含 PySide6、qt-material 等），再安装 Nuitka：

```bash
pip install -e .
pip install nuitka ordered-set zstandard
```

在项目根目录执行：

```powershell
.\build_nuitka.ps1
```

生成的单文件可执行文件为 `build/FreeOrBit.exe`。脚本默认关闭 onefile 载荷压缩，以降低打包阶段内存占用；若需更小体积且内存充足，可编辑 `build_nuitka.ps1` 去掉 `--onefile-no-compression`。

## 许可

（请在此补充许可证信息。）
