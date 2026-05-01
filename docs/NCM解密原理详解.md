# NCM 格式解密原理详解

> 本文档详细记录了网易云音乐 NCM 格式的解密实现过程，包括文件结构、加密算法、以及踩过的坑。

---

## 📋 目录

- [1. NCM 文件结构](#1-ncm-文件结构)
- [2. 加密原理](#2-加密原理)
- [3. 解密流程](#3-解密流程)
- [4. 关键代码实现](#4-关键代码实现)
- [5. 踩坑记录](#5-踩坑记录)
- [6. 完整代码](#6-完整代码)

---

## 1. NCM 文件结构

NCM 文件是一个**容器格式**，包含加密的音频数据、密钥、元数据（歌曲信息）和专辑封面。

### 文件结构图

```
NCM 文件结构：
┌─────────────────────────────────────┐
│  8字节: 文件头 "CTENFDAM"           │  ← 魔数标识
├─────────────────────────────────────┤
│  2字节: 标志位 (未知用途，跳过)     │
├─────────────────────────────────────┤
│  4字节: 密钥数据长度 (小端序 uint32) │
├─────────────────────────────────────┤
│  N字节: 加密的密钥数据              │  ← XOR 0x64 + AES 加密
├─────────────────────────────────────┤
│  4字节: 元数据长度 (小端序 uint32)   │
├─────────────────────────────────────┤
│  M字节: 加密的元数据                │  ← XOR 0x63 + Base64 + AES
├─────────────────────────────────────┤
│  4字节: 图片空白区域大小             │
│  4字节: 图片实际大小                │
├─────────────────────────────────────┤
│  P字节: 专辑封面图片数据            │
├─────────────────────────────────────┤
│  剩余: RC4 加密的音频数据           │  ← 核心音频内容
└─────────────────────────────────────┘
```

### 结构说明

| 字段 | 大小 | 说明 |
|------|------|------|
| 文件头 | 8 字节 | 固定为 `CTENFDAM`，用于识别 NCM 格式 |
| 标志位 | 2 字节 | 作用未知，直接跳过 |
| 密钥长度 | 4 字节 | 小端序 uint32，表示后续密钥数据的字节数 |
| 密钥数据 | 可变 | 加密的 AES 密钥（XOR + AES 加密） |
| 元数据长度 | 4 字节 | 小端序 uint32，表示元数据字节数 |
| 元数据 | 可变 | 歌曲信息（JSON 格式，加密存储） |
| 图片数据 | 可变 | 专辑封面（JPEG/PNG） |
| 音频数据 | 剩余 | 真正的音频内容（RC4 加密） |

---

## 2. 加密原理

NCM 使用了**两层加密**：

### 2.1 密钥加密（保护 AES 密钥）

用于解密音频的密钥本身也被加密存储：

1. **原始密钥**：一个随机生成的二进制密钥（用于 RC4 加密音频）
2. **加密过程**：
   - 密钥数据先与 `0x64` 异或
   - 然后使用 **AES-128-ECB** 加密（密钥为 `CORE_KEY`）
   - 解密后得到的数据再跳过前 17 个字节，才是真正的 RC4 密钥

### 2.2 音频加密（RC4 流密码）

音频数据使用 **RC4 流密码** 加密（不是 AES！这是很多人踩坑的地方）：

- **算法**：改进的 RC4（Pseudo-random generation algorithm 有改动）
- **密钥**：从密钥数据解密后提取
- **特点**：对称加密，加密和解密是同一个操作（XOR）

### 2.3 元数据加密

歌曲信息（歌名、艺术家、专辑等）也加密存储：

1. 元数据先与 `0x63` 异或
2. 然后进行 Base64 解码
3. 使用 **AES-128-ECB** 解密（密钥为 `META_KEY`）
4. 最后跳过前 6 个字节，得到 JSON 字符串

---

## 3. 解密流程

解密分 5 个步骤：

### 步骤 1：验证文件头

```python
with open(file_path, 'rb') as f:
    header = f.read(8)
    assert header == b"CTENFDAM", "不是有效的 NCM 文件"
```

### 步骤 2：提取并解密 AES 密钥

```python
# 跳过 2 字节标志位
f.seek(2, 1)

# 读取密钥长度和数据
key_len = struct.unpack('<I', f.read(4))[0]
key_data = bytearray(f.read(key_len))

# XOR 0x64
key_data = bytes(bytearray([byte ^ 0x64 for byte in key_data]))

# AES-128-ECB 解密
cipher = AES.new(CORE_KEY, AES.MODE_ECB)
decrypted_key = cipher.decrypt(key_data)

# 移除 PKCS7 填充
decrypted_key = unpad(decrypted_key, 16)

# 跳过前 17 字节，得到 RC4 密钥
rc4_key = decrypted_key[17:]
```

**关键点**：
- `CORE_KEY` 是固定的：`687A4852416D736F356B496E62617857`（十六进制）
- 解密后的数据前 17 字节是垃圾数据，需要跳过

### 步骤 3：提取并解密元数据

```python
# 读取元数据长度
meta_len = struct.unpack('<I', f.read(4))[0]

if meta_len > 0:
    # 读取元数据
    meta_data = bytearray(f.read(meta_len))
    
    # XOR 0x63
    meta_data = bytes(bytearray([byte ^ 0x63 for byte in meta_data]))
    
    # Base64 解码（跳过前 22 字节标识符）
    identifier = meta_data[:22].decode('utf-8', errors='ignore')
    meta_b64 = base64.b64decode(meta_data[22:])
    
    # AES-128-ECB 解密
    cipher_meta = AES.new(META_KEY, AES.MODE_ECB)
    meta_decrypted = unpad(cipher_meta.decrypt(meta_b64), 16)
    
    # 跳过前 6 字节，解析 JSON
    meta_json = meta_decrypted[6:].decode('utf-8')
    metadata = json.loads(meta_json)
```

**关键点**：
- `META_KEY` 是固定的：`2331346C6A6B5F215C5D2630553C2728`（十六进制）
- 元数据包含：`musicName`、`artist`、`album`、`format` 等字段

### 步骤 4：提取专辑封面

```python
# 跳过 5 字节
f.seek(5, 1)

# 读取图片空间大小和实际大小
image_space = struct.unpack('<I', f.read(4))[0]
image_size = struct.unpack('<I', f.read(4))[0]

# 读取图片数据
if image_size > 0:
    cover_image = f.read(image_size)
else:
    cover_image = None

# 跳过剩余空间
f.seek(image_space - image_size, 1)
```

### 步骤 5：RC4 解密音频数据

```python
# 读取加密的音频数据
audio_data = f.read()

# RC4 解密
decrypted_audio = rc4_decrypt(audio_data, rc4_key)

# 检测原始格式
if decrypted_audio[:4] == b"fLaC":
    format = "flac"
elif decrypted_audio[:3] == b"ID3":
    format = "mp3"
```

---

## 4. 关键代码实现

### 4.1 RC4 算法（改进版）

这是 NCM 解密的核心，也是最容易出错的地方！

```python
def rc4_decrypt(data: bytes, key: bytes) -> bytes:
    """
    改进的 RC4 流密码解密
    
    注意：这个实现和标准的 RC4 不同！
    - 生成流的方式有改动
    - 从索引 1 开始取数据（不是 0）
    """
    from Crypto.Util.strxor import strxor as XOR
    
    # 1. 初始化 S-box (标准 Key-scheduling algorithm)
    S = list(range(256))
    j = 0
    key_len = len(key)
    
    for i in range(256):
        j = (j + S[i] + key[i % key_len]) & 0xFF
        S[i], S[j] = S[j], S[i]
    
    # 2. 生成伪随机流 (改进的 Pseudo-random generation algorithm)
    # 关键：这里和标准的 RC4 不同！
    stream = [S[(S[i] + S[(i + S[i]) & 0xFF]) & 0xFF] for i in range(256)]
    
    # 3. 重复流直到足够长
    repeats = len(data) // 256 + 1
    stream = bytes(bytearray(stream * repeats))
    
    # 4. 从索引 1 开始取数据！这是 ncmdump 的特殊之处
    stream = stream[1:1 + len(data)]
    
    # 5. XOR 解密
    return XOR(data, stream)
```

**为什么和标准 RC4 不同？**

标准的 RC4 PRGA 是这样的：
```python
i = 0
j = 0
while 需要输出:
    i = (i + 1) & 0xFF
    j = (j + S[i]) & 0xFF
    S[i], S[j] = S[j], S[i]
    yield S[(S[i] + S[j]) & 0xFF]
```

但 NCM 使用的改进版是：
```python
# 预先生成 256 字节的流
stream = [S[(S[i] + S[(i + S[i]) & 0xFF]) & 0xFF] for i in range(256)]
# 然后重复这个流
# 并且从索引 1 开始取数据！
```

### 4.2 完整的密钥解密

```python
# 固定密钥（十六进制）
CORE_KEY = bytes.fromhex('687A4852416D736F356B496E62617857')
# 对应字符串: "hzHRAmso5kInbaxW"

def decrypt_key(encrypted_key_data):
    """解密密钥数据，提取 RC4 密钥"""
    # XOR 0x64
    key_data = bytes(bytearray([b ^ 0x64 for b in encrypted_key_data]))
    
    # AES-128-ECB 解密
    cipher = AES.new(CORE_KEY, AES.MODE_ECB)
    decrypted = cipher.decrypt(key_data)
    
    # 移除 PKCS7 填充
    decrypted = unpad(decrypted, 16)
    
    # 跳过前 17 字节
    rc4_key = decrypted[17:]
    
    return rc4_key
```

---

## 5. 踩坑记录

### 坑 1：音频加密算法搞错 ❌

**错误**：以为音频数据也是用 AES 解密的
```python
# 错误做法
cipher = AES.new(rc4_key, AES.MODE_ECB)
decrypted_audio = cipher.decrypt(audio_data)
```

**正确**：音频数据是用 **RC4 流密码** 加密的
```python
# 正确做法
decrypted_audio = rc4_decrypt(audio_data, rc4_key)
```

**后果**：解密出来的数据是乱码，前 4 字节不是 `fLaC` 或 `ID3`

---

### 坑 2：CORE_KEY 不对 ❌

**错误**：使用了不完整的密钥
```python
# 错误：只有 15 字节，缺少最后的 \x00
CORE_KEY = b"hzHRAmso5kACgkq"
```

**正确**：必须是 16 字节
```python
# 正确：完整的 16 字节密钥
CORE_KEY = bytes.fromhex('687A4852416D736F356B496E62617857')
# 或者
CORE_KEY = b"hzHRAmso5kInbaxW"
```

**后果**：AES 解密失败，密钥不对

---

### 坑 3：RC4 实现不对 ❌

**错误**：使用了标准的 RC4 实现
```python
# 标准 RC4（错误！）
def standard_rc4(data, key):
    S = list(range(256))
    # ... 初始化 ...
    i = 0
    j = 0
    result = []
    for _ in range(len(data)):
        i = (i + 1) & 0xFF
        j = (j + S[i]) & 0xFF
        S[i], S[j] = S[j], S[i]
        result.append(data[_] ^ S[(S[i] + S[j]) & 0xFF])
    return bytes(result)
```

**正确**：使用改进的 RC4，并且从索引 1 开始
```python
# 改进的 RC4（正确！）
stream = [S[(S[i] + S[(i + S[i]) & 0xFF]) & 0xFF] for i in range(256)]
stream = stream * (len(data) // 256 + 1)
stream = stream[1:1 + len(data)]  # 注意：从 1 开始！
return XOR(data, bytes(stream))
```

**后果**：解密出来的数据前几个字节不对，文件头错误

---

### 坑 4：密钥长度解析错误 ❌

**错误**：错误地解析密钥长度字段
```python
# 错误：没有正确处理小端序
key_len = int.from_bytes(f.read(4))  # 可能不对
```

**正确**：使用 struct 解析
```python
# 正确
key_len = struct.unpack('<I', f.read(4))[0]
```

**后果**：密钥长度解析错误（例如解析出 9462017 这种异常值）

---

### 坑 5：元数据解析遗漏 ❌

**错误**：忘记处理 Base64 解码和跳过标识符
```python
# 错误：直接 AES 解密
meta_decrypted = cipher.decrypt(meta_data)
```

**正确**：先 XOR，再 Base64，再 AES
```python
# 正确
meta_data = bytes(bytearray([b ^ 0x63 for b in meta_data]))  # XOR 0x63
identifier = meta_data[:22]  # 跳过标识符
meta_b64 = base64.b64decode(meta_data[22:])  # Base64 解码
meta_decrypted = cipher.decrypt(meta_b64)  # AES 解密
```

---

## 6. 核心常量总结

| 常量 | 值（十六进制） | 说明 |
|------|---------------|------|
| `CORE_KEY` | `687A4852416D736F356B496E62617857` | 用于解密密钥数据 |
| `META_KEY` | `2331346C6A6B5F215C5D2630553C2728` | 用于解密元数据 |
| 密钥 XOR 值 | `0x64` | 密钥数据的 XOR 掩码 |
| 元数据 XOR 值 | `0x63` | 元数据的 XOR 掩码 |
| 跳过字节数 | `17` | 解密后的密钥前 17 字节是垃圾 |
| RC4 流起始 | `1` | 从索引 1 开始取流数据 |

---

## 7. 测试验证

### 验证方法

解密后检查文件头：

```python
with open('output.flac', 'rb') as f:
    header = f.read(4)
    
if header == b'fLaC':
    print("✓ 成功！这是 FLAC 文件")
elif header == b'ID3':
    print("✓ 成功！这是 MP3 文件")
else:
    print("✗ 失败！文件头不对")
```

### 与 ncmdump 对比

使用已知的 `ncmdump` 工具验证：

```bash
# 安装 ncmdump
pip install ncmdump

# 使用 ncmdump 解密
python -c "from ncmdump import dump; dump('input.ncm', 'reference.flac')"

# 对比两个文件的前 32 字节
python -c "
with open('output.flac', 'rb') as f1, open('reference.flac', 'rb') as f2:
    print('Our output:', f1.read(32).hex())
    print('Reference: ', f2.read(32).hex())
"
```

如果前 32 字节完全相同，说明实现正确！

---

## 8. 总结

### 解密流程速记

```
1. 验证文件头 "CTENFDAM"
2. 读取密钥数据 → XOR 0x64 → AES-128-ECB 解密 → 跳过 17 字节 → 得到 RC4 密钥
3. 读取元数据 → XOR 0x63 → Base64 解码 → AES-128-ECB 解密 → JSON
4. 读取专辑封面
5. 读取音频数据 → RC4 解密 → 得到原始音频
```

### 关键要点

- ✅ 音频加密用的是 **RC4**，不是 AES
- ✅ RC4 实现是**改进的版本**，从索引 1 开始取流
- ✅ 密钥和元数据用 **AES-128-ECB** 加密
- ✅ 注意 **XOR 掩码**：密钥用 `0x64`，元数据用 `0x63`
- ✅ 文件结构是**小端序** (Little-Endian)

---

## 9. 参考资料

- [ncmdump 原始实现](https://github.com/nondanee/ncmdump)
- [RC4 流密码](https://en.wikipedia.org/wiki/RC4)
- [AES-128-ECB 模式](https://en.wikipedia.org/wiki/Advanced_Encryption_Standard)
- [PKCS7 填充](https://en.wikipedia.org/wiki/Padding_(cryptography)#PKCS#5_and_PKCS#7)

---

## 10. 完整实现代码

完整代码见：[`src/formats/ncm.py`](../src/formats/ncm.py)

使用示例：

```bash
# 转换 NCM 到 FLAC
python -m src.main "song.ncm" "output.flac"

# 转换 NCM 到 MP3
python -m src.main "song.ncm" "output.mp3"

# 查看详细信息
python -m src.formats.ncm "song.ncm"
```

---

**文档版本**：1.0  
**最后更新**：2025-05-01  
**作者**：基于 ncmdump 实现整理
