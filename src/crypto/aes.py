"""
AES 加解密模块 - 教学版本

这个模块演示了如何使用 AES 算法解密音频文件。
AES (Advanced Encryption Standard) 是最常用的对称加密算法。

学习要点：
1. AES 有多种模式：ECB, CBC, GCM 等
2. NCM 使用 AES-128-ECB 模式
3. ECB 模式不需要 IV（初始化向量）， CBC 需要
"""

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64


def decrypt_aes_128_ecb(encrypted_data: bytes, key: bytes) -> bytes:
    """
    AES-128-ECB 解密

    ECB (Electronic Codebook) 模式：
    - 最简单的 AES 模式
    - 每个块独立加密
    - 不需要 IV（初始化向量）

    参数:
        encrypted_data: 加密的数据
        key: 16字节的密钥（AES-128）

    返回:
        解密后的数据
    """
    # 创建 AES 解密器
    cipher = AES.new(key, AES.MODE_ECB)

    # 解密
    decrypted = cipher.decrypt(encrypted_data)

    return decrypted


def decrypt_aes_128_cbc(encrypted_data: bytes, key: bytes, iv: bytes) -> bytes:
    """
    AES-128-CBC 解密

    CBC (Cipher Block Chaining) 模式：
    - 每个块的加密依赖于前一个块
    - 需要 IV（初始化向量）

    参数:
        encrypted_data: 加密的数据
        key: 16字节的密钥
        iv: 16字节的初始化向量

    返回:
        解密后的数据
    """
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(encrypted_data)
    return decrypted


def encrypt_aes_128_ecb(data: bytes, key: bytes) -> bytes:
    """
    AES-128-ECB 加密（用于测试）
    """
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(data)


# 教学示例
if __name__ == "__main__":
    print("=== AES 加解密演示 ===\n")

    # 示例密钥（16字节 = 128位）
    key = b"1234567890123456"  # 实际使用时应该是随机的安全密钥

    # 示例数据（需要是16的倍数）
    original_data = b"Hello, Audio!123"  # 16字节

    print(f"原始数据: {original_data}")

    # 加密
    encrypted = encrypt_aes_128_ecb(original_data, key)
    print(f"加密后: {encrypted.hex()}")

    # 解密
    decrypted = decrypt_aes_128_ecb(encrypted, key)
    print(f"解密后: {decrypted}")

    # 验证
    assert original_data == decrypted, "解密失败！"
    print("\n✓ 加解密成功！")
