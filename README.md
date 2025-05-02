# WxDat Decrypt

> 一个用于解密微信图片文件的工具

## 功能简介

- 将微信缓存的 `.dat` 文件解密为原始图片格式。
- 支持多种加密版本与自定义 XOR 密钥。

## 特性

- 纯 XOR 解密
- 支持 V1/V2 两种官方文件头加密格式
- 可指定任意整数作为异或（XOR）密钥

## 安装

从 [Releases](https://github.com/recarto404/reChat/releases) 页面下载预编译的二进制文件。

## 使用方法

```bash
dat2img -i <input_path> -o <output_path> -v <version> -x <xorKey>
```

### 参数说明

- `-i, --input`  
  输入文件路径（`.dat` 格式）。

- `-o, --output`  
  输出文件路径（如 `output.jpg`、`output.png`）。

- `-v, --version`  
  `.dat` 文件版本（整型）。  
  - `0`：纯 XOR 解密  
  - `1`：V1 版本，文件头为 `b"\x07\x08V1\x08\x07"`  
  - `2`：V2 版本，文件头为 `b"\x07\x08V2\x08\x07"`

- `-x, --xorKey`  
  异或密钥（整型）。

## 示例

1. 纯 XOR 解密 
   ```bash
   dat2img -i wx_image.dat -o wx_image.jpg -v 0 -x 101
   ```

2. 解密 V1 版本微信图片  
   ```bash
   dat2img -i wx_image.dat -o wx_image.jpg -v 1 -x 101
   ```

3. 解密 V2 版本微信图片  
   ```bash
   dat2img -i wx_image.dat -o wx_image.jpg -v 2 -x 101
   ```

## 常见问题

- **Q:** 解密后图片无法打开？  
  **A:** 请确认 `version` 与 `xorKey` 设置正确，或尝试不同的 `xorKey`。

- **Q:** 支持批量解密吗？  
  **A:** 当前版本仅支持单文件操作，可通过 shell 脚本或批处理自行循环调用。

## 计划

- [ ] 开源完整代码
- [ ] 实现对 `wxgf` 格式微信图片的解码支持  
- [ ] 增加批量处理功能，一次性解密多个文件

## 贡献

欢迎提交 Issue！

## 许可证

本项目采用 [MIT License](./LICENSE) 开源协议。
