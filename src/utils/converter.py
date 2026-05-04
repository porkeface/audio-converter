"""
音频转码工具

这个模块演示了如何使用 FFmpeg 进行音频格式转换。
FFmpeg 是最强大的音视频处理工具，几乎所有播放器和转换器都在用它。

学习要点：
1. FFmpeg 的基本用法
2. 如何使用 Python 调用外部工具
3. 不同音频格式的特点
"""

import subprocess
from pathlib import Path
from typing import Optional

# 防止 subprocess 弹出命令行窗口（GUI 应用必需）
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

# FFmpeg 路径：优先使用项目目录下的，其次使用系统 PATH
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_FFMPEG_DIR = _PROJECT_ROOT / "vendor" / "ffmpeg"
FFMPEG_PATH = str(_FFMPEG_DIR / "ffmpeg.exe") if _FFMPEG_DIR.joinpath("ffmpeg.exe").exists() else "ffmpeg"
FFPROBE_PATH = str(_FFMPEG_DIR / "ffprobe.exe") if _FFMPEG_DIR.joinpath("ffprobe.exe").exists() else "ffprobe"


def check_ffmpeg() -> bool:
    """检查 FFmpeg 是否可用。"""
    try:
        subprocess.run(
            [FFMPEG_PATH, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            creationflags=_NO_WINDOW,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def convert_audio(
    input_file: str,
    output_file: str,
    output_format: Optional[str] = None,
    bitrate: str = "320k",
    sample_rate: str = "44100"
) -> bool:
    """
    转换音频格式

    使用 FFmpeg 进行转换。FFmpeg 是一个命令行工具，
    我们通过 subprocess 调用它。

    参数:
        input_file: 输入文件路径
        output_file: 输出文件路径
        output_format: 输出格式（如 'flac', 'mp3'），如果为 None 则从文件名推断
        bitrate: 比特率（用于有损格式如 MP3）
        sample_rate: 采样率

    返回:
        True 如果转换成功
    """
    input_path = Path(input_file)
    output_path = Path(output_file)

    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_file}")

    # 检查 FFmpeg
    if not check_ffmpeg():
        print("✗ FFmpeg 未安装！")
        print("请安装 FFmpeg:")
        print("  Windows: https://ffmpeg.org/download.html")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: sudo apt install ffmpeg")
        return False

    # 构建 FFmpeg 命令
    cmd = [
        FFMPEG_PATH,
        "-i", str(input_path),  # 输入文件
        "-y",  # 覆盖输出文件
    ]

    # 根据输出格式设置参数
    if output_format == "mp3" or output_path.suffix == ".mp3":
        # MP3 设置
        cmd.extend([
            "-codec:a", "libmp3lame",  # MP3 编码器
            "-b:a", bitrate,  # 比特率
            "-ar", sample_rate,  # 采样率
        ])
    elif output_format == "flac" or output_path.suffix == ".flac":
        # FLAC 设置（无损）
        cmd.extend([
            "-codec:a", "flac",  # FLAC 编码器
        ])
    elif output_format == "wav" or output_path.suffix == ".wav":
        # WAV 设置
        cmd.extend([
            "-codec:a", "pcm_s16le",  # WAV 编码器
        ])
    elif output_format == "m4a" or output_path.suffix == ".m4a":
        # M4A (AAC) 设置
        cmd.extend([
            "-codec:a", "aac",  # AAC 编码器
            "-b:a", bitrate,
        ])

    # 输出文件
    cmd.append(str(output_path))

    print(f"执行命令: {' '.join(cmd)}")

    try:
        # 执行转换
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            creationflags=_NO_WINDOW,
        )
        print(f"✓ 转换成功: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 转换失败: {e.stderr}")
        return False


def get_audio_info(file_path: str) -> dict:
    """
    获取音频文件信息（使用 ffprobe）

    参数:
        file_path: 音频文件路径

    返回:
        音频信息字典
    """
    try:
        cmd = [
            FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            creationflags=_NO_WINDOW,
        )

        import json
        info = json.loads(result.stdout)
        return info
    except Exception as e:
        print(f"获取音频信息失败: {e}")
        return {}


# 教学示例
if __name__ == "__main__":
    print("=== 音频转码演示 ===\n")

    print("FFmpeg 基本命令示例：")
    print()
    print("# 转换 MP3 到 FLAC")
    print("ffmpeg -i input.mp3 output.flac")
    print()
    print("# 转换时指定比特率")
    print("ffmpeg -i input.wav -b:a 320k output.mp3")
    print()
    print("# 获取音频信息")
    print("ffprobe -show_format input.mp3")
    print()

    if check_ffmpeg():
        print("✓ FFmpeg 已安装")
    else:
        print("✗ FFmpeg 未安装")
