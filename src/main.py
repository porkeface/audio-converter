"""
音频转换工具 - 真正可用的版本

用法:
    python -m src.main song.ncm [output.flac]
    python -m src.main song.ncm -f mp3
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.formats import NCMFormat
from src.utils.detector import detect_format


def print_banner():
    """打印欢迎信息"""
    print("=" * 60)
    print("  音频格式转换工具 (Audio Converter)")
    print("  支持: NCM → FLAC/MP3/WAV")
    print("=" * 60)
    print()


def convert_ncm(input_file: str, output_file: str = None, output_format: str = None):
    """
    转换 NCM 文件

    参数:
        input_file: 输入文件路径
        output_file: 输出文件路径（可选）
        output_format: 输出格式（可选）
    """
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"[错误] 文件不存在: {input_file}")
        return False

    # 检测格式
    fmt = detect_format(str(input_path))

    if fmt is None:
        print("[错误] 无法识别的格式，或不是加密格式")
        return False

    print(f"\n[信息] 检测到格式: {fmt.FORMAT_NAME}")
    print(f"[信息] 文件: {input_path.name}")
    print()

    try:
        # 解密
        print("[*] 开始解密...")
        decrypted_data = fmt.decrypt()

        # 获取元数据
        metadata = fmt.get_metadata()
        if metadata:
            print(f"\n[歌曲信息]")
            print(f"  歌曲名: {metadata.get('musicName', 'Unknown')}")
            print(f"  艺术家: {metadata.get('artist', ['Unknown'])[0] if isinstance(metadata.get('artist'), list) else 'Unknown'}")
            print(f"  专辑: {metadata.get('album', 'Unknown')}")
            print()

        # 确定输出文件
        if output_file is None:
            # 自动生成输出文件名
            if output_format:
                ext = output_format
            else:
                # 根据原始格式决定
                original_format = fmt._original_format or 'flac'
                ext = original_format
            output_file = input_path.stem + '.' + ext

        # 保存解密后的文件
        print(f"[*] 保存文件: {output_file}")
        with open(output_file, 'wb') as f:
            f.write(decrypted_data)

        print(f"\n[成功] 文件已保存: {output_file}")
        print(f"[信息] 文件大小: {len(decrypted_data)} 字节")

        # 如果格式需要转换（比如原始是 MP3，但要输出 FLAC）
        if output_format and fmt._original_format != output_format:
            print(f"\n[*] 需要转码: {fmt._original_format} -> {output_format}")
            print("[*] 调用 FFmpeg 进行转码...")

            # 临时文件
            temp_file = output_file + '.temp'
            os.rename(output_file, temp_file)

            try:
                from src.utils.converter import convert_audio
                success = convert_audio(temp_file, output_file, output_format)
                os.remove(temp_file)  # 删除临时文件

                if success:
                    print(f"[成功] 转码完成: {output_file}")
                else:
                    print("[警告] 转码失败，保留原始文件")
                    os.rename(temp_file, output_file)
            except Exception as e:
                print(f"[错误] 转码失败: {e}")
                if os.path.exists(temp_file):
                    os.rename(temp_file, output_file)

        return True

    except Exception as e:
        print(f"\n[错误] 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    import argparse

    print_banner()

    parser = argparse.ArgumentParser(
        description="音频格式转换工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转换 NCM 到 FLAC (自动检测原始格式)
  python -m src.main song.ncm

  # 指定输出文件
  python -m src.main song.ncm output.flac

  # 转换到 MP3 格式
  python -m src.main song.ncm -f mp3

  # 查看支持的格式
  python -m src.main --list-formats
        """
    )

    parser.add_argument("input", nargs="?", help="输入文件 (NCM 等)")
    parser.add_argument("output", nargs="?", help="输出文件 (可选)")
    parser.add_argument("-f", "--format", help="输出格式 (flac/mp3/wav)")
    parser.add_argument("-l", "--list-formats", action="store_true", help="列出支持的格式")

    args = parser.parse_args()

    if args.list_formats:
        print("[支持的格式]")
        print("  输入: NCM (网易云音乐)")
        print("  输出: FLAC, MP3, WAV")
        print()
        return

    if not args.input:
        parser.print_help()
        return

    # 执行转换
    success = convert_ncm(args.input, args.output, args.format)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
