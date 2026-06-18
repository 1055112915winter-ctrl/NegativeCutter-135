#!/usr/bin/env bash
# build.sh — 一键构建 NegativeCutter-135 分发包
#
# 依赖：
#   - Python 3
#   - pip install pyinstaller
#   - 已安装 numpy、Pillow、rawpy（可选）等 filmcrop 依赖
#
# 用法：
#   cd NegativeCutter-135.lrplugin
#   ./build.sh
#
# 输出：
#   ../NegativeCutter-135-v{VERSION}.zip

set -euo pipefail

# 解析版本号
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(python3 - <<'PY'
import sys
sys.path.insert(0, '.')
from filmcrop import __version__
print(__version__)
PY
)

PLUGIN_NAME="NegativeCutter-135"
OUTPUT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_ZIP="${OUTPUT_DIR}/${PLUGIN_NAME}-v${VERSION}.zip"

echo "==> 构建 NegativeCutter-135 v${VERSION}"
echo "==> 插件目录: $SCRIPT_DIR"
echo "==> 输出包:   $OUTPUT_ZIP"

# 1. 清理旧构建产物
echo "==> 清理旧构建产物..."
rm -rf build dist
rm -f "$OUTPUT_ZIP"

# 2. 用 PyInstaller 构建 onedir 可执行文件
echo "==> 运行 PyInstaller..."
python3 -m PyInstaller NegativeCutter.spec

# 3. 检查 PyInstaller 输出并复制到插件根目录
# 优先使用 onedir 模式（dist/NegativeCutter/ 目录），避免 onefile 在 Lightroom
# 沙箱子进程中自解压失败（退出码 32512 / semaphore 初始化错误）。
EXE_DIR=""
if [[ -d "dist/NegativeCutter" && -x "dist/NegativeCutter/NegativeCutter" ]]; then
  EXE_DIR="dist/NegativeCutter"
elif [[ -x "dist/NegativeCutter" ]]; then
  # 兼容旧的 onefile 输出
  EXE_DIR="dist/NegativeCutter"
fi

if [[ -z "$EXE_DIR" ]]; then
  echo "ERROR: 可执行文件未生成于 dist/NegativeCutter" >&2
  exit 1
fi

echo "==> 可执行文件生成成功: $EXE_DIR"
echo "==> 复制可执行文件到插件根目录..."
rm -rf "./NegativeCutter"
# -L 强制跟随符号链接：PyInstaller onedir 在 macOS 上会对 Python.framework 等使用
# 符号链接，但 macOS 的代码签名和安全策略可能对符号链接有额外限制；确保插件内是
# 普通文件/目录。
cp -RL "$EXE_DIR" "./NegativeCutter"
chmod +x "./NegativeCutter/NegativeCutter"

# 4. 清理 Python 字节码缓存，避免打包进 zip
echo "==> 清理 __pycache__..."
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find . -type f -name '*.pyc' -delete 2>/dev/null || true
find . -type f -name '*.pyo' -delete 2>/dev/null || true

# 5. 打包（注意：不要把 dist/ 和 build/ 打进 zip）
echo "==> 打包插件..."
TMP_PACKAGE_DIR="${TMPDIR:-/tmp}/filmcrop-build-$$"
rm -rf "$TMP_PACKAGE_DIR"
mkdir -p "$TMP_PACKAGE_DIR"
trap 'rm -rf "$TMP_PACKAGE_DIR"' EXIT

# 复制插件目录到临时目录，并剔除开发/构建产物
cp -R "$SCRIPT_DIR" "$TMP_PACKAGE_DIR/${PLUGIN_NAME}.lrplugin"
cd "$TMP_PACKAGE_DIR/${PLUGIN_NAME}.lrplugin"
rm -rf build dist __pycache__ .DS_Store
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find . -type f -name '*.pyc' -delete 2>/dev/null || true
find . -type f -name '*.pyo' -delete 2>/dev/null || true

# A dirty source tree must never leak development artifacts into a release.
forbidden=$(find . \
  \( -name tests -o -name WORK -o -name CLAUDE.md -o \
     -name debug_visualize.py -o -name detect_debug.log \) -print)
if [[ -n "$forbidden" ]]; then
  echo "ERROR: forbidden development artifacts remain in release stage:" >&2
  echo "$forbidden" >&2
  exit 1
fi

# Every Lightroom menu entry must resolve inside the staged plugin.
python3 - <<'PY'
import re
from pathlib import Path

root = Path('.')
info = (root / 'Info.lua').read_text(encoding='utf-8')
missing = [p for p in re.findall(r'''file\s*=\s*["']([^"']+)["']''', info)
           if not (root / p).is_file()]
if missing:
    raise SystemExit('ERROR: Info.lua references missing files: ' + ', '.join(missing))
PY

# 6. 生成 zip
cd "$TMP_PACKAGE_DIR"
zip -r -q "$OUTPUT_ZIP" "${PLUGIN_NAME}.lrplugin"

echo "==> 构建完成: $OUTPUT_ZIP"
ls -lh "$OUTPUT_ZIP"
