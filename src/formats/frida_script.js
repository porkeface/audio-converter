/**
 * Frida script for decrypting mflac files via QQ Music's QQMusicCommon.dll
 *
 * This script hooks into QQ Music's process and uses the EncAndDesMediaFile
 * API to decrypt encrypted mflac/mgg audio files.
 *
 * Requirements:
 * - QQ Music must be running
 * - QQMusicCommon.dll must be loaded in the process
 */

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
