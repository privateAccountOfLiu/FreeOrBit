# FreeOrBit

一款免费开源的十六进制 / 二进制编辑器（Hex Editor）。

![FreeOrBit MainWindow](MainWindowShow.png)

**当前版本：1.0.2**

基于 **PySide6** 的桌面应用，面向逆向、固件与数据分析。支持大文件（`mmap`）、多标签、暗色主题、**中英文界面**（设置中切换）。

## 功能概览

| 类别 | 说明 |
|------|------|
| **编辑** | 十六进制 / ASCII 视图、插入/覆盖、撤销重做、**转到偏移**、**书签**（筛选、编辑、删除、**JSON 导入/导出**）、搜索高亮 |
| **搜索** | 十六进制与 **ASCII 字面量**；十六进制模式支持 `??` 单字节通配（如 `48??6C`） |
| **结构模板** | Python 模板：`build_field_tree(model)` → `FieldNode` 树；标量 `dtype` 写回；`builders` 辅助；内置模板（如 PE DOS 头）；**扩展名 / Magic 自动匹配**（设置中可配）；**Ctrl+J** 在结构树中定位光标；悬停字节显示字段路径 |
| **脚本** | 受限 `EditorAPI`（`read` / `write` / `cursor` / `message` 等），见 [`python_script_api.html`](python_script_api.html) |
| **工具** | **反汇编**（Capstone，多架构）、**填充/字节运算**、文件比较、校验和/哈希、**ORF 滑窗分析**（数值筛选 + 相位分组 + 偏移分布图） |
| **平台（Windows）** | **打开进程内存**、**原始磁盘/卷**（需管理员）；进程缓冲下 **Hex 左侧列** 显示 **模块名+RVA**（类 Cheat Engine）；**F5 刷新**外部缓冲 |
| **其它** | 启动画面、工具栏图标（QtAwesome / Font Awesome） |

## 运行要求

- Python **3.10+**
- 依赖见 [`pyproject.toml`](pyproject.toml)：**PySide6**、**QtAwesome**、**capstone**
- Windows 下使用系统原生 **`windowsvista`** 界面样式

## 从源码运行

在项目根目录：

```bash
pip install -e ".[dev]"
python main.py
```

或（已安装可编辑包或将 `src` 加入 `PYTHONPATH`）：

```bash
python -m freeorbit
```

安装后也可直接：

```bash
freeorbit
```

## 文档

| 文档 | 说明 |
|------|------|
| [`python_script_api.html`](python_script_api.html) | 脚本面板 API |
| [`python_template.html`](python_template.html) | 结构模板（Python）编写指南 |
| [`Scheme.md`](Scheme.md) | 产品策划、与 010 Editor 对照、已实现能力清单 |

## 打包（Windows，Nuitka 单文件）

安装构建依赖：

```bash
pip install -e ".[build]"
```

在项目根目录执行：

```powershell
.\build_nuitka.ps1
```

输出：`build/FreeOrBit.exe`。若 onefile 解压内存不足，可使用：

```powershell
.\build_nuitka.ps1 -OneFileNoCompression
```

详细说明见 [`build_nuitka.ps1`](build_nuitka.ps1) 顶部注释。

### Windows「智能应用控制」/ SmartScreen

本地构建的 `FreeOrBit.exe` **未代码签名**时，系统可能提示未知发布者。可在拦截界面选择「更多信息」→「仍要运行」。正式分发建议使用 **Authenticode** 证书签名。

## 许可

### [Apache License 2.0](LICENSE)

### 软件最终解释权归作者 PrivateLiu 所有
