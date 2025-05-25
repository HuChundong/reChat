# WxDat Decrypt

> 一个用于解密微信图片文件的工具
> 
> 本项目仅供学习交流使用，**可能存在封号风险，请勿用于非法用途**，否则后果自负。
> 
> **最近更新**: 代码已上传

## 功能简介

- 将微信缓存的 `.dat` 文件解密为原始图片格式。
- 支持微信 3.x 和 4.x 多种加密版本。

## 特性

- 支持微信 3.x 与 4.0 版本解密
- 支持微信 4.0.3 新的加密格式，**可通过模板文件自动查找密钥**
- 可以通过指定密钥解密

## 安装

使用 dat2img.py 文件，或者
从 [Releases](https://github.com/recarto404/reChat/releases) 页面下载预编译的二进制文件。

## 使用方法

```bash
dat2img -i <input_path> -o <output_path> [-v <version>] [-x <xorKey> -a <aesKey> | -f <template>]
```
`-f` 命令会在同目录下生成 `key.dat` AES 密钥缓存文件，第二次使用时将优先尝试缓存密钥。

### 参数说明

- `-i, --input`  
  输入文件路径（`.dat` 格式）。

- `-o, --output`  
  输出文件路径（如 `output.jpg`、`output.png`）。

- `-v, --version`  
  `.dat` 文件版本（整型）。**可选项，不使用将自动判断文件加密版本**
  - `0`：纯 XOR 解密  
  - `1`：V1 版本，文件头为 `b"\x07\x08V1\x08\x07"`  
  - `2`：V2 版本，文件头为 `b"\x07\x08V2\x08\x07"`

- `-x, --xorKey`  
  异或密钥（整型）。**与 `-f` 参数二选一**。

- `-a, --aesKey`  
  AES 密钥（16位字符串）。**与 `-f` 参数二选一**。

- `-f, --findKey`  
  模板文件路径。用于辅助查找密钥。建议选用 `_t.dat` 结尾的文件作为模板文件。**与 `-x` 和 `-a` 参数二选一**。

## 示例

0. **推荐**: 解密微信图片，自动选择加密版本，并使用模板文件查找密钥解密
   ```bash
   dat2img -i wx_image.dat -o wx_image.jpg -f template_t.dat
   ```

1. 解密 V1 版本微信图片，手动指定异或密钥解密
   ```bash
   dat2img -i wx_image.dat -o wx_image.jpg -v 2 -x 101
   ```

2. 解密 V2 版本微信图片，手动指定密钥解密
   ```bash
   dat2img -i wx_image.dat -o wx_image.jpg -v 2 -x 101 -a abcdefgh12345678
   ```

3. 解密 V2 版本微信图片，使用模板文件查找密钥解密
   ```bash
   dat2img -i wx_image.dat -o wx_image.jpg -v 2 -f template_t.dat
   ```

## 常见问题

- **Q:** 解密后图片无法打开？  
  **A:** 请确认 `version`, `xorKey`, `aesKey` 设置正确。如果使用 `-f` 参数，请确保模板文件有效。

- **Q:** 如何选择合适的模板文件？  
  **A:** 建议使用与目标 `.dat` 文件来自同一微信账号的 `_t.dat` 文件。通常，同一个微信账号使用相同的密钥。

- **Q:** 支持批量解密吗？  
  **A:** 当前版本仅支持单文件操作，可通过 shell 脚本或批处理自行循环调用。

- **Q:** 为何设置正确但解密的图片仍无法查看?  
  **A:** 查看文件前四个字节是否为 b"wxgf"，若是，则在计划之中。

## 计划

- [ ] 实现对 `wxgf` 格式微信图片的解码支持  
- [ ] 增加批量处理功能，一次性解密多个文件

## 贡献

欢迎提交 Issue！

## 许可证

本项目采用 [MIT License](./LICENSE) 开源协议。
