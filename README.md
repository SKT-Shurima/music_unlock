# 🎵 music-tool

加密音乐文件**解密**命令行工具 —— 专注解密,不扫描、不分类、不改动你的音乐库。

支持 QQ音乐、网易云、酷狗、酷我、虾米、咪咕、喜马拉雅等主流平台的加密格式，
并支持 QQ 音乐 PC 版 ≥19.5 的 **musicex / QMCv2 新格式**（需登录 cookie）。

## ✨ 特性

- **纯解密** — 输入目录 → 输出目录，绝不移动/删除/改动其他文件
- **多平台** — QQ / 网易云 / 酷狗 / 酷我 / 虾米 / 咪咕 / 喜马拉雅
- **支持 QQ 新格式 musicex** — 凭登录 cookie 在线获取 ekey 解密
- **跨平台** — macOS / Linux / Windows (WSL)

## 📋 支持的格式

| 平台 | 格式 | 是否需要 cookie |
|------|------|----------------|
| QQ 音乐(旧/内嵌密钥) | `.mflac` `.mgg` `.mggl` `.qmc*` `.mflach` `.bkc*` `.tm*` `.mmp4` | 否 |
| **QQ 音乐(新格式 musicex/QMCv2)** | `.mflac` `.mgg`（PC 版 ≥19.5 下载） | **是** |
| 网易云音乐 | `.ncm` `.uc` | 否 |
| 酷狗 | `.kgm` `.kgma` `.vpr` | 否 |
| 酷我 | `.kwm` | 否 |
| 虾米 | `.xm` | 否 |
| 咪咕 | `.mg3d` | 否 |
| 喜马拉雅 | `.x2m` `.x3m` | 否 |

## 🚀 快速开始

```bash
git clone https://github.com/SKT-Shurima/music_unlock.git
cd music_unlock
./install.sh
music-tool setup        # 初始化（安装解密依赖）
```

### 依赖

- **Python 3.8+** — 解密引擎
- **Node.js 18+** — WASM 解密模块（QQ 旧格式 / 酷狗）
- **numpy**（可选）— 加速 QQ musicex 大文件解密：`pip install numpy`
- **certifi**（可选，QQ musicex 建议）— HTTPS 证书：`pip install certifi`

## 📖 使用方法

```bash
music-tool decrypt <输入目录> [输出目录] [选项]
```

不指定输出目录时，默认输出到 `<输入目录>/decrypted`。

### 按元数据批量重命名

解密后文件名可能是 QQ 音乐的随机 ID（如 `F0M00006oypR46bcLX.flac`）。
`rename` 命令读取音频文件的 TITLE/ARTIST 元数据，自动重命名为 `歌曲名 - 歌手.ext`：

```bash
music-tool rename <目录> [--dry-run]
```

- `--dry-run` — 预览模式，只显示将会如何重命名，不实际修改文件
- 重名文件自动追加序号（如 `遗失的心跳 - 萧亚轩 (2).flac`）
- 依赖 ffprobe（ffmpeg 自带）；缺失时静默跳过

### 选项

| 选项 | 说明 |
|------|------|
| `--cookie '<qqmusic_key=...>'` | QQ 音乐登录 cookie（解密 musicex 新格式必需） |
| `--cookie-file <路径>` | 从文件读取 cookie |
| `--failed-dir <目录>` | 失败文件拷贝到此目录 |
| `--qq-db <路径>` | 指定本地 `qqmusic.sqlite`（默认自动检测 macOS 路径） |

也可用环境变量 `QQMUSIC_COOKIE` 代替 `--cookie`。

### 示例

```bash
# 其他平台 / QQ 旧格式（内嵌密钥，无需 cookie）
music-tool decrypt ~/Downloads/songs ~/Music/out

# QQ 新格式 musicex（需登录 cookie）
music-tool decrypt ~/Downloads/qq ~/Music/out --cookie 'qqmusic_key=XXXXXXXX'
```

## 🔑 如何获取 QQ 音乐 cookie（解密 musicex 必需）

QQ 音乐 PC 版 ≥19.5 下载的 `.mflac/.mgg` 采用 musicex/QMCv2 加密，**密钥不在文件里**，
需凭你的登录态从 QQ 音乐服务器获取。获取方式：

1. 浏览器登录 <https://y.qq.com>，确认已登录（你的会员账号）
2. 按 `F12` → **Application（应用）** → 左侧 **Cookies** → 点 `https://y.qq.com`
3. 复制 **`qqmusic_key`** 的值（或从某个 `musics.fcg` 请求里复制整行 `cookie`，更稳妥）
4. 作为 `--cookie` 传入

> 仅用于解密你自己账号有权访问的音乐，请勿用于侵权用途。

### songmid 的解析（musicex 工作原理简述）

- **musicex 文件**：尾部自带 songmid 与媒体文件名，直接调用 API 取 ekey
- **数字命名**（如 `101455-13.mgg`）：文件名数字即 song_id，自动查 API 获取
- **O 前缀**（如 `O4M0xxx.mgg`）：文件名含 media_mid，需查本地 `qqmusic.sqlite`
  反查 songmid（macOS 自动检测；不在本地库中的歌曲无法解密）

## 🏗️ 架构

```
music-tool (shell 包装器，仅 setup / decrypt)
  └── unlock.py (Python CLI 入口)
       └── engine.py (按扩展名分发)
            ├── qmc.py   → 智能路由:
            │     ├── 内嵌密钥(QTag/短key尾) → wasm_bridge.js → @xhacker/qmcwasm
            │     └── musicex/QMCv2 → qq_api.py(取 ekey) + qmc2.py(TEA+RC4/MAP 解密)
            ├── ncm.py   → 纯 Python + AES        (网易云)
            ├── kgm.py   → wasm_bridge.js          (酷狗)
            ├── kwm.py / xm.py / tm.py / mg3d.py / cache.py / ximalaya.py
            └── ...
```

新增模块：
- `unlock_lib/qmc2.py` — QMCv2 解密核心（ekey→RC4key 的 TC-TEA、RC4/MAP 流式解密，numpy 可选加速）
- `unlock_lib/qq_api.py` — QQ 音乐 ekey 获取、footer 解析、songmid 解析、本地 DB 反查

## ⚠️ 已知限制

- **QQ musicex 需要 cookie**：未提供 cookie 时只能解密内嵌密钥格式
- **库外歌曲**：O 前缀文件若其 media_mid 不在本地 QQ 音乐库（你从未在 QQ 操作过该歌），
  无法反查 songmid，因而无法取密钥
- **试听片段 / 版权受限**：服务器不发完整下载密钥（API `result=104003`），无法解密
- **JOOX 格式**（`.ofl_en`）：需用户手动提供设备 UUID，暂不支持

## 📄 许可证

MIT License
