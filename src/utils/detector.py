"""
音频格式检测工具

这个模块演示了如何通过文件头来识别各种音频格式。
文件头（magic bytes）就像是文件的"身份证"，告诉我们这是什么格式。
"""

from pathlib import Path
from typing import Optional, Type
from ..formats.base import AudioFormat
from ..formats.ncm import NCMFormat


# 格式注册表：将所有支持的格式注册到这里
SUPPORTED_FORMATS = [
    NCMFormat,
    # 未来可以添加更多格式：
    # QMCFormat,
    # KugouFormat,
    # KuwoFormat,
]


def detect_format(file_path: str) -> Optional[AudioFormat]:
    """
    检测文件格式并返回对应的处理器

    这是工厂模式（Factory Pattern）的应用：
    根据输入创建合适的对象。

    参数:
        file_path: 文件路径

    返回:
        AudioFormat 对象，如果不支持则返回 None
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 尝试每种格式
    for format_class in SUPPORTED_FORMATS:
        try:
            # 创建格式对象
            fmt = format_class(str(file_path))

            # 检测是否是这种格式
            if fmt.detect():
                print(f"✓ 检测到格式: {fmt.FORMAT_NAME}")
                return fmt
        except Exception as e:
            # 如果检测失败，继续尝试下一种格式
            continue

    # 检查是否是标准音频格式
    if is_standard_audio(file_path):
        print(f"✓ 检测到标准音频格式")
        return None  # 标准格式不需要特殊处理

    print("✗ 未识别的格式")
    return None


def is_standard_audio(file_path: Path) -> bool:
    """
    检查是否是标准音频格式（不需要解密）

    参数:
        file_path: 文件路径

    返回:
        True 如果是标准音频格式
    """
    with open(file_path, 'rb') as f:
        header = f.read(16)

    # FLAC
    if header[:4] == b"fLaC":
        return True

    # MP3
    if header[:3] == b"ID3" or header[:2] in [b'\xff\xfb', b'\xff\xfa']:
        return True

    # WAV
    if header[:4] == b"RIFF":
        return True

    # AAC
    if header[:4] == b"ADIF" or header[:2] == b'\xff\xf1':
        return True

    return False


def get_file_info(file_path: str) -> dict:
    """
    获取文件信息

    参数:
        file_path: 文件路径

    返回:
        文件信息字典
    """
    path = Path(file_path)

    info = {
        "file_name": path.name,
        "file_size": path.stat().st_size,
        "file_extension": path.suffix,
    }

    # 读取文件头
    with open(path, 'rb') as f:
        header = f.read(16)
        info["header_hex"] = header.hex()

    return info


# 教学示例
if __name__ == "__main__":
    print("=== 格式检测演示 ===\n")

    print("常见音频格式的文件头：")
    print("  FLAC: fLaC")
    print("  MP3:  ID3 或 FFFB")
    print("  WAV:  RIFF")
    print("  NCM:  CTENFDAM")
    print()

    print("使用方法：")
    print("  from src.utils.detector import detect_format")
    print("  fmt = detect_format('song.ncm')")
    print("  if fmt:")
    print("      data = fmt.decrypt()")
