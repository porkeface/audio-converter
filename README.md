# audio-converter

音频解密工具 — 支持 QQ 音乐 mflac 和网易云音乐 NCM 格式。

## 支持格式

| 格式 | 来源 | 加密方式 | 解密方式 |
|------|------|---------|---------|
| mflac | QQ 音乐 | XOR 流加密 | Frida 注入 / 密钥文件 |
| NCM | 网易云音乐 | RC4 + AES-128-ECB | 纯算法解密 |

## 安装

```bash
cd audio-converter
uv sync
```

## 使用

### 自动检测 + 解密

```bash
# NCM 解密（自动检测原始格式）
python -m src.main convert song.ncm

# mflac 解密（需要密钥文件）
python -m src.main convert song.mflac -k key.bin

# 指定输出文件
python -m src.main convert song.ncm output.flac
```

### Frida 解密（mflac 专用）

```bash
# 需要 QQ 音乐正在运行
python -m src.main frida song.mflac
```

### 批量处理

```bash
# 批量解密目录下所有 .mflac 和 .ncm 文件
python -m src.main batch D:\music\encrypted

# 指定输出目录和密钥
python -m src.main batch D:\input D:\output -k key.bin
```

### 密钥管理

```bash
# 从 mflac/flac 对提取密钥
python -m src.main extract-key song.mflac reference.flac key.bin
```

### 文件分析

```bash
python -m src.main analyze song.ncm
python -m src.main analyze song.mflac
```

### GUI 模式

```bash
python gui.py
# 或双击 run_gui.bat
```

## 项目结构

```
src/
├── main.py              # CLI 入口
├── formats/
│   ├── base.py          # 音频格式基类（ABC）
│   ├── ncm.py           # 网易云 NCM 格式处理器
│   ├── mflac.py         # QQ 音乐 mflac 格式处理器
│   ├── frida_decrypt.py # Frida 注入解密（mflac）
│   └── key_extractor.py # 密钥流提取
├── utils/
│   ├── detector.py      # 格式自动检测
│   └── converter.py     # FFmpeg 转码
└── ui.py               # GUI 界面
```

## 工作原理

### NCM 解密流程

1. 验证文件头 `CTENFDAM`
2. 提取加密密钥 → XOR 0x64 → AES-128-ECB 解密 → 跳过 17 字节得到 RC4 密钥
3. 提取元数据 → XOR 0x63 → Base64 → AES 解密 → JSON
4. 提取专辑封面图片
5. 改进的 RC4 流密码解密音频数据

### mflac 解密流程

mflac 文件结构：`[192-byte header][XOR 加密 FLAC 数据][musicex 尾部标记]`

**方式一：Frida 注入**
1. 注入 QQ 音乐进程
2. 调用 `QQMusicCommon.dll` 的 `EncAndDesMediaFile` API
3. 直接读取解密后的数据

**方式二：密钥文件**
1. 从 mflac/flac 对提取密钥流
2. XOR 解密

## 依赖

| 包 | 用途 |
|----|------|
| pycryptodome | NCM 的 AES/RC4 解密 |
| frida | mflac 的进程注入 |
| frida-tools | Frida CLI 工具 |
