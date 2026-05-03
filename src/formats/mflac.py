"""QQ 音乐 mflac 格式处理器。"""

from pathlib import Path
from typing import Optional

from .base import AudioFormat

MFLAC_HEADER_SIZE = 192


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
        """
        解密 mflac 文件。

        需要密钥流才能离线解密，否则请使用 Frida 方式。
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

        key_len = len(self._key)
        result = bytearray(len(encrypted))
        for i in range(len(encrypted)):
            result[i] = encrypted[i] ^ self._key[i % key_len]

        self._decrypted_data = bytes(result)
        return self._decrypted_data

    def extract_key_from_pair(self, flac_path: str) -> bytes:
        """从 mflac 和对应的 flac 提取密钥流。"""
        mflac_data = self.read_file()
        with open(flac_path, 'rb') as f:
            flac_data = f.read()

        encrypted = mflac_data[MFLAC_HEADER_SIZE:]
        min_len = min(len(encrypted), len(flac_data))
        self._key = bytes(encrypted[i] ^ flac_data[i] for i in range(min_len))
        return self._key

    def set_key(self, key: bytes) -> None:
        self._key = key

    def get_format_info(self) -> dict:
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
