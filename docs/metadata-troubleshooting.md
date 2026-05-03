# NCM 转换元数据显示问题排查与修复

## 问题描述

使用 audio-converter 将 NCM（网易云加密音频）转换为 FLAC/MP3 后，出现两个问题：

1. **GUI 显示"失败"**：文件已成功转换并可正常播放，但界面上显示红色"失败"标记
2. **部分文件无元数据**：转换后的音频文件在 Windows 资源管理器中不显示歌曲名、艺术家、专辑等信息

## 根本原因分析

### 问题一：GUI 显示"失败"

**原因**：`_embed_audio_metadata()` 函数末尾存在一段复制粘贴遗留的死代码。

```python
# 旧代码 (main.py 第 269-278 行)
except Exception as e:
    print(f"[-] 写入元数据失败（不影响音频）: {e}")
    if isinstance(a, list):       # ← 变量 a 未定义
        names.append(a[0])        # ← 变量 names 未定义
    else:
        names.append(str(a))
if names:                         # ← 变量 names 未定义
    parts.append(', '.join(names))# ← 变量 parts 未定义
album = meta.get('album')
if album:
    parts.append(album)
return ' · '.join(parts)          # ← 这段代码来自 get_metadata_str()，被错误地拼接到了 _embed_audio_metadata()
```

这段代码引用了 `a`、`names`、`parts` 等未定义变量，导致每次执行都会抛出 `NameError`。异常向上传播到 `convert_file()`（第 78 行没有 try/except 包裹），最终被 UI 的 `_conversion_worker` 外层 try/except 捕获，标记为"失败"。

**修复**：删除死代码，确保 `_embed_audio_metadata()` 在元数据写入失败时不影响转换结果。

### 问题二：部分文件无元数据

**原因**：NCM 文件包含**两个独立的元数据来源**：

| 来源 | 说明 | 示例 |
|------|------|------|
| NCM JSON 元数据 | 加密在 NCM 文件头中，解密后可提取 | `musicName`、`artist`、`album` |
| 音频流内嵌标签 | FLAC 的 Vorbis Comments / MP3 的 ID3 Tags | 已嵌入在音频数据本身中 |

三个测试文件的情况：

| 文件 | NCM JSON 元数据 | 音频流内嵌标签 | 原始格式 |
|------|----------------|---------------|---------|
| G.E.M.邓紫棋 - 来自天堂的魔鬼 | 有（name/artist/album） | 无 | FLAC |
| Pianoboy高至豪 - The Truth that You Leave | 有 | 有（Vorbis Comments） | **MP3** |
| 菲菲公主 - 第57次取消发送 | 有 | 有（Vorbis Comments） | **MP3** |

关键发现：Pianoboy 和 菲菲公主 的原始格式是 **MP3**，但 GUI 选择输出格式为 FLAC，导致：

- 解密后的音频数据是 MP3 格式（以 `ID3` 头开头）
- 文件被保存为 `.flac` 扩展名
- mutagen 使用 `ID3` 标签写入（因为实际数据是 MP3）
- **Windows 资源管理器只从 `.flac` 文件读取 Vorbis Comments，忽略 ID3 标签**
- 结果：ID3 标签已写入但不可见

## 技术原理

### Windows 资源管理器的元数据读取规则

```
文件扩展名        读取的标签格式         忽略的标签格式
─────────────    ─────────────────     ─────────────────
.flac            Vorbis Comments       ID3 Tags
.mp3             ID3 Tags              Vorbis Comments
.wav             RIFF Info / ID3       Vorbis Comments
```

这意味着：**文件扩展名必须与实际音频格式匹配**，否则操作系统无法正确读取元数据。

### mutagen 库的格式检测

```python
import mutagen
audio = mutagen.File("song.flac")  # 根据文件内容（非扩展名）检测格式
# 如果文件内容是 MP3 → 返回 mutagen.mp3.MP3 对象
# 如果文件内容是 FLAC → 返回 mutagen.flac.FLAC 对象
```

`mutagen.File()` 根据文件头魔数（magic bytes）检测格式，而非扩展名。但写入标签时：
- `mutagen.mp3.MP3` 只能写 ID3 标签
- `mutagen.flac.FLAC` 只能写 Vorbis Comments

## 修复方案

### 1. 根据实际音频数据检测格式

添加 `_detect_audio_format_data()` 函数，从解密后的音频数据头几个字节判断真实格式：

```python
def _detect_audio_format_data(data: bytes) -> str:
    if data[:4] == b'fLaC':
        return 'flac'
    if data[:3] == b'ID3' or data[:2] == b'\xff\xfb':
        return 'mp3'
    if data[:4] == b'RIFF':
        return 'wav'
    return 'flac'
```

### 2. 输出文件使用正确扩展名

在 `convert_file()` 中，根据实际格式设置输出文件扩展名：

```python
actual_ext = _detect_audio_format_data(data)
if output_file is None:
    output_file = str(fmt.file_path.parent / (fmt.file_path.stem + '.' + actual_ext))
else:
    out_path = Path(output_file)
    if out_path.suffix.lower() != '.' + actual_ext:
        output_file = str(out_path.with_suffix('.' + actual_ext))
        print(f"实际格式为 {actual_ext}，输出文件: {output_file}")
```

### 3. 使用 mutagen.File() 自动适配标签格式

```python
audio = mutagen.File(output_path, easy=False)

if isinstance(audio, mutagen.flac.FLAC):
    # 写入 Vorbis Comments
    audio['title'] = [title]
    audio['artist'] = [artist]
    audio['album'] = [album]
    audio.add_picture(pic)  # 封面
    audio.save()

elif isinstance(audio, mutagen.mp3.MP3):
    # 写入 ID3 标签
    audio.tags.add(TIT2(encoding=3, text=[title]))
    audio.tags.add(TPE1(encoding=3, text=[artist]))
    audio.tags.add(TALB(encoding=3, text=[album]))
    audio.tags.add(APIC(encoding=3, ...))  # 封面
    audio.save()
```

### 4. 避免破坏已有标签

如果 NCM JSON 元数据为空（`{}` 或只有 `format` 字段），跳过写入，保留音频流中已有的 Vorbis/ID3 标签：

```python
has_useful_meta = meta and (meta.get('musicName') or meta.get('artist') or meta.get('album'))
if not has_useful_meta and not cover:
    return  # 不调用 mutagen，避免破坏已有标签
```

## 修复后的文件命名规则

| 原始格式 | 输出文件 | 原因 |
|---------|---------|------|
| FLAC | `song.flac` | 格式匹配，直接写入 |
| MP3 | `song.mp3` | 使用正确扩展名，Windows 可读取 ID3 标签 |
| WAV | `song.wav` | 格式匹配 |

## 验证方法

转换完成后，右键点击输出文件 → 属性 → 详细信息，检查：

- 标题（Title）
- 参与创作的艺术家（Artist）
- 唱片集（Album）
- 唱片集封面（Cover Art）

如果仍无元数据，检查：
1. 输出文件的实际格式是否正确（用 `file` 命令或十六进制编辑器查看文件头）
2. 文件扩展名是否与实际格式匹配
3. 查看控制台输出是否有 `[+] 已写入 FLAC/MP3 元数据` 或 `[-] 写入元数据失败` 日志
