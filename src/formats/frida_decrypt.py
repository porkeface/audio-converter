"""
Frida-based mflac decoder that hooks into QQ Music's QQMusicCommon.dll.

Replicates sunwoo.exe's approach: uses Frida to inject into QQ Music's process
and call the EncAndDesMediaFile API for decryption.

Requirements:
- QQ Music must be installed and running
- Frida must be installed (pip install frida frida-tools)
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Tuple, Optional
import frida


def _load_frida_script() -> str:
    """Load Frida JavaScript payload from external file.

    Returns:
        The JavaScript source code for the Frida script.

    Raises:
        FileNotFoundError: If the script file cannot be found.
    """
    script_path = Path(__file__).parent / "frida_script.js"
    if not script_path.exists():
        raise FileNotFoundError(f"Frida script not found: {script_path}")
    return script_path.read_text(encoding="utf-8")


# Load script once at module level for efficiency
FRIDA_SCRIPT = _load_frida_script()


def find_qqmusic_process() -> Tuple[Optional[int], Optional[str]]:
    """Find QQ Music process.

    Returns:
        Tuple of (pid, process_name) or (None, None) if not found.
    """
    try:
        device = frida.get_local_device()
        processes = device.enumerate_processes()
        for proc in processes:
            if 'QQMusic' in proc.name:
                return proc.pid, proc.name
    except Exception as e:
        print(f"Error finding QQ Music: {e}")
    return None, None


def attach_and_decrypt(pid: int, src_path: str, dst_path: str) -> dict:
    """Attach to QQ Music and decrypt a file using Frida.

    Args:
        pid: Process ID of QQ Music.
        src_path: Path to the encrypted mflac file.
        dst_path: Path for the decrypted output file.

    Returns:
        Dictionary with 'status' (0 for success) and optional 'error'.
    """
    session = frida.attach(pid)
    script = session.create_script(FRIDA_SCRIPT)
    script.load()

    try:
        api = script.exports_sync
        result = api.decrypt(src_path, dst_path)
    finally:
        script.unload()
        session.detach()

    return result


def decode_mflac(input_path: str, output_path: Optional[str] = None) -> Tuple[bool, str]:
    """Decode an mflac file to flac using Frida + QQ Music's DLL.

    Requires QQ Music to be running.

    Args:
        input_path: Path to the encrypted mflac file.
        output_path: Optional path for the output file. Defaults to input_name.flac.

    Returns:
        Tuple of (success, output_path_or_error_message).
    """
    # 使用绝对路径，QQ Music 的 DLL 需要完整路径才能打开文件
    input_path = os.path.abspath(input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        base = os.path.splitext(input_path)[0]
        output_path = base + ".flac"
    else:
        output_path = os.path.abspath(output_path)

    # Find QQ Music process
    pid, name = find_qqmusic_process()
    if pid is None:
        raise RuntimeError(
            "QQ Music is not running. Please start QQ Music first, "
            "then try again."
        )

    print(f"Found QQ Music: {name} (PID: {pid})")
    print(f"Decrypting: {input_path}")
    print(f"Output: {output_path}")

    result = attach_and_decrypt(pid, input_path, output_path)

    if result.get('status') == 0:
        size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        print(f"Success! Output: {output_path} ({size:,} bytes)")
        return True, output_path
    else:
        error = result.get('error', 'unknown error')
        print(f"Failed: {error}")
        return False, error


def batch_decode(input_dir: str, output_dir: Optional[str] = None) -> None:
    """Batch decode all mflac files in a directory.

    Args:
        input_dir: Directory containing encrypted mflac/mgg files.
        output_dir: Optional output directory. Defaults to input_dir/decoded.

    Raises:
        NotADirectoryError: If input_dir does not exist.
        RuntimeError: If QQ Music is not running.
    """
    if not os.path.isdir(input_dir):
        raise NotADirectoryError(f"Directory not found: {input_dir}")

    if output_dir is None:
        output_dir = os.path.join(input_dir, "decoded")
    os.makedirs(output_dir, exist_ok=True)

    mflac_files = [f for f in os.listdir(input_dir) if f.endswith(('.mflac', '.mgg'))]
    if not mflac_files:
        print("No .mflac/.mgg files found.")
        return

    print(f"Found {len(mflac_files)} mflac files")

    # Find QQ Music first
    pid, name = find_qqmusic_process()
    if pid is None:
        raise RuntimeError("QQ Music is not running. Please start QQ Music first.")

    print(f"Connected to: {name} (PID: {pid})")

    session = frida.attach(pid)
    script = session.create_script(FRIDA_SCRIPT)
    script.load()

    try:
        api = script.exports_sync

        success_count = 0
        for fname in mflac_files:
            src = os.path.join(input_dir, fname)
            dst = os.path.join(output_dir, os.path.splitext(fname)[0] + ".flac")
            print(f"\nDecrypting: {fname}")

            result = api.decrypt(src, dst)

            if result.get('status') == 0:
                size = os.path.getsize(dst) if os.path.exists(dst) else 0
                print(f"  Success! ({size:,} bytes)")
                success_count += 1
            else:
                print(f"  Failed: {result.get('error', 'unknown')}")

        print(f"\nDone: {success_count}/{len(mflac_files)} files decrypted")
    finally:
        script.unload()
        session.detach()


def main() -> None:
    """CLI entry point for Frida-based mflac decryption."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python frida_decrypt.py <input.mflac> [output.flac]")
        print("  python frida_decrypt.py --batch <input_dir> [output_dir]")
        sys.exit(1)

    if sys.argv[1] == "--batch":
        input_dir = sys.argv[2] if len(sys.argv) > 2 else "."
        output_dir = sys.argv[3] if len(sys.argv) > 3 else None
        batch_decode(input_dir, output_dir)
    else:
        input_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        decode_mflac(input_path, output_path)


if __name__ == "__main__":
    main()
