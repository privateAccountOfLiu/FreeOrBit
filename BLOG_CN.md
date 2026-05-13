# FreeOrBit：一款开源十六进制编辑器的诞生——免费替代 010 Editor 的尝试

> **摘要**：FreeOrBit 是一款基于 Python + PySide6 的开源十六进制编辑器，支持深色/浅色主题、字节级文件对比矩阵、Capstone 多架构反汇编、Python 二进制模板系统、内嵌脚本引擎，以及 Android Frida 调试集成。本文介绍它的设计理念、核心功能与技术架构。

---

## 为什么还要造一个 Hex Editor？

市面上的十六进制编辑器并不少。Windows 下有 **010 Editor**（$50 个人版 / $130 专业版）、**Hex Editor Neo**、**WinHex**，Linux 下有 **GHex**、**Bless**，跨平台的有 **ImHex**。

但它们各有痛点：

- **010 Editor** 功能最强，但是闭源商业软件，价格不菲
- **ImHex** 开源但 C++ 技术栈，贡献门槛高
- 多数免费工具缺乏**二进制模板解析**、**脚本自动化**、**进程内存编辑**等高级功能

**FreeOrBit** 的选择是：用 **Python + Qt 6** 全栈，降低开发门槛，同时尽可能覆盖专业场景。

---

## 核心特性一览

### 1. 深色 / 浅色主题，开箱即用

基于 Qt Fusion 风格引擎，全局暗色调色板覆盖所有组件——菜单、滚动条、停靠面板、表格、进度条。内置深色/浅色双主题，可在 **设置 → 外观与行为 → 主题** 中一键切换，即时生效且持久化。

### 2. 字节对比矩阵（Dot Plot）

打开两个文件作比较时，窗口底部会渲染一张**字节级对比矩阵**——横轴为文件 A，纵轴为文件 B，若 `byte_A[i] == byte_B[j]` 则点亮金色像素。矩阵保持 `len(A):len(B)` 的等比缩放，支持超大文件的降采样渲染（后台线程异步计算，不阻塞 UI）。

配合上半部分的**左右分栏十六进制视图**（绿/红逐字节高亮相同/差异，同步滚动），比较两个二进制文件的体验非常直观。

### 3. Python 二进制模板系统

这是整个编辑器最核心的差异化能力。你可以写一个 Python 函数来**解析任意二进制格式**：

```python
# 示例：解析 PNG 文件头
from freeorbit.template.fields import FieldNode

def build_field_tree(model):
    sig = model.read(0, 8)
    if sig[:4] != b'\x89PNG':
        return []
    return [
        FieldNode("signature", 0, "bytes", length=8),
        FieldNode("width",     8,  "u32be"),
        FieldNode("height",   12,  "u32be"),
        FieldNode("bit_depth", 16, "u8"),
        FieldNode("color_type",17, "u8"),
    ]
```

模板会自动挂载到结构树面板，双击字段即可跳转到对应字节，支持标量类型的**就地编辑写回**。

内置了 PE DOS Header、PNG、JPEG、MP4、MP3、GIF、WebP、ZIP、PDF 等常见格式的解析模板。设置中可配置 **扩展名/Magic 自动匹配规则**，打开文件时自动应用对应模板。

### 4. 内嵌 Python 脚本引擎

脚本面板提供了一个受限的 Python 执行环境，暴露 `EditorAPI` 接口：

```python
# 将当前文件所有字节翻转
data = editor.read(0, editor.cursor())
editor.write(0, data[::-1])
editor.message("Done!")
```

支持代码编辑器、输出日志窗口。虽然目前接口不如 010 Editor 的 350+ 函数丰富，但 Python 本身就是最强大的脚本语言——你可以直接在脚本中写正则、调算法、做数据分析。

### 5. Capstone 多架构反汇编

选中任意字节范围，切换架构（x86/x64/ARM/ARM64/MIPS/RISC-V），即可在反汇编面板中查看指令序列。导出功能支持将反汇编结果保存为文本文件。

### 6. Windows 进程内存编辑（类 Cheat Engine）

打开正在运行的进程，直接浏览和编辑其内存空间。左侧地址列会显示 **模块名 + RVA 偏移**，类 Cheat Engine 体验。支持 F5 刷新外部缓冲。

还支持**原始磁盘/卷**的打开与编辑（需管理员权限）。

### 7. Android Frida 调试（可选）

通过 **窗口 → Android 调试面板**，可以：

- ADB 连接设备，查看包名、进程列表、执行 Shell 命令
- 注入 Frida GumJS 脚本到目标进程
- 内存 Dump 到新标签页进行分析
- JS/TS 脚本编辑器带**语法高亮**

这是 010 Editor 甚至不具备的能力。

### 8. 更多工具

- **ORF 滑窗分析**：将字节流按宽度解释为标量（u8/u16/u32/f32 等），支持范围筛选、相位分组、偏移分布直方图
- **字节运算面板**：范围填充、AND/OR/XOR/NOT、ROL、16/32 位字节交换
- **书签面板**：命名书签、JSON 导入导出、筛选搜索
- **校验和/哈希**：MD5、SHA-1、SHA-256、SHA-512、CRC32、Adler-32
- **十六进制文本导入**

---

## 技术架构

| 层 | 技术选型 |
|----|----------|
| **UI 框架** | PySide6（Qt 6 官方 Python 绑定） |
| **主题系统** | Qt Fusion 风格 + 深色/浅色双 QPalette + 全局 QSS |
| **数据模型** | `BinaryDataModel`：`bytearray` 内存模式 / `mmap` 大文件模式 |
| **大文件** | `mmap.ACCESS_WRITE`（可写映射），插入/删除时自动 `ensure_mutable_copy` 切换到内存 |
| **反汇编** | Capstone 5.x（ctypes 绑定） |
| **图标** | QtAwesome（Font Awesome 5 Free） |
| **打包** | Nuitka `--onefile`，单文件 EXE 约 57 MB（zstd 压缩） |
| **测试** | pytest |
| **代码质量** | ruff |

### 项目结构

```
src/freeorbit/
├── app.py                 # 应用入口、高 DPI、主题应用
├── main_window.py         # 主窗口、菜单、工具栏、停靠面板管理
├── theme.py               # 主题系统（深色/浅色调色板、全局 QSS、字体工具）
├── model/
│   └── binary_data_model.py  # 数据模型（bytearray + mmap）
├── view/
│   ├── hex_editor_view.py    # 十六进制主视图（自绘 QPainter 画布）
│   └── hex_format.py         # 十六进制转储格式化
├── viewmodel/
│   └── document_editor.py    # 单文档编辑器（模型 + 视图 + 撤销栈）
├── services/
│   ├── compare_view.py           # 双文件比较窗口（分栏 + 对比矩阵）
│   ├── compare_matrix_widget.py  # 字节级对比矩阵（Dot Plot）
│   ├── search.py                 # 异步搜索与结果面板
│   ├── disasm_dock.py            # 反汇编面板
│   ├── byte_tools_dock.py        # 字节运算面板
│   ├── checksum_dialog.py        # 校验和/哈希对话框
│   ├── orf_window.py             # ORF 滑窗分析
│   ├── script_runner.py          # Python 脚本面板
│   ├── bookmarks.py              # 书签面板
│   ├── frida_script_highlighter.py  # JS/TS 语法高亮
│   └── android_debug_window.py   # Android ADB + Frida 面板
├── template/
│   ├── fields.py             # FieldNode 数据结构与类型编码
│   ├── builders.py           # 模板构建辅助工厂
│   ├── structure_dock.py     # 结构树停靠面板
│   ├── auto_template.py      # 扩展名/Magic 自动匹配引擎
│   └── builtin_templates.py  # 内置模板枚举
├── dialogs/                  # 各类对话框
├── commands/                 # 撤销/重做编辑命令
└── platform/                 # 平台相关代码（Windows 进程/磁盘、ADB、提权）
```

---

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/privateAccountOfLiu/FreeOrBit.git
cd FreeOrBit

# 安装依赖
pip install -e ".[dev]"

# 运行
python main.py
```

Windows 下打包为单文件 EXE：

```powershell
pip install -e ".[build]"
.\build_nuitka.ps1
# 输出：build/FreeOrBit.exe（约 57 MB）
```
或者直接到git仓库下载单文件exe发行版！：
### [github下载链接](https://github.com/privateAccountOfLiu/FreeOrBit/releases)


---

## 与 010 Editor 的对比

| 功能领域 | FreeOrBit | 010 Editor |
|----------|-----------|------------|
| **基础十六进制编辑** | 完整（插入/覆盖/撤销/书签/跳转） | 完整 |
| **深色/浅色主题** | 支持，设置中切换 | 支持 |
| **二进制模板** | Python 模板系统，自动匹配 | C-like .bt 模板，300+ 在线库 |
| **脚本引擎** | Python 嵌入（~15 API） | 专用 .1sc 语言（350+ 函数） |
| **反汇编** | Capstone（x86/x64/ARM/ARM64/MIPS/RISC-V） | Capstone（更多架构） |
| **文件对比** | 分栏 + 字节矩阵 Dot Plot | 分栏 + 智能对齐 + 三向合并 |
| **进程内存编辑** | Windows 支持（模块名+RVA） | 支持 |
| **Android Frida** | **独有**（ADB + Frida + 内存 Dump） | 不支持 |
| **数据导览器** | 待实现 | 实时多类型解读 |
| **价格** | **免费开源** | $50-$130 |

FreeOrBit 在 Python 脚本灵活性、Android 调试集成方面有独特优势；010 Editor 在模板生态、脚本函数库、搜索替换方面更加成熟。

---

## 路线图

近期规划的功能优先级：

1. **数据导览面板（Inspector）** —— 光标处字节实时解读为 u8/u16/u32/u64/f32/f64/string
2. **替换功能** —— 十六进制/ASCII 搜索替换
3. **数值搜索** —— 按整数/浮点数范围搜索
4. **增强模板** —— 位域、联合体、枚举下拉框、`#include` 支持
5. **更多内置模板** —— ELF、BMP、WebP、FLAC 等
6. **右键上下文菜单** —— 复制为 C 数组 / Python bytes / Base64

---

## 参与贡献

本项目使用 **Apache License 2.0** 开源。欢迎提交 Issue 和 PR。

如果你擅长：
- **Python / PySide6**：改进 UI、新增工具面板
- **二进制分析**：贡献文件格式解析模板
- **逆向工程**：增强反汇编面板、Frida 集成
- **测试/文档**：补充测试用例、完善文档

欢迎一起把 FreeOrBit 打造成最好的开源 Hex Editor。

---

> 项目地址：[github.com/privateAccountOfLiu/FreeOrBit](https://github.com/privateAccountOfLiu/FreeOrBit)
>
> 作者：PrivateLiu
>
> 许可：Apache License 2.0
