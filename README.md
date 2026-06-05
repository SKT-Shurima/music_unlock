# 🎵 music-tool

一键解密/分类/清理加密音乐文件的命令行工具。

支持 QQ音乐、网易云、酷狗、酷我、虾米、咪咕、喜马拉雅等主流平台的加密格式。

## ✨ 特性

- **零配置** — 安装后直接使用，自动处理依赖
- **多格式** — 支持 30+ 种加密格式
- **智能分类** — 按曲风/场景自动归类
- **质量检查** — 自动识别音质受损文件
- **跨平台** — macOS / Linux / Windows (WSL)

## 📋 支持的格式

| 平台 | 格式 |
|------|------|
| QQ 音乐 | `.mflac` `.mgg` `.mggl` `.qmc*` `.mflach` `.bkc*` `.tm*` `.mmp4` |
| 网易云音乐 | `.ncm` `.uc` |
| 酷狗 | `.kgm` `.kgma` `.vpr` |
| 酷我 | `.kwm` |
| 虾米 | `.xm` |
| 咪咕 | `.mg3d` |
| 喜马拉雅 | `.x2m` `.x3m` |

## 🚀 快速开始

### macOS / Linux

```bash
git clone https://github.com/SKT-Shurima/music_unlock.git
cd music_unlock
./install.sh
music-tool setup
```

### 依赖

- **Python 3.8+** — 解密引擎和分类器
- **Node.js 18+** — WASM 解密模块（QQ音乐/酷狗）
- **openssl** — macOS/Linux 自带

## 📖 使用方法

```bash
music-tool setup               # 初始化环境（首次使用）
music-tool decrypt <目录>       # 解密目录中的加密音乐
music-tool classify <目录>      # 按曲风分类
music-tool check <目录>         # 检查音质异常
music-tool all <目录>           # 一键：解密→分类→检查
music-tool report              # 查看最近报告
music-tool clean               # 清理临时文件
```

### 示例

```bash
# 一键处理 QQ 音乐下载目录
music-tool all ~/Downloads/qqmusic

# 只解密
music-tool decrypt ~/Music/encrypted

# 检查已整理的音乐库
music-tool check ~/personal/music
```

## 🏗️ 架构

```
music-tool (shell 包装器)
  ├── unlock.py (Python CLI 入口)
  │   ├── qmc.py → wasm_bridge.js → @xhacker/qmcwasm  (QQ音乐)
  │   ├── kgm.py → wasm_bridge.js → @xhacker/kgmwasm  (酷狗)
  │   ├── ncm.py → 纯 Python + openssl AES           (网易云)
  │   ├── kwm.py → 纯 Python XOR                      (酷我)
  │   ├── xm.py  → 纯 Python                          (虾米)
  │   ├── tm.py  → 纯 Python                          (QQ旧版)
  │   ├── mg3d.py → 纯 Python                         (咪咕)
  │   └── cache.py → 纯 Python                        (缓存)
  └── Shell: classify / check / report
```

## ⚠️ 已知限制

- **musicex 格式**（QQ 音乐 PC 版 ≥19.51）：需要 QQ 音乐客户端运行时的本地密钥，暂不支持
- **JOOX 格式**（`.ofl_en`）：需要用户手动提供设备 UUID

## 📄 许可证

MIT License
