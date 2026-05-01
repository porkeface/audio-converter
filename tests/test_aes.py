"""
AES 加解密测试

这个文件演示了如何为加密模块编写测试。
测试是确保代码正确性的重要手段。
"""

import unittest
import sys
from pathlib import Path

# 添加 src 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crypto.aes import decrypt_aes_128_ecb, encrypt_aes_128_ecb


class TestAES(unittest.TestCase):
    """AES 加解密测试"""

    def test_encrypt_decrypt_ecb(self):
        """测试 AES-128-ECB 加解密"""
        # 准备测试数据
        key = b"1234567890123456"  # 16字节密钥
        original = b"Hello, Audio!123"  # 16字节数据（必须是16的倍数）

        # 加密
        encrypted = encrypt_aes_128_ecb(original, key)

        # 解密
        decrypted = decrypt_aes_128_ecb(encrypted, key)

        # 验证
        self.assertEqual(original, decrypted, "解密后的数据应该和原始数据相同")

    def test_encrypt_decrypt_long_data(self):
        """测试长数据的加解密"""
        key = b"1234567890123456"

        # 创建长数据（必须是16的倍数）
        original = b"A" * 1024  # 1KB 数据

        # 加密
        encrypted = encrypt_aes_128_ecb(original, key)

        # 解密
        decrypted = decrypt_aes_128_ecb(encrypted, key)

        # 验证
        self.assertEqual(original, decrypted)

    def test_different_keys(self):
        """测试不同密钥不能解密"""
        key1 = b"1234567890123456"
        key2 = b"abcdefghijklmnop"  # 不同的密钥

        original = b"Test Data 12345"

        # 用 key1 加密
        encrypted = encrypt_aes_128_ecb(original, key1)

        # 用 key2 解密（应该失败）
        decrypted = decrypt_aes_128_ecb(encrypted, key2)

        # 解密后的数据应该不同
        self.assertNotEqual(original, decrypted)


if __name__ == "__main__":
    unittest.main()
