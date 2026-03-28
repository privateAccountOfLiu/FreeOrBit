# 用户结构模板（常见文件头）

本目录为 **FreeOrBit** 可加载的 Python 结构模板：入口函数为 `build_field_tree(model)`，返回 `list[FieldNode]`。

| 文件 | 格式 | 说明 |
|------|------|------|
| `png.py` | PNG | 签名 + IHDR（宽高、位深、颜色类型等） |
| `jpeg.py` | JPEG | SOI + 首段标记与长度 |
| `pdf.py` | PDF | `%PDF-` 首行 |
| `mp4.py` | MP4 / ISO BMFF | 首个顶层盒（常为 `ftyp`）；`size==1` 时解析 64 位扩展长度 |
| `mp3.py` | MP3 | `ID3` 头或 MPEG 帧同步 |
| `gif.py` | GIF | `GIF87a`/`GIF89a` + 逻辑屏幕描述符 |
| `webp.py` | WebP | RIFF + WEBP + 首块头 |
| `zip.py` | ZIP | 本地文件头 `PK\x03\x04`（含 .zip / .docx 等） |

**使用**：结构面板「加载模板…」选择对应 `.py`。若将本目录复制到安装目录下的 `templates\`，可从该路径加载。

另见仓库内 `example_build_field_tree.py` 与包内 `freeorbit/resources/templates/pe_dos_header.py`。
