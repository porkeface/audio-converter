"""
音频格式基类

所有加密音频格式（NCM, QMC, 等）都应该继承这个类。
这演示了面向对象编程中的"多态"概念。
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import struct


class AudioFormat(ABC):
    """
    音频格式基类

    抽象基类（ABC）定义了所有格式必须实现的方法。
    这样可以确保每种格式都有统一的接口。
    """

    # 文件头的魔数（用于识别格式）
    MAGIC_BYTES: bytes = b""

    # 格式名称
    FORMAT_NAME: str = ""

    def __init__(self, file_path: str):
        """
        初始化

        参数:
            file_path: 音频文件路径
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

    def read_file(self) -> bytes:
        """
        读取整个文件内容

        返回:
            文件的二进制数据
        """
        with open(self.file_path, 'rb') as f:
            return f.read()

    def read_file_header(self, size: int = 16) -> bytes:
        """
        读取文件头（用于格式识别）

        参数:
            size: 要读取的字节数

        返回:
            文件头数据
        """
        with open(self.file_path, 'rb') as f:
            return f.read(size)

    @abstractmethod
    def detect(self) -> bool:
        """
        检测文件是否是这种格式

        这是一个抽象方法，子类必须实现。

        返回:
            True 如果是这种格式，否则 False
        """
        pass

    @abstractmethod
    def decrypt(self) -> bytes:
        """
        解密文件，返回原始音频数据

        这是一个抽象方法，子类必须实现。

        返回:
            解密后的音频数据
        """
        pass

    @abstractmethod
    def get_format_info(self) -> dict:
        """
        获取格式信息

        返回:
            包含格式信息的字典
        """
        pass

    def save_decrypted(self, output_path: str, data: Optional[bytes] = None):
        """
        保存解密后的文件

        参数:
            output_path: 输出文件路径
            data: 要保存的数据，如果为 None 则先调用 decrypt()
        """
        if data is None:
            data = self.decrypt()

        with open(output_path, 'wb') as f:
            f.write(data)

        print(f"✓ 文件已保存: {output_path}")

    def __str__(self):
        return f"{self.FORMAT_NAME} Format: {self.file_path.name}"
