import struct

from Crypto.Cipher import AES
from Crypto.Util import Padding


def decrypt_dat_v3(input_path: str, output_path: str, xor_key: int) -> None:

    # 读取加密文件的内容
    with open(input_path, "rb") as f:
        data = f.read()

    # 将解密后的数据写入输出文件
    with open(output_path, "wb") as f:
        f.write(bytes(b ^ xor_key for b in data))


def decrypt_dat_v4(
    input_path: str,
    output_path: str,
    xor_key: int,
    aes_key: bytes,
) -> None:

    # 读取加密文件的内容
    with open(input_path, "rb") as f:
        header, data = f.read(0xF), f.read()
        signature, aes_size, xor_size = struct.unpack("<6sLLx", header)
        aes_size += AES.block_size - aes_size % AES.block_size

        aes_data = data[:aes_size]
        xor_data = data[-xor_size:]
        raw_data = data[aes_size:-xor_size]

    cipher = AES.new(aes_key, AES.MODE_ECB)
    decrypted_data = Padding.unpad(cipher.decrypt(aes_data), AES.block_size)

    xored_data = bytes(b ^ xor_key for b in xor_data)

    # 将解密后的数据写入输出文件
    with open(output_path, "wb") as f:
        f.write(decrypted_data)
        f.write(raw_data)
        f.write(xored_data)
