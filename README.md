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

### Windows「智能应用控制」/ SmartScreen 提示未知发布者

本地 Nuitka 打出的 `FreeOrBit.exe`**未经过代码签名**，Windows 可能显示「不知道发布者」「不是熟悉的应用」并拦截。这是系统对**未建立信誉的未签名程序**的常规策略，与 PySide6/Nuitka 本身无关。

**临时在本机运行**：在拦截界面上点「更多信息」或「仍要运行」（具体文案因 Windows 版本而异），即可启动。

**正式对外分发**（减少用户看到红/黄提示）：使用由**受信任 CA 颁发的代码签名证书**，在构建完成后对 `FreeOrBit.exe` 做 **Authenticode 签名**（常用工具：`signtool.exe`，需安装 Windows SDK）。扩展验证（EV）证书通常能更快获得 SmartScreen 信任，但需向证书厂商购买并按流程验证身份。

**注意**：自签名证书一般**不能**消除 SmartScreen 的发布者警告，仅适合内网或自用场景。

## 许可

MIT License

## 其它

软件最终解释权归作者PrivateLiu所有
