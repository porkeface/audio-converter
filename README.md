# 音频格式转换教学项目

这是一个教学项目，演示如何实现类似 Sunwoo 的音频格式转换功能。

## 项目结构

```
audio-converter-demo/
├── src/
│   ├── formats/          # 各平台格式处理
│   │   ├── ncm.py        # 网易云 NCM 格式
│   │   ├── qmc.py        # QQ音乐 QMC 格式
│   │   └── base.py       # 格式基类
│   ├── crypto/           # 加密解密模块
│   │   └── aes.py        # AES 加解密
│   ├── utils/            # 工具函数
│   │   ├── detector.py   # 格式检测
│   │   └── converter.py  # 转码工具
│   └── main.py           # 主程序入口
├── tests/                # 测试文件
├── requirements.txt      # 依赖包
└── README.md            # 本文件
```

## 核心概念

### 1. 加密音频格式的本质
- 大多数音乐平台的"加密"格式 = 标准音频格式 + 简单的加密层
- 解密后通常就是普通的 MP3/FLAC 文件
- 加密算法通常是 AES（高级加密标准）

### 2. NCM 格式结构
```
NCM 文件 =
├── 文件头: "CTENFDAM" (8字节)
├── 加密的密钥数据
└── AES-128-ECB 加密的音频数据
```

### 3. 转换流程
```
输入文件 → 检测格式 → 解密 → 检测原始格式 → 转码 → 输出文件
```

## 使用方法

```bash
# 安装依赖
pip install -r requirements.txt

# 转换单个文件
python src/main.py input.ncm output.flac

# 查看支持的格式
python src/main.py --list-formats
```

## 学习路径

1. 先阅读 `src/formats/base.py` 了解格式基类
2. 然后看 `src/formats/ncm.py` 学习 NCM 解密
3. 再看 `src/crypto/aes.py` 理解 AES 解密
4. 最后看 `src/main.py` 了解整体流程
