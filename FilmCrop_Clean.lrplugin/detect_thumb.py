#!/usr/bin/env python3
"""
FilmCrop 缩略图分析 - 兼容 CLI 入口
版本: v2.0.0 - 核心算法已提取到 filmcrop 包

向后兼容原有命令行接口：
    python3 detect_thumb.py <thumb_path> [--frames N] [--cleanup-scale X.X] [--original <path>]
"""

import json
import sys
from pathlib import Path

try:
    from filmcrop.detector import analyze_image
except ImportError:
    # fallback: 如果 filmcrop 包未安装，从同级目录导入
    sys.path.insert(0, str(Path(__file__).parent))
    from filmcrop.detector import analyze_image


def main():
    if len(sys.argv) < 2:
        result = {
            "error": "用法: python3 detect_thumb.py <thumb_path> [--frames N] [--cleanup-scale X.X] [--original <path>]"
        }
        print(json.dumps(result, separators=(",", ":")))
        sys.exit(1)

    thumb_path = sys.argv[1]
    expected_frames = 6
    cleanup_scale = 0.5
    original_path = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--frames" and i + 1 < len(sys.argv):
            expected_frames = int(sys.argv[i + 1])
            i += 2
        elif arg == "--cleanup-scale" and i + 1 < len(sys.argv):
            cleanup_scale = float(sys.argv[i + 1])
            i += 2
        elif arg == "--original" and i + 1 < len(sys.argv):
            original_path = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    if not Path(thumb_path).exists():
        result = {"error": f"文件不存在: {thumb_path}"}
        print(json.dumps(result, separators=(",", ":")))
        sys.exit(1)

    try:
        result = analyze_image(thumb_path, expected_frames, cleanup_scale, original_path)
        print(json.dumps(result, separators=(",", ":")))
    except Exception as e:
        import traceback

        result = {"error": str(e), "traceback": traceback.format_exc()}
        print(json.dumps(result, separators=(",", ":")))
        sys.exit(1)


if __name__ == "__main__":
    main()
