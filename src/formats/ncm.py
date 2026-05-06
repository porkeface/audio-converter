"""
网易云音乐 NCM 格式 - 正确实现 (基于 ncmdump)

基于开源 ncmdump 实现: https://github.com/nondanee/ncmdump
作者: Nzix

NCM 文件结构：
├── 8字节: "CTENFDAM" 文件头
├── 2字节: 标志位（跳过）
├── 4字节: 密钥数据长度 (小端序)
├── N字节: 加密的密钥数据 (XOR 0x64)
├── 4字节: 元数据长度 (小端序)
├── M字节: 加密的元数据 (XOR 0x63, Base64, AES)
├── 4字节: 图片空白区域
├── 4字节: 图片大小
├── P字节: 图片数据
└── 剩余: RC4 加密的音频数据

解密流程：
1. 验证文件头
2. 提取并解密 AES 密钥 (XOR 0x64 -> AES-128-ECB -> 移除填充 -> 跳过17字节)
3. 提取并解密元数据 (XOR 0x63 -> Base64解码 -> AES-128-ECB -> JSON)
4. 提取专辑封面图片
5. 用改进的 RC4 流密码解密音频数据
6. 检测原始音频格式并保存
"""

import struct
import base64
import json
from pathlib import Path
from typing import Any, Optional, Dict

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from Crypto.Util.strxor import strxor as XOR

from .base import AudioFormat


class NCMFormat(AudioFormat):
    """
    网易云音乐 NCM 格式处理器 - 正确实现
    """

    MAGIC_BYTES = b"CTENFDAM"
    FORMAT_NAME = "NetEase NCM"

    # 核心密钥 (用于解密密钥数据)
    # 来源: 逆向工程网易云音乐客户端获取
    # 用途: AES-128-ECB 解密 NCM 文件中的加密密钥数据
    # 十六进制: 687A4852416D736F356B496E62617857
    # ASCII: hzHRAmso5kInbaxW
    CORE_KEY = bytes.fromhex('687A4852416D736F356B496E62617857')

    # 元数据密钥 (用于解密元数据)
    # 来源: 逆向工程网易云音乐客户端获取
    # 用途: AES-128-ECB 解密 NCM 文件中的歌曲元数据 (JSON 格式)
    # 十六进制: 2331346C6A6B5F215C5D2630553C2728
    # ASCII: #14ljk_!\]&0U<'
    META_KEY = bytes.fromhex('2331346C6A6B5F215C5D2630553C2728')

    def __init__(self, file_path: str):
        super().__init__(file_path)
        self._decrypted_data: Optional[bytes] = None
        self._metadata: Optional[Dict] = None
        self._aes_key: Optional[bytes] = None
        self._original_format: Optional[str] = None
        self._cover_image: Optional[bytes] = None

    def detect(self) -> bool:
        """
        检测是否是 NCM 格式

        检查文件头是否是 "CTENFDAM"
        """
        try:
            with open(self.file_path, 'rb') as f:
                header = f.read(8)
                return header == self.MAGIC_BYTES
        except Exception:
            return False

    def _rc4_decrypt(self, data: bytes, key: bytes) -> bytes:
        """
        RC4 流密码解密 (改进版，与 ncmdump 完全一致)

        参数:
            data: 加密的数据
            key: RC4 密钥

        返回:
            解密后的数据
        """
        # 1. 初始化 S-box (标准 RC4 Key-scheduling algorithm)
        S = list(range(256))
        j = 0
        key_len = len(key)

        for i in range(256):
            j = (j + S[i] + key[i % key_len]) & 0xFF
            S[i], S[j] = S[j], S[i]

        # 2. 生成伪随机流 (改进 RC4 Pseudo-random generation algorithm)
        # 这是关键！和标准的 RC4 不同
        stream = [S[(S[i] + S[(i + S[i]) & 0xFF]) & 0xFF] for i in range(256)]

        # 3. 重复流直到足够长
        repeats = len(data) // 256 + 1
        stream = bytes(bytearray(stream * repeats))

        # 4. 从索引 1 开始取数据！这是 ncmdump 的特殊之处
        stream = stream[1:1 + len(data)]

        # 5. XOR 解密
        return XOR(data, stream)

    def decrypt(self) -> bytes:
        """
        解密 NCM 文件

        完整的解密流程，基于 ncmdump 实现。

        返回:
            解密后的音频数据
        """
        if self._decrypted_data is not None:
            return self._decrypted_data

        print(f"[*] 开始解密: {self.file_path.name}")

        with open(self.file_path, 'rb') as f:
            # 1. 验证文件头
            header = f.read(8)
            if header != self.MAGIC_BYTES:
                raise ValueError(f"无效的 NCM 文件头: {header}")
            print("[+] 文件头验证通过")

            # 2. 跳过 2 字节标志位
            f.seek(2, 1)

            # 3. 读取密钥数据
            key_len_bytes = f.read(4)
            key_len = struct.unpack('<I', key_len_bytes)[0]
            print(f"[+] 密钥长度: {key_len} 字节")

            # 读取密钥数据并 XOR 0x64
            key_data = bytearray(f.read(key_len))
            if len(key_data) != key_len:
                raise ValueError(f"读取密钥数据失败: 期望 {key_len} 字节，实际 {len(key_data)} 字节")

            key_data = bytes(bytearray([byte ^ 0x64 for byte in key_data]))
            print(f"[+] 密钥数据 XOR 完成")

            # 4. AES-128-ECB 解密密钥
            cipher = AES.new(self.CORE_KEY, AES.MODE_ECB)
            decrypted_key = cipher.decrypt(key_data)

            # 移除 PKCS7 填充
            decrypted_key = unpad(decrypted_key, 16)
            print(f"[+] AES 密钥解密成功")

            # 跳过前 17 字节，得到真正的 RC4 密钥
            self._aes_key = decrypted_key[17:]
            print(f"[+] RC4 密钥长度: {len(self._aes_key)} 字节")
            print(f"    RC4 密钥 (前32字节): {self._aes_key[:16].hex()}...")

            # 5. 读取元数据
            meta_len_bytes = f.read(4)
            meta_len = struct.unpack('<I', meta_len_bytes)[0]
            print(f"[+] 元数据长度: {meta_len} 字节")

            if meta_len > 0:
                meta_data = bytearray(f.read(meta_len))
                meta_data = bytes(bytearray([byte ^ 0x63 for byte in meta_data]))
                print(f"[+] 元数据 XOR 完成")

                # Base64 解码
                try:
                    identifier = meta_data[:22].decode('utf-8', errors='ignore')
                    meta_b64 = base64.b64decode(meta_data[22:])
                    print(f"[+] Base64 解码成功")

                    # AES 解密元数据
                    cipher_meta = AES.new(self.META_KEY, AES.MODE_ECB)
                    meta_decrypted = unpad(cipher_meta.decrypt(meta_b64), 16)
                    print(f"[+] 元数据 AES 解密成功")

                    # 跳过前 6 字节，然后解析 JSON
                    meta_json = meta_decrypted[6:].decode('utf-8')
                    self._metadata = json.loads(meta_json)

                    if self._metadata:
                        print(f"[+] 歌曲: {self._metadata.get('musicName', 'Unknown')}")
                        print(f"    艺术家: {self._metadata.get('artist', ['Unknown'])[0] if isinstance(self._metadata.get('artist'), list) else 'Unknown'}")
                        print(f"    专辑: {self._metadata.get('album', 'Unknown')}")
                        print(f"    格式: {self._metadata.get('format', 'Unknown')}")

                except Exception as e:
                    print(f"[-] 元数据解析失败: {e}")
                    self._metadata = {}
            else:
                print("[*] 无元数据")
                # 根据文件大小猜测格式
                file_size = self.file_path.stat().st_size
                self._metadata = {'format': 'flac' if file_size > 1024 ** 2 * 16 else 'mp3'}

            # 6. 跳过 5 字节
            f.seek(5, 1)

            # 7. 读取专辑封面图片
            image_space_bytes = f.read(4)
            image_space = struct.unpack('<I', image_space_bytes)[0]

            image_size_bytes = f.read(4)
            image_size = struct.unpack('<I', image_size_bytes)[0]

            print(f"[+] 图片空间: {image_space} 字节")
            print(f"[+] 图片大小: {image_size} 字节")

            if image_size > 0:
                self._cover_image = f.read(image_size)
                print(f"[+] 已读取专辑封面 ({len(self._cover_image)} 字节)")
            else:
                self._cover_image = None

            # 跳过剩余的图片空间
            f.seek(image_space - image_size, 1)

            # 8. 读取并解密音频数据 (改进的 RC4 流密码!)
            audio_data = f.read()
            print(f"[+] 加密音频数据: {len(audio_data)} 字节")

            # 使用改进的 RC4 解密
            decrypted_audio = self._rc4_decrypt(audio_data, self._aes_key)
            print(f"[+] RC4 解密完成: {len(decrypted_audio)} 字节")

            # 9. 检测原始格式
            self._original_format = self._detect_audio_format(decrypted_audio)
            print(f"[+] 检测格式: {self._original_format}")

            self._decrypted_data = decrypted_audio
            return decrypted_audio

    def _detect_audio_format(self, data: bytes) -> str:
        """
        检测音频格式

        通过文件头魔数判断
        """
        if len(data) < 16:
            return "unknown"

        # FLAC: "fLaC"
        if data[:4] == b"fLaC":
            return "flac"

        # MP3: ID3 标签或帧同步头
        if data[:3] == b"ID3":
            return "mp3"
        if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
            return "mp3"

        # WAV: "RIFF"
        if data[:4] == b"RIFF":
            return "wav"

        # AAC: ADIF 或 ADTS
        if data[:4] == b"ADIF":
            return "aac"
        if data[:2] == b'\xff\xf1':
            return "aac"

        return "unknown"

    def get_format_info(self) -> Dict[str, Any]:
        """获取格式信息。

        Returns:
            包含格式信息的字典。
        """
        info: Dict[str, Any] = {
            "format": "NCM",
            "platform": "NetEase Cloud Music (网易云音乐)",
            "encryption": "RC4 (音频) + AES-128-ECB (密钥)",
            "file_path": str(self.file_path),
            "file_size": self.file_path.stat().st_size,
            "original_format": self._original_format or "需要解密后检测",
        }

        if self._metadata:
            info["metadata"] = self._metadata

        if self._aes_key:
            info["key_length"] = len(self._aes_key)

        return info

    def get_metadata(self) -> Optional[Dict]:
        """
        获取歌曲元数据

        返回:
            包含歌曲信息的字典（名称、艺术家等）
        """
        if self._metadata is None:
            # 需要解密才能获取元数据
            self.decrypt()
        return self._metadata

    def get_cover_image(self) -> Optional[bytes]:
        """
        获取专辑封面图片

        返回:
            图片数据，如果没有则返回 None
        """
        if self._cover_image is None:
            # 需要解密才能获取图片
            self.decrypt()
        return self._cover_image


# 测试代码
if __name__ == "__main__":
    import sys

    print("=== NCM 格式解密工具 (正确实现) ===\n")

    if len(sys.argv) < 2:
        print("用法: python ncm.py <ncm文件路径> [输出文件路径]")
        print("\n示例:")
        print("  python ncm.py song.ncm")
        print("  python ncm.py song.ncm output.flac")
        sys.exit(1)

    ncm_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    # 检查文件是否存在
    if not Path(ncm_file).exists():
        print(f"错误: 文件不存在: {ncm_file}")
        sys.exit(1)

    # 创建处理器
    ncm = NCMFormat(ncm_file)

    # 检查格式
    if not ncm.detect():
        print("错误: 不是有效的 NCM 文件")
        sys.exit(1)

    # 解密
    try:
        data = ncm.decrypt()

        # 显示信息
        info = ncm.get_format_info()
        print("\n=== 文件信息 ===")
        for k, v in info.items():
            if k != "metadata":
                print(f"  {k}: {v}")

        # 显示元数据
        metadata = ncm.get_metadata()
        if metadata:
            print("\n=== 歌曲信息 ===")
            print(f"  歌曲名: {metadata.get('musicName', 'Unknown')}")
            print(f"  艺术家: {metadata.get('artist', ['Unknown'])[0] if isinstance(metadata.get('artist'), list) else 'Unknown'}")
            print(f"  专辑: {metadata.get('album', 'Unknown')}")
            print(f"  格式: {metadata.get('format', 'Unknown')}")

        # 保存或显示数据
        if output_file:
            with open(output_file, 'wb') as f:
                f.write(data)
            print(f"\n[+] 已保存到: {output_file}")

            # 如果有封面，尝试嵌入
            cover = ncm.get_cover_image()
            if cover:
                print(f"[+] 封面图片: {len(cover)} 字节")
        else:
            print(f"\n[+] 解密完成，数据长度: {len(data)} 字节")
            print(f"    前16字节: {data[:16].hex()}")

    except Exception as e:
        print(f"\n[-] 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
