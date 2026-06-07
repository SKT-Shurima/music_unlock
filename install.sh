#!/bin/bash
set -e

# 脚本所在目录（处理符号链接和相对路径）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_DIR="$HOME/.music-tool"
BIN_DIR="$HOME/bin"

echo "🎵 music-tool 安装（纯解密工具）"
echo "================================"
echo ""

# 创建目录
mkdir -p "$TOOL_DIR" "$BIN_DIR"

# 复制 Python 库和脚本
echo "→ 安装 Python 解密引擎..."
rm -rf "$TOOL_DIR/unlock_lib"
cp -r "$SCRIPT_DIR/unlock_lib" "$TOOL_DIR/"
cp "$SCRIPT_DIR/unlock.py" "$TOOL_DIR/"

# numpy 可选（加速 QMCv2 MAP 解密大文件）
if python3 -c "import numpy" 2>/dev/null; then
  echo "  ✓ numpy 已安装（MAP 解密加速）"
else
  echo "  ℹ numpy 未安装（可选；pip install numpy 可加速大文件）"
fi
# certifi 可选（QQ musicex 取 ekey 的 HTTPS 证书校验）
python3 -c "import certifi" 2>/dev/null \
  && echo "  ✓ certifi 已安装" \
  || echo "  ℹ certifi 未安装（QQ musicex 解密建议: pip install certifi）"

# 复制 WASM 桥接
echo "→ 安装 WASM 解密桥接..."
cp "$SCRIPT_DIR/wasm_bridge.js" "$TOOL_DIR/"
cp "$SCRIPT_DIR/package.json" "$TOOL_DIR/"

# 安装 Node.js 依赖
echo "→ 安装 Node.js 依赖..."
cd "$TOOL_DIR"
npm install --silent 2>&1 | tail -3

# 安装 shell 包装器
echo "→ 安装命令行工具..."
cp "$SCRIPT_DIR/music-tool" "$BIN_DIR/"
chmod +x "$BIN_DIR/music-tool"

echo ""
echo "✅ 安装完成！"
echo ""
echo "使用方法:"
echo "  music-tool setup                          初始化环境"
echo "  music-tool decrypt <输入目录> [输出目录]    解密音乐"
echo "  music-tool decrypt <目录> --cookie '...'   解密 QQ 新格式(musicex)"
echo ""
echo "首次使用请运行: music-tool setup"
