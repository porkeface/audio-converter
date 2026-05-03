# Bug Fix: 默认格式输出文件名被截断

## 问题描述

### 现象
选择"默认"格式转换 NCM 文件时，输出文件名被错误截断。

**输入文件**: `G.E.M.邓紫棋 - 来自天堂的魔鬼.ncm`

**预期输出**: `G.E.M.邓紫棋 - 来自天堂的魔鬼.flac`

**实际输出**: `G.E.M.flac`（文件名被截断）

---

## 根因分析

### 核心问题：Python `Path.stem` / `Path.suffix` 对含点号文件名的处理

Python 的 `pathlib.Path` 在处理文件名时，会将**最后一个点号**之后的部分视为扩展名。

```
Path("G.E.M.邓紫棋 - 来自天堂的魔鬼").suffix  → ".邓紫棋 - 来自天堂的魔鬼"
Path("G.E.M.邓紫棋 - 来自天堂的魔鬼").stem    → "G.E.M"
```

这导致两个地方出错：

### 问题点 1：`ui.py` 中构建输出路径

```python
# 原代码（已验证正确，因为 .ncm 会被正确识别为扩展名）
output_path = str(Path(final_out) / Path(path).stem)
# Path("G.E.M.邓紫棋 - 来自天堂的魔鬼.ncm").stem → "G.E.M.邓紫棋 - 来自天堂的魔鬼" ✓
```

`ui.py` 这里实际上没问题，因为输入文件有 `.ncm` 扩展名，`Path.stem` 能正确去除。

### 问题点 2：`main.py` 中修正扩展名逻辑

```python
# 原代码
out_path = Path(output_file)
if out_path.suffix.lower() != '.' + actual_ext:
    output_file = str(out_path.with_suffix('.' + actual_ext))
```

当 `output_file = "D:\...\out\G.E.M.邓紫棋 - 来自天堂的魔鬼"`（无扩展名）时：
- `out_path.suffix` = `".邓紫棋 - 来自天堂的魔鬼"`（被误认为扩展名）
- `out_path.with_suffix('.flac')` 内部调用 `stem`，得到 `"G.E.M"`
- 最终结果：`"G.E.M.flac"` ✗

### 第一次修复尝试（失败）

```python
if out_path.suffix:
    base_name = out_path.stem    # ← 问题：Path.stem 仍然错误截断
else:
    base_name = out_path.name
```

失败原因：`out_path.suffix` 为 `".邓紫棋 - 来自天堂的魔鬼"`（非空），所以走了 `if` 分支，`out_path.stem` 仍然返回 `"G.E.M"`。

### 第二次修复尝试（失败）

```python
last_dot = output_file.rfind('.')
if last_dot > 0 and output_file[last_dot:].lower() in known_exts:
    output_file = output_file[:last_dot] + '.' + actual_ext
else:
    output_file = output_file + '.' + actual_ext
```

失败原因：`output_file.rfind('.')` 在**整个路径字符串**上查找，会匹配到路径中其他点号。

---

## 最终修复方案

### 原则
不使用 `Path.stem`、`Path.suffix`、`str.rfind('.')` 等会在整个路径/文件名上操作的方法。改为：**只在文件名部分**查找已知扩展名。

### 修改文件：`src/main.py`

```python
# 根据实际音频数据检测格式，确定正确的文件扩展名
actual_ext = _detect_audio_format_data(data)
if output_file is None:
    output_file = str(fmt.file_path.parent / (fmt.file_path.stem + '.' + actual_ext))
else:
    if not output_file.lower().endswith('.' + actual_ext):
        # 只在文件名部分查找点号，避免匹配父目录中的点号
        fname = Path(output_file).name
        known_exts = {'.flac', '.mp3', '.wav', '.ogg', '.m4a', '.ncm', '.mflac', '.mgg', '.tmp'}
        last_dot = fname.rfind('.')
        if last_dot > 0 and fname[last_dot:].lower() in known_exts:
            output_file = str(Path(output_file).parent / (fname[:last_dot] + '.' + actual_ext))
        else:
            output_file = output_file + '.' + actual_ext
```

**关键改动**：
1. 用 `Path(output_file).name` 提取纯文件名（不含路径）
2. 在文件名上用 `rfind('.')` 查找点号
3. 检查点号后的部分是否为已知扩展名，避免误匹配文件名中的点号

### 修改文件：`src/ui.py`

```python
# 添加"默认"格式选项
for i, fmt in enumerate(["默认", "flac", "mp3", "wav", "m4a"]):
    rb = ctk.CTkRadioButton(...)

# 默认值改为"默认"
self.output_format = ctk.StringVar(value="默认")

# 转换逻辑中，"默认"时不添加扩展名
fmt_choice = self.output_format.get()
if fmt_choice == "默认":
    output_path = str(Path(final_out) / Path(path).stem)
else:
    output_path = str(Path(final_out) / f"{Path(path).stem}.{fmt_choice}")
```

---

## 验证

对含点号文件名的处理逻辑：

| 输入文件名 | `Path.stem` | `fname.rfind('.')` | `fname[last_dot:]` | 结果 |
|---|---|---|---|---|
| `G.E.M.邓紫棋.ncm` | `G.E.M.邓紫棋` | 5 | `.邓紫棋` | `G.E.M.邓紫棋.flac` ✓ |
| `song.mp3` | `song` | 4 | `.mp3` | `song.flac` ✓ |
| `normal_file.ncm` | `normal_file` | -1 | — | `normal_file.flac` ✓ |

---

## Bug 2: mflac/mgg 二次转换失败 + 无扩展名残留文件

### 现象
mflac/mgg 文件第一次转换成功，第二次转换失败，且输出目录出现无扩展名的残留文件。

### 根因
1. **Frida `CreateFileW` 使用 `CREATE_ALWAYS` 标志** — 即使解密失败也会在磁盘上创建文件
2. **Windows 上 `os.rename` 不覆盖已有文件** — 第二次重命名时目标 `.flac` 已存在，抛出 `FileExistsError`，导致无扩展名文件残留

### 修复
- 解密失败时清理残留文件
- `os.rename` → `os.replace`（跨平台原子覆盖）

---

## Bug 3: 选择非"默认"格式时输出仍为原始格式

### 现象
用户选择 `mp3`/`flac`/`wav`/`m4a` 格式，但输出文件仍然是加密文件内部的原始格式（如 NCM 内部是 flac，选 mp3 输出仍是 flac）。

### 根因
`convert_file` 检测到实际格式后，直接用实际格式覆盖用户选择的扩展名，**没有调用 FFmpeg 转码**。

### 修复
在 `convert_file` 和 `frida_convert` 中添加 FFmpeg 转码逻辑：

```python
need_convert = desired_ext is not None and desired_ext != actual_ext

if need_convert:
    # 先写入临时文件，再用 FFmpeg 转换
    tmp_path = output_file + '.tmp.' + actual_ext
    with open(tmp_path, 'wb') as f:
        f.write(data)
    from src.utils.converter import convert_audio
    if convert_audio(tmp_path, output_file, desired_ext):
        os.remove(tmp_path)
    else:
        # 转换失败，保留实际格式
        os.replace(tmp_path, fallback)
```

---

## Bug 4: mflac/mgg FFmpeg 报错 "Output same as Input"

### 现象
mflac/mgg 文件选择非"默认"格式（如 mp3）时，FFmpeg 报错：
```
Output same as Input #0 - exiting.
FFmpeg cannot edit existing files in-place.
```

### 根因
`frida_convert` 将 `output_file`（如 `song.mp3`）直接传给 `decode_mflac`，Frida 解密后将 FLAC 数据写入 `song.mp3`。
然后调用 `convert_audio("song.mp3", "song.mp3", "mp3")`，输入和输出是同一个文件，FFmpeg 不支持原地编辑。

### 修复
Frida 始终写入临时文件（`base_name.tmp.frida`），FFmpeg 再从临时文件转换为最终格式：

```python
# Frida 写入临时文件
frida_output = str(out_parent / (base_name + '.tmp.frida'))
success, result = decode_mflac(input_file, frida_output)

# FFmpeg 从临时文件转换为用户期望的格式（输入 ≠ 输出）
final_path = str(final_dir / (base_name + '.' + desired_ext))
convert_audio(result, final_path, desired_ext)
```

---

## 经验总结

1. **不要在含路径的字符串上做文件名操作** — 先用 `Path.name` 提取纯文件名
2. **Python `Path.stem` 不等于"去掉扩展名"** — 它只去掉最后一个点号后的部分，对含多个点号的文件名会截断
3. **Python 缓存问题** — 修改代码后如果行为未变，先清除 `__pycache__`
4. **Windows 上 `os.rename` 不覆盖已有文件** — 用 `os.replace` 代替
5. **格式选择 ≠ 扩展名修改** — 需要实际调用 FFmpeg 转码
6. **FFmpeg 不能原地编辑** — 输入和输出必须是不同文件，否则报 "Output same as Input"
7. **需要转码时，解密工具应写入临时文件** — FFmpeg 从临时文件转换为最终格式，避免输入输出冲突
