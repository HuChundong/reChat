import argparse
import asyncio
import ctypes
import struct
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from functools import lru_cache
from multiprocessing import freeze_support
from pathlib import Path
from typing import Any

import pymem
import yara
from Crypto.Cipher import AES
from Crypto.Util import Padding
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from hypercorn.asyncio import serve
from hypercorn.config import Config

# 定义必要的常量
PROCESS_ALL_ACCESS = 0x1F0FFF
PAGE_READWRITE = 0x04
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000

# Constants
IV_SIZE = 16
HMAC_SHA256_SIZE = 64
HMAC_SHA512_SIZE = 64
KEY_SIZE = 32
AES_BLOCK_SIZE = 16
ROUND_COUNT = 256000
PAGE_SIZE = 4096
SALT_SIZE = 16

finish_flag = False


# 定义 MEMORY_BASIC_INFORMATION 结构
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]


# Windows API Constants
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

# Load Windows DLLs
kernel32 = ctypes.windll.kernel32


# 打开目标进程
def open_process(pid):
    return ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)


# 读取目标进程内存
def read_process_memory(process_handle, address, size):
    buffer = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t(0)
    success = ctypes.windll.kernel32.ReadProcessMemory(
        process_handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read)
    )
    if not success:
        return None
    return buffer.raw


# 获取所有内存区域
def get_memory_regions(process_handle):
    regions = []
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    while ctypes.windll.kernel32.VirtualQueryEx(
        process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)
    ):
        if mbi.State == MEM_COMMIT and mbi.Type == MEM_PRIVATE:
            regions.append((mbi.BaseAddress, mbi.RegionSize))
        address += mbi.RegionSize
    return regions


# 导入 Windows API 函数
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
ReadProcessMemory.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


@lru_cache
def verify(encrypted: bytes, key: bytes) -> bool:
    aes_key = key[:16]
    cipher = AES.new(aes_key, AES.MODE_ECB)
    text = cipher.decrypt(encrypted)

    if text.startswith(b"\xff\xd8\xff"):
        return True
    else:
        return False


def search_memory_chunk(process_handle, base_address, region_size, encrypted, rules):
    """搜索单个内存块"""
    memory = read_process_memory(process_handle, base_address, region_size)
    if not memory:
        return None

    matches = rules.match(data=memory)
    if matches:
        for match in matches:
            if match.rule == "AesKey":
                for string in match.strings:
                    for instance in string.instances:
                        content = instance.matched_data[1:-1]
                        if verify(encrypted, content):
                            return content[:16]
    return None


def get_aes_key(encrypted: bytes, pid: int) -> Any:
    process_handle = open_process(pid)
    if not process_handle:
        print(f"无法打开进程 {pid}")
        return ""

    # 编译YARA规则
    rules_key = r"""
    rule AesKey {
        strings:
            $pattern = /[^a-z0-9][a-z0-9]{32}[^a-z0-9]/
        condition:
            $pattern
    }
    """
    rules = yara.compile(source=rules_key)

    # 获取内存区域
    process_infos = get_memory_regions(process_handle)

    # 创建线程池
    found_result = threading.Event()
    result = [None]

    def process_chunk(args):
        if found_result.is_set():
            return None
        base_address, region_size = args
        res = search_memory_chunk(
            process_handle, base_address, region_size, encrypted, rules
        )
        if res:
            result[0] = res
            found_result.set()
        return res

    with ThreadPoolExecutor(max_workers=min(32, len(process_infos))) as executor:
        executor.map(process_chunk, process_infos)

    CloseHandle(process_handle)
    return result[0]


def dump_wechat_info_v4(encrypted: bytes, pid: int) -> bytes:
    process_handle = open_process(pid)
    if not process_handle:
        raise RuntimeError(f"无法打开微信进程: {pid}")

    result = get_aes_key(encrypted, pid)
    if isinstance(result, bytes):
        return result[:16]
    else:
        raise RuntimeError("未找到 AES 密钥")


def find_key(weixin_dir: Path):
    """
    遍历目录下文件, 找到至多 16 个 (.*)_t.dat 文件,
    收集最后两位字节, 选择出现次数最多的两个字节.
    """
    print(f"[+] 读取文件, 收集密钥...")

    # 查找所有 _t.dat 结尾的文件
    template_files = list(weixin_dir.rglob("*_t.dat"))[:16]

    if not template_files:
        raise RuntimeError("未找到模板文件")

    # 收集所有文件最后两个字节
    last_bytes_list = []
    for file in template_files:
        try:
            with open(file, "rb") as f:
                # 读取最后两个字节
                f.seek(-2, 2)
                last_bytes = f.read(2)
                last_bytes_list.append(last_bytes)
        except Exception as e:
            print(f"[-] 读取文件 {file} 失败: {e}")
            continue

    if not last_bytes_list:
        raise RuntimeError("未能成功读取任何模板文件")

    # 使用 Counter 统计最常见的字节组合
    counter = Counter(last_bytes_list)
    most_common = counter.most_common(1)[0][0]

    x, y = most_common
    if (xor_key := x ^ 0xFF) == y ^ 0xD9:
        print(f"[+] 找到 XOR 密钥: 0x{xor_key:02X}")
    else:
        raise RuntimeError("未能找到 XOR 密钥")

    for file in template_files:
        with open(file, "rb") as f:
            # 检查文件头
            if f.read(6) != b"\x07\x08V2\x08\x07":
                continue

            # 检查文件尾
            f.seek(-2, 2)
            if f.read(2) != most_common:
                continue

            # 读取 AES 密钥
            f.seek(0xF)
            ciphertext = f.read(16)
            break
    else:
        raise RuntimeError("未能成功读取任何模板文件")

    try:
        pm = pymem.Pymem("Weixin.exe")
        pid = pm.process_id
        assert isinstance(pid, int)
    except:
        raise RuntimeError("找不到微信进程")

    aes_key = dump_wechat_info_v4(ciphertext, pid)
    print(f"[+] 找到 AES 密钥: {aes_key}")

    return xor_key, aes_key


def decrypt_dat_v3(input_path: str | Path, xor_key: int) -> bytes:
    # 读取加密文件的内容
    with open(input_path, "rb") as f:
        data = f.read()

    # 将解密后的数据写入输出文件
    return bytes(b ^ xor_key for b in data)


def decrypt_dat_v4(input_path: str | Path, xor_key: int, aes_key: bytes) -> bytes:
    # 读取加密文件的内容
    with open(input_path, "rb") as f:
        header, data = f.read(0xF), f.read()
        signature, aes_size, xor_size = struct.unpack("<6sLLx", header)
        aes_size += AES.block_size - aes_size % AES.block_size

        aes_data = data[:aes_size]
        raw_data = data[aes_size:]

    cipher = AES.new(aes_key, AES.MODE_ECB)
    decrypted_data = Padding.unpad(cipher.decrypt(aes_data), AES.block_size)

    if xor_size > 0:
        raw_data = data[aes_size:-xor_size]
        xor_data = data[-xor_size:]
        xored_data = bytes(b ^ xor_key for b in xor_data)
    else:
        xored_data = b""

    # 将解密后的数据写入输出文件
    return decrypted_data + raw_data + xored_data


def decrypt_dat(input_file: str | Path) -> int:
    with open(input_file, "rb") as f:
        signature = f.read(6)

    match signature:
        case b"\x07\x08V1\x08\x07":
            return 1

        case b"\x07\x08V2\x08\x07":
            return 2

        case _:
            return 0














app = FastAPI()

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WeixinInfo:
    weixin_dir: Path
    xor_key: int
    aes_key: bytes


@app.get("/decrypt/{file_path:path}")
async def decrypt(file_path: str) -> Response:
    global info

    full_path = info.weixin_dir / file_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    print(f"[+] 解密文件 {full_path}...")
    
    version = decrypt_dat(full_path)
    print(f"[+] 加密版本: v{version}")
    match version:
        case 0:
            data = decrypt_dat_v3(full_path, info.xor_key)

        case 1:
            data = decrypt_dat_v4(full_path, info.xor_key, b"cfcd208495d565ef")

        case 2:
            data = decrypt_dat_v4(full_path, info.xor_key, info.aes_key)


    return Response(content=data, media_type="image/png")


info = WeixinInfo()

if __name__ == "__main__":
    freeze_support()

    parser = argparse.ArgumentParser(description="微信文件解密服务")
    parser.add_argument("-d", "--dir", help="微信文件目录路径")
    args = parser.parse_args()

    info.weixin_dir = Path(args.dir).resolve()

    if not info.weixin_dir.exists():
        print(f"[-] 错误：目录 {info.weixin_dir} 不存在")
        sys.exit(1)

    print(f"[+] 微信文件目录: {info.weixin_dir}")
    info.xor_key, info.aes_key = find_key(info.weixin_dir)

    config = Config()
    config.bind = ["127.0.0.1:49152"]
    print(f"[+] 服务启动在: http://127.0.0.1:49152")
    asyncio.run(serve(app, config))  # type: ignore
