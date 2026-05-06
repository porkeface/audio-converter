"""QQ 音乐 mflac 格式处理器。"""

from itertools import cycle
from pathlib import Path
from typing import Optional

from .base import AudioFormat

MFLAC_HEADER_SIZE = 192


def xor_bytes(data: bytes, key: bytes) -> bytes:
    """使用密钥对数据进行 XOR 解密（优化版本）。

    使用 itertools.cycle 循环密钥，避免手动索引计算。

    Args:
        data: 要解密的数据。
        key: XOR 密钥。

    Returns:
        解密后的数据。
    """
    return bytes(a ^ b for a, b in zip(data, cycle(key)))


class MflacFormat(AudioFormat):
    """
    QQ 音乐 mflac 格式：[192-byte header][XOR 加密 FLAC 数据][尾部标记]

    解密方式：
    1. 提供密钥流（从 mflac/flac 对提取）
    2. 通过 Frida 注入 QQ 音乐进程（需要 QQ 音乐运行）
    """

    MAGIC_BYTES = b""  # mflac 无固定魔数
    FORMAT_NAME = "QQ Music mflac"

    def __init__(self, file_path: str, key: Optional[bytes] = None) -> None:
        super().__init__(file_path)
        self._key = key
        self._decrypted_data: Optional[bytes] = None

    def detect(self) -> bool:
        """通过扩展名和文件结构检测（支持 .mflac 和 .mgg）。"""
        if self.file_path.suffix.lower() not in ('.mflac', '.mgg'):
            return False
        return self.file_path.stat().st_size > MFLAC_HEADER_SIZE + 30

    def decrypt(self) -> bytes:
        """解密 mflac 文件。

        需要密钥流才能离线解密，否则请使用 Frida 方式。

        Returns:
            解密后的音频数据。

        Raises:
            ValueError: 如果没有设置密钥。
        """
        if self._decrypted_data is not None:
            return self._decrypted_data

        data = self.read_file()
        encrypted = data[MFLAC_HEADER_SIZE:]

        if self._key is None:
            raise ValueError(
                "mflac 离线解密需要密钥流。\n"
                "请使用以下方式之一：\n"
                "  1. 提供密钥文件: python -m src.main convert file.mflac -k key.bin\n"
                "  2. 通过 Frida 解密: python -m src.formats.frida_decrypt file.mflac\n"
                "  3. 使用 sunwoo.exe 转换"
            )

        self._decrypted_data = xor_bytes(encrypted, self._key)
        return self._decrypted_data

    def extract_key_from_pair(self, flac_path: str) -> bytes:
        """从 mflac 和对应的 flac 提取密钥流。

        通过 XOR 运算从加密数据和已知明文恢复密钥流。

        Args:
            flac_path: 对应的 FLAC 文件路径。

        Returns:
            提取的密钥流。
        """
        mflac_data = self.read_file()
        with open(flac_path, 'rb') as f:
            flac_data = f.read()

        encrypted = mflac_data[MFLAC_HEADER_SIZE:]
        min_len = min(len(encrypted), len(flac_data))
        self._key = xor_bytes(encrypted[:min_len], flac_data[:min_len])
        return self._key

    def set_key(self, key: bytes) -> None:
        """设置解密密钥流。

        Args:
            key: 密钥流字节数据，通常从 mflac/flac 对提取。
        """
        self._key = key

    def get_format_info(self) -> dict:
        """获取格式信息。

        Returns:
            包含格式信息的字典。
        """
        size = self.file_path.stat().st_size
        return {
            "format": "mflac",
            "platform": "QQ 音乐",
            "encryption": "XOR 流加密",
            "file_path": str(self.file_path),
            "file_size": size,
            "header_size": MFLAC_HEADER_SIZE,
            "encrypted_size": size - MFLAC_HEADER_SIZE - 30,
        }
