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
import frida

# Frida JavaScript payload extracted from sunwoo.exe
FRIDA_SCRIPT = r"""
var _globalCache = {};

function getCachedNativeFunction(name, addr, retType, argTypes, abi) {
    if (!_globalCache[name]) {
        _globalCache[name] = new NativeFunction(addr, retType, argTypes, abi);
    }
    return _globalCache[name];
}

function clearGlobalCache() {
    _globalCache = {};
}

const TARGET_DLL = "QQMusicCommon.dll";

var targetModule = Process.getModuleByName(TARGET_DLL);

var EncAndDesMediaFileConstructorAddr = targetModule.getExportByName(
    "??0EncAndDesMediaFile@@QAE@XZ"
);
var EncAndDesMediaFileDestructorAddr = targetModule.getExportByName(
    "??1EncAndDesMediaFile@@QAE@XZ"
);
var EncAndDesMediaFileOpenAddr = targetModule.getExportByName(
    "?Open@EncAndDesMediaFile@@QAE_NPB_W_N1@Z"
);
var EncAndDesMediaFileGetSizeAddr = targetModule.getExportByName(
    "?GetSize@EncAndDesMediaFile@@QAEKXZ"
);
var EncAndDesMediaFileReadAddr = targetModule.getExportByName(
    "?Read@EncAndDesMediaFile@@QAEKPAEK_J@Z"
);

var EncAndDesMediaFileConstructor = getCachedNativeFunction(
    "Constructor", EncAndDesMediaFileConstructorAddr,
    "pointer", ["pointer"], "thiscall"
);
var EncAndDesMediaFileDestructor = getCachedNativeFunction(
    "Destructor", EncAndDesMediaFileDestructorAddr,
    "void", ["pointer"], "thiscall"
);
var EncAndDesMediaFileOpen = getCachedNativeFunction(
    "Open", EncAndDesMediaFileOpenAddr,
    "bool", ["pointer", "pointer", "bool", "bool"], "thiscall"
);
var EncAndDesMediaFileGetSize = getCachedNativeFunction(
    "GetSize", EncAndDesMediaFileGetSizeAddr,
    "uint32", ["pointer"], "thiscall"
);
var EncAndDesMediaFileRead = getCachedNativeFunction(
    "Read", EncAndDesMediaFileReadAddr,
    "uint", ["pointer", "pointer", "uint32", "uint64"], "thiscall"
);

const kernel32 = Process.getModuleByName("kernel32.dll");
var CreateFileW = getCachedNativeFunction(
    "CreateFileW", kernel32.getExportByName("CreateFileW"),
    'pointer', ['pointer', 'uint', 'uint', 'pointer', 'uint', 'uint', 'pointer']
);
var WriteFile = getCachedNativeFunction(
    "WriteFile", kernel32.getExportByName("WriteFile"),
    'bool', ['pointer', 'pointer', 'uint', 'pointer', 'pointer']
);
var CloseHandle = getCachedNativeFunction(
    "CloseHandle", kernel32.getExportByName("CloseHandle"),
    'bool', ['pointer']
);

function convertToWideChar(str) {
    return Memory.allocUtf16String(str);
}

rpc.exports = {
    decrypt: function (srcFileName, tmpFileName) {
        var EncAndDesMediaFileObject = null;
        var fileHandle = null;
        var buffer = null;
        var bytesWritten = null;

        try {
            console.log("[+] start task: ", srcFileName, " -> ", tmpFileName);

            EncAndDesMediaFileObject = Memory.alloc(0x28);
            EncAndDesMediaFileConstructor(EncAndDesMediaFileObject);

            var fileNameUtf16 = convertToWideChar(srcFileName);
            var result = EncAndDesMediaFileOpen(EncAndDesMediaFileObject, fileNameUtf16, 1, 0);

            if (!result) {
                console.log("[-] open file failed");
                EncAndDesMediaFileDestructor(EncAndDesMediaFileObject);
                return { status: 1, error: "failed to open file" };
            }

            var fileSize = EncAndDesMediaFileGetSize(EncAndDesMediaFileObject);
            console.log("[+] source file size: ", fileSize);

            if (fileSize === 0) {
                EncAndDesMediaFileDestructor(EncAndDesMediaFileObject);
                return { status: 1, error: "file size is 0" };
            }

            var tmpFileNameUtf16 = convertToWideChar(tmpFileName);
            const GENERIC_WRITE = 0x40000000;
            const FILE_SHARE_READ = 0x00000001;
            const CREATE_ALWAYS = 2;
            const FILE_ATTRIBUTE_NORMAL = 0x80;

            fileHandle = CreateFileW(
                tmpFileNameUtf16, GENERIC_WRITE, FILE_SHARE_READ,
                ptr(0), CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, ptr(0)
            );

            const INVALID_HANDLE_VALUE = ptr(-1);
            if (fileHandle.equals(INVALID_HANDLE_VALUE)) {
                EncAndDesMediaFileDestructor(EncAndDesMediaFileObject);
                return { status: 1, error: "failed to create output file" };
            }

            const CHUNK_SIZE = 512 * 1024;
            buffer = Memory.alloc(CHUNK_SIZE);
            bytesWritten = Memory.alloc(8);
            var totalProcessed = 0;

            while (totalProcessed < fileSize) {
                var currentChunkSize = Math.min(CHUNK_SIZE, fileSize - totalProcessed);
                var readSize = EncAndDesMediaFileRead(
                    EncAndDesMediaFileObject, buffer, currentChunkSize, totalProcessed
                );

                if (readSize !== currentChunkSize) {
                    CloseHandle(fileHandle);
                    EncAndDesMediaFileDestructor(EncAndDesMediaFileObject);
                    return { status: 1, error: "read chunk failed" };
                }

                var writeResult = WriteFile(
                    fileHandle, buffer, currentChunkSize, bytesWritten, ptr(0)
                );

                if (!writeResult) {
                    CloseHandle(fileHandle);
                    EncAndDesMediaFileDestructor(EncAndDesMediaFileObject);
                    return { status: 1, error: "write failed" };
                }

                totalProcessed += currentChunkSize;
            }

            console.log("[+] decrypt success, total processed:", totalProcessed, "bytes");

            try {
                if (fileHandle && !fileHandle.equals(ptr(-1))) {
                    CloseHandle(fileHandle);
                    fileHandle = null;
                }
                if (EncAndDesMediaFileObject) {
                    EncAndDesMediaFileDestructor(EncAndDesMediaFileObject);
                    EncAndDesMediaFileObject = null;
                }
                buffer = null;
                bytesWritten = null;
                clearGlobalCache();
                if (typeof gc === 'function') { gc(); }
            } catch (cleanupError) {}

            return { status: 0 };

        } catch (error) {
            console.log("[-] decrypt error:", error);
            try {
                if (fileHandle && !fileHandle.equals(ptr(-1))) { CloseHandle(fileHandle); }
                if (EncAndDesMediaFileObject) { EncAndDesMediaFileDestructor(EncAndDesMediaFileObject); }
                buffer = null;
                bytesWritten = null;
                clearGlobalCache();
            } catch (cleanupError) {}
            return { status: 1, error: error.toString() };
        }
    },
};
"""


def find_qqmusic_process():
    """Find QQ Music process."""
    try:
        device = frida.get_local_device()
        processes = device.enumerate_processes()
        for proc in processes:
            if 'QQMusic' in proc.name:
                return proc.pid, proc.name
    except Exception as e:
        print(f"Error finding QQ Music: {e}")
    return None, None


def attach_and_decrypt(pid, src_path, dst_path):
    """Attach to QQ Music and decrypt a file using Frida."""
    session = frida.attach(pid)
    script = session.create_script(FRIDA_SCRIPT)
    script.load()

    api = script.exports_sync
    result = api.decrypt(src_path, dst_path)

    script.unload()
    session.detach()

    return result


def decode_mflac(input_path, output_path=None):
    """
    Decode an mflac file to flac using Frida + QQ Music's DLL.

    Requires QQ Music to be running.
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


def batch_decode(input_dir, output_dir=None):
    """Batch decode all mflac files in a directory."""
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

    script.unload()
    session.detach()

    print(f"\nDone: {success_count}/{len(mflac_files)} files decrypted")


if __name__ == "__main__":
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
