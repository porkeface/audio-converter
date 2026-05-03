"""
音频格式转换工具

支持格式：
  输入: NCM (网易云音乐), mflac (QQ 音乐)
  输出: FLAC, MP3, WAV

用法:
  python -m src.main convert song.ncm
  python -m src.main convert song.mflac
  python -m src.main convert song.mflac --key key.bin
  python -m src.main frida song.mflac
  python -m src.main batch D:\music
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, Tuple, List

from src.formats import NCMFormat, MflacFormat
from src.utils.detector import detect_format


# ──────────────────────────────────────────────
# 核心转换
# ──────────────────────────────────────────────

def convert_file(
    input_file: str,
    output_file: Optional[str] = None,
    key_file: Optional[str] = None,
) -> bool:
    """自动检测格式并解密。"""
    fmt = detect_format(input_file)

    if fmt is None:
        # 检查是否是标准音频
        with open(input_file, 'rb') as f:
            header = f.read(4)
        if header in (b"fLaC", b"ID3", b"RIFF") or header[:2] == b'\xff\xf1':
            print(f"标准音频格式，无需解密: {input_file}")
            return True
        print(f"无法识别的格式: {input_file}")
        return False

    print(f"检测到格式: {fmt.FORMAT_NAME}")
    print(f"文件: {fmt.file_path.name}")

    # mflac: 有密钥用密钥，没有就走 Frida
    if isinstance(fmt, MflacFormat):
        if key_file:
            with open(key_file, 'rb') as f:
                fmt.set_key(f.read())
            print(f"已加载密钥: {key_file}")
        else:
            print("无密钥，尝试 Frida 解密...")
            return frida_convert(input_file, output_file)

    try:
        data = fmt.decrypt()
    except ValueError as e:
        print(f"解密失败: {e}")
        return False

    # 确定输出路径
    if output_file is None:
        ext = _get_output_ext(fmt)
        output_file = str(fmt.file_path.parent / (fmt.file_path.stem + ext))

    with open(output_file, 'wb') as f:
        f.write(data)

    print(f"解密成功: {output_file} ({len(data):,} 字节)")
    _show_metadata(fmt)
    return True


def frida_convert(input_file: str, output_file: Optional[str] = None) -> bool:
    """通过 Frida 解密 mflac（需要 QQ 音乐运行）。"""
    from src.formats.frida_decrypt import decode_mflac
    success, result = decode_mflac(input_file, output_file)
    return success


def batch_convert(
    input_dir: str,
    output_dir: Optional[str] = None,
    key_file: Optional[str] = None,
) -> Tuple[int, int]:
    """批量解密目录下所有支持的文件。"""
    input_path = Path(input_dir)
    if output_dir is None:
        output_dir = str(input_path / "converted")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    extensions = ('.mflac', '.ncm')
    files: List[Path] = []
    for ext in extensions:
        files.extend(input_path.glob(f'*{ext}'))
        files.extend(input_path.glob(f'*{ext.upper()}'))

    if not files:
        print("未找到支持的文件 (.mflac, .ncm)")
        return 0, 0

    print(f"找到 {len(files)} 个文件")

    success = 0
    failed = 0
    for f in sorted(files):
        dst = str(Path(output_dir) / (f.stem + '.flac'))
        print(f"\n{'='*50}")
        print(f"处理: {f.name}")
        try:
            if convert_file(str(f), dst, key_file):
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"失败: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"完成: {success} 成功, {failed} 失败")
    return success, failed


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _get_output_ext(fmt) -> str:
    if isinstance(fmt, NCMFormat):
        return '.' + (fmt._original_format or 'flac')
    return '.flac'


def _show_metadata(fmt) -> None:
    if isinstance(fmt, NCMFormat):
        meta = fmt.get_metadata()
        if meta:
            print(f"  歌曲: {meta.get('musicName', '-')}")
            artist = meta.get('artist', ['-'])
            if isinstance(artist, list):
                artist = ', '.join(artist)
            print(f"  艺术家: {artist}")
            print(f"  专辑: {meta.get('album', '-')}")


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="音频解密工具 — 支持 NCM (网易云) 和 mflac (QQ 音乐)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转换 NCM（自动检测原始格式）
  python -m src.main convert song.ncm

  # 转换 mflac（需要密钥）
  python -m src.main convert song.mflac -k key.bin

  # 通过 Frida 解密 mflac（需要 QQ 音乐运行）
  python -m src.main frida song.mflac

  # 批量转换
  python -m src.main batch D:\\music\\encrypted
        """
    )

    sub = parser.add_subparsers(dest='command')

    # convert — 自动检测 + 解密
    p = sub.add_parser('convert', help='自动检测格式并解密')
    p.add_argument('input', help='输入文件')
    p.add_argument('output', nargs='?', help='输出文件（可选）')
    p.add_argument('-k', '--key', help='密钥文件（mflac 离线解密用）')

    # frida — 通过 Frida 解密 mflac
    p = sub.add_parser('frida', help='通过 Frida 解密 mflac（需 QQ 音乐运行）')
    p.add_argument('input', help='输入 mflac 文件')
    p.add_argument('output', nargs='?', help='输出 flac 文件')

    # batch — 批量转换
    p = sub.add_parser('batch', help='批量解密目录下所有文件')
    p.add_argument('input_dir', help='输入目录')
    p.add_argument('output_dir', nargs='?', help='输出目录（可选）')
    p.add_argument('-k', '--key', help='密钥文件')

    # extract-key — 提取密钥
    p = sub.add_parser('extract-key', help='从 mflac/flac 对提取密钥')
    p.add_argument('mflac', help='mflac 文件')
    p.add_argument('flac', help='对应的 flac 文件')
    p.add_argument('output', help='输出密钥文件')

    # analyze — 分析文件
    p = sub.add_parser('analyze', help='分析文件格式')
    p.add_argument('input', help='输入文件')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == 'convert':
        sys.exit(0 if convert_file(args.input, args.output, args.key) else 1)

    elif args.command == 'frida':
        sys.exit(0 if frida_convert(args.input, args.output) else 1)

    elif args.command == 'batch':
        s, f = batch_convert(args.input_dir, args.output_dir, args.key)
        sys.exit(0 if f == 0 else 1)

    elif args.command == 'extract-key':
        fmt = MflacFormat(args.mflac)
        key = fmt.extract_key_from_pair(args.flac)
        with open(args.output, 'wb') as fh:
            fh.write(key)
        print(f"密钥已提取: {len(key):,} 字节 -> {args.output}")

    elif args.command == 'analyze':
        fmt = detect_format(args.input)
        if fmt is None:
            print(f"无法识别: {args.input}")
        else:
            for k, v in fmt.get_format_info().items():
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
