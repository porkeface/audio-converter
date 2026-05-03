# Audio Converter

网易云音乐 NCM 加密音频格式转换工具，支持解密并导出为 FLAC/MP3/WAV/M4A。

## 项目结构

```
audio-converter/
├── gui.py              # GUI 启动脚本
├── run_gui.bat         # Windows 快捷启动
├── requirements.txt    # 依赖包
└── src/
    ├── main.py         # CLI 入口
    ├── ui.py           # GUI 界面
    ├── formats/
    │   ├── base.py     # 音频格式基类
    │   └── ncm.py      # NCM 格式解密
    └── utils/
        ├── detector.py # 格式检测
        └── converter.py# FFmpeg 转码
```

## 使用方法

### GUI 模式

```bash
# 双击 run_gui.bat 启动
# 或手动运行
python gui.py
```

支持拖拽上传文件，可批量转换。

### 命令行模式

```bash
# 安装依赖
pip install -r requirements.txt

# 转换单个文件（自动检测原始格式）
python -m src.main song.ncm

# 指定输出文件
python -m src.main song.ncm output.flac

# 指定输出格式
python -m src.main song.ncm -f mp3
```

## 支持的格式

| 输入 | 输出 |
|------|------|
| NCM（网易云音乐） | FLAC、MP3、WAV、M4A |

## 依赖

- `pycryptodome` - AES 解密
- `pydub` - 音频处理
- `mutagen` - 元数据处理
- FFmpeg - 音频转码（需单独安装）
