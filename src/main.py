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
import traceback
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
        if header in (b"fLaC", b"ID3", b"RIFF", b"OggS") or header[:2] == b'\xff\xf1':
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
    except Exception as e:
        print(f"解密失败: {e}")
        traceback.print_exc()
        return False

    # 根据实际音频数据检测格式，确定正确的文件扩展名
    actual_ext = _detect_audio_format_data(data)
    if output_file is None:
        output_file = str(fmt.file_path.parent / (fmt.file_path.stem + '.' + actual_ext))
    else:
        # 用户指定了输出路径，但扩展名可能与实际格式不匹配
        # 例如用户选了 FLAC 但实际是 MP3 → 改为正确扩展名
        out_path = Path(output_file)
        if out_path.suffix.lower() != '.' + actual_ext:
            output_file = str(out_path.with_suffix('.' + actual_ext))
            print(f"实际格式为 {actual_ext}，输出文件: {output_file}")

    with open(output_file, 'wb') as f:
        f.write(data)

    print(f"解密成功: {output_file} ({len(data):,} 字节)")

    _embed_audio_metadata(output_file, fmt)

    try:
        _show_metadata(fmt)
    except Exception as e:
        print(f"元数据显示失败（不影响输出）: {e}")

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

    extensions = ('.mflac', '.mgg', '.ncm')
    files: List[Path] = []
    for ext in extensions:
        files.extend(input_path.glob(f'*{ext}'))
        files.extend(input_path.glob(f'*{ext.upper()}'))

    if not files:
        print("未找到支持的文件 (.mflac, .mgg, .ncm)")
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
            artist = meta.get('artist', [])
            names = []
            for a in artist:
                if isinstance(a, list):
                    names.append(a[0])
                else:
                    names.append(str(a))
            print(f"  艺术家: {', '.join(names) if names else '-'}")
            print(f"  专辑: {meta.get('album', '-')}")


def get_metadata_str(fmt) -> str:
    """从解密后的格式对象中提取元数据摘要字符串。"""
    if not isinstance(fmt, NCMFormat):
        return ""
    meta = fmt.get_metadata()
    if not meta:
        return ""
    parts = []
    name = meta.get('musicName')
    if name:
        parts.append(name)
    artist = meta.get('artist', [])
    names = []
    for a in artist:
        if isinstance(a, list):
            names.append(a[0])
        else:
            names.append(str(a))
    if names:
        parts.append(', '.join(names))
    album = meta.get('album')
    if album:
        parts.append(album)
    return ' · '.join(parts)


def _detect_audio_format(file_path: str) -> str:
    """根据文件头检测实际音频格式（flac/mp3/wav/ogg）。"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
        if header == b'fLaC':
            return 'flac'
        if header[:3] == b'ID3' or header[:2] == b'\xff\xfb':
            return 'mp3'
        if header == b'RIFF':
            return 'wav'
        if header == b'OggS':
            return 'ogg'
    except Exception:
        pass
    return 'flac'


def _detect_audio_format_data(data: bytes) -> str:
    """根据音频数据的前几个字节检测格式。"""
    if data[:4] == b'fLaC':
        return 'flac'
    if data[:3] == b'ID3' or data[:2] == b'\xff\xfb':
        return 'mp3'
    if data[:4] == b'RIFF':
        return 'wav'
    if data[:4] == b'OggS':
        return 'ogg'
    return 'flac'


def _extract_artist_names(artist_list) -> str:
    """从 NCM 元数据的 artist 字段提取艺术家名称字符串。"""
    names = []
    for a in (artist_list or []):
        if isinstance(a, list):
            names.append(a[0])
        else:
            names.append(str(a))
    return ', '.join(names)


def _embed_audio_metadata(output_path: str, fmt) -> None:
    """将元数据和封面写入输出音频文件（FLAC/MP3）。"""
    if not isinstance(fmt, NCMFormat):
        return

    meta = fmt.get_metadata()
    cover = fmt.get_cover_image()

    # 没有 NCM 元数据且没有封面 → 跳过，保留音频流中已有的 Vorbis/ID3 标签
    has_useful_meta = meta and (meta.get('musicName') or meta.get('artist') or meta.get('album'))
    if not has_useful_meta and not cover:
        return

    try:
        import mutagen
        audio = mutagen.File(output_path, easy=False)
        if audio is None:
            print(f"[-] 无法识别音频格式: {output_path}")
            return

        title = meta.get('musicName', '') if meta else ''
        artist_str = _extract_artist_names(meta.get('artist', []) if meta else [])
        album = meta.get('album', '') if meta else ''

        if isinstance(audio, mutagen.flac.FLAC):
            from mutagen.flac import Picture
            if title:
                audio['title'] = [title]
            if artist_str:
                audio['artist'] = [artist_str]
            if album:
                audio['album'] = [album]
            if cover:
                pic = Picture()
                pic.type = 3
                pic.mime = 'image/jpeg'
                pic.data = cover
                audio.clear_pictures()
                audio.add_picture(pic)
            audio.save()
            print(f"[+] 已写入 FLAC 元数据")

        elif isinstance(audio, mutagen.mp3.MP3):
            from mutagen.id3 import APIC, TIT2, TPE1, TALB
            if title:
                audio.tags.add(TIT2(encoding=3, text=[title]))
            if artist_str:
                audio.tags.add(TPE1(encoding=3, text=[artist_str]))
            if album:
                audio.tags.add(TALB(encoding=3, text=[album]))
            if cover:
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover))
            audio.save()
            print(f"[+] 已写入 MP3 元数据")

        elif isinstance(audio, mutagen.oggvorbis.OggVorbis):
            if title:
                audio['title'] = [title]
            if artist_str:
                audio['artist'] = [artist_str]
            if album:
                audio['album'] = [album]
            audio.save()
            print(f"[+] 已写入 OGG 元数据")

    except Exception as e:
        print(f"[-] 写入元数据失败（不影响音频）: {e}")


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
