"""音频格式检测工具"""

from pathlib import Path
from typing import Optional, Type

from ..formats.base import AudioFormat
from ..formats.ncm import NCMFormat
from ..formats.mflac import MflacFormat


# 格式注册表
SUPPORTED_FORMATS = [
    NCMFormat,
    MflacFormat,
]


def detect_format(file_path: str) -> Optional[AudioFormat]:
    """检测文件格式并返回对应的处理器。"""
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    for format_class in SUPPORTED_FORMATS:
        try:
            fmt = format_class(str(file_path))
            if fmt.detect():
                return fmt
        except Exception:
            continue

    if is_standard_audio(file_path):
        return None

    return None


def is_standard_audio(file_path: Path) -> bool:
    """检查是否是标准音频格式（不需要解密）。"""
    with open(file_path, 'rb') as f:
        header = f.read(4)

    if header == b"fLaC":
        return True
    if header[:3] == b"ID3" or header[:2] in [b'\xff\xfb', b'\xff\xfa']:
        return True
    if header == b"RIFF":
        return True
    if header == b"OggS":
        return True
    if header == b"ADIF" or header[:2] == b'\xff\xf1':
        return True

    return False
