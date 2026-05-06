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

import os
import sys
import argparse
import traceback
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from src.formats import NCMFormat, MflacFormat
from src.formats.base import AudioFormat
from src.utils.detector import detect_format


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

KNOWN_AUDIO_EXTENSIONS = {'.flac', '.mp3', '.wav', '.ogg', '.m4a', '.ncm', '.mflac', '.mgg', '.tmp'}


# ──────────────────────────────────────────────
# 音频格式检测
# ──────────────────────────────────────────────

def detect_audio_format(data: bytes) -> str:
    """根据音频数据的文件头检测格式。

    Args:
        data: 音频数据的前几个字节。

    Returns:
        格式字符串: 'flac', 'mp3', 'wav', 'ogg', 或 'flac'(默认)。
    """
    if len(data) < 4:
        return 'flac'
    if data[:4] == b'fLaC':
        return 'flac'
    if data[:3] == b'ID3' or data[:2] == b'\xff\xfb':
        return 'mp3'
    if data[:4] == b'RIFF':
        return 'wav'
    if data[:4] == b'OggS':
        return 'ogg'
    return 'flac'


def detect_audio_format_from_file(file_path: str) -> str:
    """根据文件头检测实际音频格式。

    Args:
        file_path: 音频文件路径。

    Returns:
        格式字符串: 'flac', 'mp3', 'wav', 'ogg', 或 'flac'(默认)。
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
        return detect_audio_format(header)
    except Exception:
        return 'flac'


# ──────────────────────────────────────────────
# 输出路径解析
# ──────────────────────────────────────────────

def parse_output_extension(filename: str) -> Tuple[str, Optional[str]]:
    """从文件名中解析基础名称和期望的扩展名。

    Args:
        filename: 文件名（不含目录路径）。

    Returns:
        Tuple of (base_name, desired_extension_or_None)。
    """
    last_dot = filename.rfind('.')
    if last_dot > 0 and filename[last_dot:].lower() in KNOWN_AUDIO_EXTENSIONS:
        desired_ext = filename[last_dot:].lower().lstrip('.')
        base_name = filename[:last_dot]
        return base_name, desired_ext
    return filename, None


def build_output_path(
    output_dir: str,
    base_name: str,
    actual_ext: str,
    desired_ext: Optional[str] = None,
) -> str:
    """构建最终输出文件路径。

    Args:
        output_dir: 输出目录。
        base_name: 文件基础名称（不含扩展名）。
        actual_ext: 实际音频格式的扩展名。
        desired_ext: 用户期望的扩展名，None 表示使用实际格式。

    Returns:
        完整的输出文件路径。
    """
    ext = desired_ext if desired_ext is not None else actual_ext
    return str(Path(output_dir) / f"{base_name}.{ext}")


# ──────────────────────────────────────────────
# 文件写入和转码
# ──────────────────────────────────────────────

def write_and_convert(
    data: bytes,
    output_file: str,
    actual_ext: str,
    desired_ext: Optional[str] = None,
) -> str:
    """写入解密数据并根据需要进行 FFmpeg 转码。

    Args:
        data: 解密后的音频数据。
        output_file: 最终输出文件路径。
        actual_ext: 实际音频格式。
        desired_ext: 期望的输出格式，None 表示不转码。

    Returns:
        实际输出的文件路径。
    """
    need_convert = desired_ext is not None and desired_ext != actual_ext

    if need_convert:
        # 需要转码：先写入临时文件，再用 FFmpeg 转换
        tmp_path = output_file + '.tmp.' + actual_ext
        with open(tmp_path, 'wb') as f:
            f.write(data)
        print(f"解密完成，实际格式: {actual_ext}，正在转换为 {desired_ext}...")

        from src.utils.converter import convert_audio
        if convert_audio(tmp_path, output_file, desired_ext):
            print(f"转换成功: {output_file}")
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        else:
            # FFmpeg 转换失败，保留实际格式的文件
            base_name = Path(output_file).stem
            fallback = str(Path(output_file).parent / f"{base_name}.{actual_ext}")
            os.replace(tmp_path, fallback)
            output_file = fallback
            print(f"FFmpeg 转换失败，保留原始格式: {output_file}")
    else:
        # 不需要转码：直接写入
        with open(output_file, 'wb') as f:
            f.write(data)

    return output_file


# ──────────────────────────────────────────────
# 标准音频格式转换
# ──────────────────────────────────────────────

def _convert_standard_audio(
    input_file: str,
    output_file: Optional[str] = None,
) -> Optional[str]:
    """转换标准音频格式（非加密格式）。

    支持 FLAC、MP3、WAV、OGG、AAC 等格式之间的转换。

    Args:
        input_file: 输入文件路径。
        output_file: 输出文件路径（可选）。

    Returns:
        实际输出文件路径，失败返回 None。
    """
    input_path = Path(input_file)
    actual_ext = detect_audio_format_from_file(input_file)

    # 确定输出路径和期望的格式
    if output_file is None:
        # 没有指定输出文件，直接返回原文件
        print(f"标准音频格式，无需转换: {input_file}")
        return input_file

    # 解析用户指定的输出格式
    fname = Path(output_file).name
    base_name, desired_ext = parse_output_extension(fname)

    if desired_ext is None:
        # 没有指定扩展名，使用原格式
        print(f"标准音频格式，无需转换: {input_file}")
        return input_file

    # 检查是否需要转换
    if desired_ext == actual_ext:
        print(f"格式相同，无需转换: {input_file}")
        return input_file

    # 需要 FFmpeg 转换
    output_path = str(Path(output_file).parent / f"{base_name}.{desired_ext}")
    print(f"检测到标准音频格式: {actual_ext}")
    print(f"正在转换为: {desired_ext}...")

    from src.utils.converter import convert_audio
    if convert_audio(input_file, output_path, desired_ext):
        print(f"转换成功: {output_path}")
        return output_path
    else:
        print(f"转换失败")
        return None


# ──────────────────────────────────────────────
# 核心转换
# ──────────────────────────────────────────────

def convert_file(
    input_file: str,
    output_file: Optional[str] = None,
    key_file: Optional[str] = None,
) -> Optional[str]:
    """自动检测格式并解密/转换。返回实际输出文件路径，失败返回 None。

    Args:
        input_file: 输入文件路径。
        output_file: 输出文件路径（可选）。
        key_file: 密钥文件路径（可选，用于 mflac 离线解密）。

    Returns:
        实际输出文件路径，失败返回 None。
    """
    fmt = detect_format(input_file)

    if fmt is None:
        # 检查是否是标准音频
        with open(input_file, 'rb') as f:
            header = f.read(4)
        if header in (b"fLaC", b"ID3", b"RIFF", b"OggS") or header[:2] == b'\xff\xf1':
            return _convert_standard_audio(input_file, output_file)
        print(f"无法识别的格式: {input_file}")
        return None

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
        return None

    # 根据实际音频数据检测格式
    actual_ext = detect_audio_format(data)

    # 确定输出路径
    if output_file is None:
        output_file = str(fmt.file_path.parent / f"{fmt.file_path.stem}.{actual_ext}")
    else:
        fname = Path(output_file).name
        base_name, desired_ext = parse_output_extension(fname)
        if desired_ext is None:
            # "默认"模式：使用实际格式
            output_file = str(Path(output_file).parent / f"{base_name}.{actual_ext}")
        else:
            # 用户指定了格式
            output_file = str(Path(output_file).parent / f"{base_name}.{desired_ext}")

    # 解析期望的扩展名（用于转码判断）
    _, desired_ext = parse_output_extension(Path(output_file).name)

    # 写入并转码
    output_file = write_and_convert(data, output_file, actual_ext, desired_ext)

    print(f"解密成功: {output_file} ({len(data):,} 字节)")

    _embed_audio_metadata(output_file, fmt)

    try:
        _show_metadata(fmt)
    except Exception as e:
        print(f"元数据显示失败（不影响输出）: {e}")

    return output_file


def frida_convert(input_file: str, output_file: Optional[str] = None) -> Optional[str]:
    """通过 Frida 解密 mflac/mgg（需要 QQ 音乐运行）。返回实际输出路径。"""
    from src.formats.frida_decrypt import decode_mflac

    # 解析用户期望的输出格式
    desired_ext = None
    if output_file:
        _, desired_ext = parse_output_extension(Path(output_file).name)

    # 确定 Frida 的输出目标和最终输出路径
    if output_file:
        out_parent = Path(output_file).parent
        fname = Path(output_file).name
        base_name, _ = parse_output_extension(fname)
        # Frida 写入临时文件，FFmpeg 再转为最终格式
        frida_output = str(out_parent / f"{base_name}.tmp.frida")
        final_dir = out_parent
    else:
        base_name = Path(input_file).stem
        final_dir = Path(input_file).parent
        frida_output = str(final_dir / f"{base_name}.tmp.frida")

    # Frida 解密写入临时文件
    success, result = decode_mflac(input_file, frida_output)

    if not success or not result:
        # 解密失败：清理 Frida 可能残留的输出文件
        if os.path.exists(frida_output):
            try:
                os.remove(frida_output)
            except OSError:
                pass
        return None

    if not os.path.exists(result):
        return None

    # 检测实际音频格式
    actual_ext = detect_audio_format_from_file(result)

    # FFmpeg 转码前，保存元数据
    source_meta = _read_source_metadata(input_file)
    if not source_meta:
        source_meta = _read_source_metadata(result)

    if desired_ext is not None and desired_ext != actual_ext:
        # 需要 FFmpeg 转码
        final_path = str(final_dir / f"{base_name}.{desired_ext}")
        print(f"实际格式为 {actual_ext}，正在转换为 {desired_ext}...")
        from src.utils.converter import convert_audio
        if convert_audio(result, final_path, desired_ext):
            print(f"转换成功: {final_path}")
            try:
                os.remove(result)
            except OSError:
                pass
            # 重新写入元数据
            _embed_audio_metadata(final_path, None, source_meta)
            return final_path
        else:
            # 转换失败，保留实际格式
            fallback = str(final_dir / f"{base_name}.{actual_ext}")
            os.replace(result, fallback)
            print(f"FFmpeg 转换失败，保留原始格式: {fallback}")
            return fallback
    else:
        # 不需要转码，直接重命名为正确扩展名
        final_path = str(final_dir / f"{base_name}.{actual_ext}")
        os.replace(result, final_path)
        print(f"实际格式为 {actual_ext}，输出文件: {final_path}")
        return final_path


def batch_convert(
    input_dir: str,
    output_dir: Optional[str] = None,
    key_file: Optional[str] = None,
) -> Tuple[int, int]:
    """批量解密目录下所有支持的文件。

    Args:
        input_dir: 输入目录路径。
        output_dir: 输出目录路径，None 表示在输入目录下创建 converted 子目录。
        key_file: 密钥文件路径（可选）。

    Returns:
        Tuple of (success_count, failed_count)。
    """
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

def _show_metadata(fmt: AudioFormat) -> None:
    """显示格式对象中的元数据信息。

    Args:
        fmt: 音频格式对象。
    """
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


def get_metadata_str(fmt: AudioFormat) -> str:
    """从解密后的格式对象中提取元数据摘要字符串。

    Args:
        fmt: 音频格式对象。

    Returns:
        元数据摘要字符串，格式为 "歌曲名 · 艺术家 · 专辑"。
    """
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


def get_metadata_from_file(file_path: str) -> str:
    """从音频文件中读取元数据标签（支持 FLAC/MP3/OGG/M4A）。

    Args:
        file_path: 音频文件路径。

    Returns:
        元数据摘要字符串，格式为 "标题 · 艺术家 · 专辑"。
    """
    try:
        import mutagen
        audio = mutagen.File(file_path, easy=True)
        if audio is None:
            return ""
        parts = []
        if audio.get('title'):
            parts.append(audio['title'][0])
        if audio.get('artist'):
            parts.append(audio['artist'][0])
        if audio.get('album'):
            parts.append(audio['album'][0])
        return ' · '.join(parts)
    except Exception:
        return ""


def _extract_artist_names(artist_list: Any) -> str:
    """从 NCM 元数据的 artist 字段提取艺术家名称字符串。

    Args:
        artist_list: NCM 元数据中的 artist 字段，可能是字符串或列表。

    Returns:
        逗号分隔的艺术家名称字符串。
    """
    if isinstance(artist_list, str):
        return artist_list
    names = []
    for a in (artist_list or []):
        if isinstance(a, list):
            names.append(a[0])
        else:
            names.append(str(a))
    return ', '.join(names)


def _read_source_metadata(file_path: str) -> Dict[str, Any]:
    """从音频文件中读取元数据（用于在 FFmpeg 转码前保存元数据）。

    Args:
        file_path: 音频文件路径。

    Returns:
        包含元数据的字典，可能包含 'title', 'artist', 'album', 'cover' 键。
    """
    try:
        import mutagen
        audio = mutagen.File(file_path, easy=False)
        if audio is None:
            return {}
        result: Dict[str, Any] = {}
        if isinstance(audio, mutagen.flac.FLAC):
            if audio.get('title'):
                result['title'] = audio['title'][0]
            if audio.get('artist'):
                result['artist'] = audio['artist'][0]
            if audio.get('album'):
                result['album'] = audio['album'][0]
            if audio.pictures:
                result['cover'] = audio.pictures[0].data
        elif isinstance(audio, mutagen.mp3.MP3) and audio.tags:
            if audio.tags.get('TIT2'):
                result['title'] = audio.tags['TIT2'].text[0]
            if audio.tags.get('TPE1'):
                result['artist'] = audio.tags['TPE1'].text[0]
            if audio.tags.get('TALB'):
                result['album'] = audio.tags['TALB'].text[0]
            if audio.tags.get('APIC'):
                result['cover'] = audio.tags['APIC'].data
        elif isinstance(audio, mutagen.oggvorbis.OggVorbis):
            if audio.get('title'):
                result['title'] = audio['title'][0]
            if audio.get('artist'):
                result['artist'] = audio['artist'][0]
            if audio.get('album'):
                result['album'] = audio['album'][0]
        elif isinstance(audio, mutagen.mp4.MP4):
            if audio.get('\xa9nam'):
                result['title'] = audio['\xa9nam'][0]
            if audio.get('\xa9ART'):
                result['artist'] = audio['\xa9ART'][0]
            if audio.get('\xa9alb'):
                result['album'] = audio['\xa9alb'][0]
            if audio.get('covr'):
                result['cover'] = bytes(audio['covr'][0])
        return result
    except Exception:
        return {}


def _embed_audio_metadata(
    output_path: str,
    fmt: Optional[AudioFormat],
    source_meta: Optional[Dict[str, Any]] = None,
) -> None:
    """将元数据写入输出音频文件，或保留音频流中已有的标签。

    Args:
        output_path: 输出文件路径。
        fmt: 格式对象（NCMFormat 等），可以为 None。
        source_meta: 从源文件预读取的元数据（用于 mflac/mgg 等无独立元数据源的格式）。
    """
    # 提取 NCM 元数据（如果有）
    meta = None
    cover = None
    if isinstance(fmt, NCMFormat):
        meta = fmt.get_metadata()
        cover = fmt.get_cover_image()

    # 如果 NCM 没有元数据，使用从源文件预读取的元数据
    if not meta and source_meta:
        meta = {
            'musicName': source_meta.get('title', ''),
            'artist': source_meta.get('artist', ''),
            'album': source_meta.get('album', ''),
        }
        cover = source_meta.get('cover')

    has_useful_meta = meta and (meta.get('musicName') or meta.get('artist') or meta.get('album'))

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
            if has_useful_meta:
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
            if has_useful_meta or cover:
                audio.save()
                print(f"[+] 已写入 FLAC 元数据")
            else:
                print(f"[+] FLAC 已有元数据，保留不变")

        elif isinstance(audio, mutagen.mp3.MP3):
            from mutagen.id3 import APIC, TIT2, TPE1, TALB
            if has_useful_meta:
                if title:
                    audio.tags.add(TIT2(encoding=3, text=[title]))
                if artist_str:
                    audio.tags.add(TPE1(encoding=3, text=[artist_str]))
                if album:
                    audio.tags.add(TALB(encoding=3, text=[album]))
            if cover:
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover))
            if has_useful_meta or cover:
                audio.save()
                print(f"[+] 已写入 MP3 元数据")
            else:
                print(f"[+] MP3 已有元数据，保留不变")

        elif isinstance(audio, mutagen.oggvorbis.OggVorbis):
            # OGG Vorbis：保留已有标签，仅在有 NCM 元数据时覆盖
            if has_useful_meta:
                if title:
                    audio['title'] = [title]
                if artist_str:
                    audio['artist'] = [artist_str]
                if album:
                    audio['album'] = [album]
                audio.save()
                print(f"[+] 已写入 OGG 元数据")
            else:
                print(f"[+] OGG 已有元数据，保留不变")

        elif isinstance(audio, mutagen.mp4.MP4):
            # M4A/AAC：使用 iTunes 风格的标签
            if has_useful_meta:
                if title:
                    audio['\xa9nam'] = [title]
                if artist_str:
                    audio['\xa9ART'] = [artist_str]
                if album:
                    audio['\xa9alb'] = [album]
            if cover:
                from mutagen.mp4 import MP4Cover
                audio['covr'] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
            if has_useful_meta or cover:
                audio.save()
                print(f"[+] 已写入 M4A 元数据")
            else:
                print(f"[+] M4A 已有元数据，保留不变")

    except Exception as e:
        print(f"[-] 写入元数据失败（不影响音频）: {e}")


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def main() -> None:
    """CLI 入口函数。"""
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
