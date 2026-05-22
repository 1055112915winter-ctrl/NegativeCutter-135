#!/usr/bin/env python3
"""
FilmCrop 缩略图分析 - 兼容 CLI 入口
版本: v2.4.0 - 核心算法已提取到 filmcrop 包

向后兼容原有命令行接口：
    python3 detect_thumb.py <thumb_path> [--frames N] [--cleanup-scale X.X] [--original <path>]
"""

import json
import sys
import traceback
from pathlib import Path

# Prevent Python from writing bytecode caches that can mask source changes
sys.dont_write_bytecode = True

# Diagnostic logging for Lightroom debugging
_LOG_PATH = Path(__file__).parent / "detect_debug.log"
try:
    _LOG_PATH.write_text("detect_thumb.py started\n", encoding="utf-8")
except Exception:
    pass

def _log(msg):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

# Force local filmcrop package to take precedence over any system installation
_script_dir = str(Path(__file__).parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)
elif sys.path[0] != _script_dir:
    sys.path.remove(_script_dir)
    sys.path.insert(0, _script_dir)

_detector_mtime = 0
try:
    from filmcrop.detector import analyze_image
    _log("import analyze_image OK")
    import filmcrop.detector as _detector_mod
    _detector_path = getattr(_detector_mod, "__file__", "unknown")
    try:
        _detector_mtime = int(Path(_detector_path).stat().st_mtime)
    except (OSError, ValueError):
        _detector_mtime = 0
except ImportError:
    _log("ImportError from filmcrop, trying fallback paths")
    fallback_dirs = [_script_dir]
    for d in fallback_dirs:
        if d not in sys.path:
            sys.path.insert(0, d)
    try:
        from filmcrop.detector import analyze_image
        import filmcrop.detector as _detector_mod
        _detector_path = getattr(_detector_mod, "__file__", "unknown")
        try:
            _detector_mtime = int(Path(_detector_path).stat().st_mtime)
        except (OSError, ValueError):
            _detector_mtime = 0
        _log("import analyze_image OK (fallback)")
    except Exception as _e:
        _log(f"import failed: {_e}")
        print(json.dumps({"error": f"导入 filmcrop 失败: {_e}", "traceback": traceback.format_exc(), "sys_executable": sys.executable, "sys_path": sys.path[:8], "cwd": str(Path.cwd()), "script_dir": _script_dir}, separators=(",", ":")))
        sys.exit(1)


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
    format_hint = None

    _FORMAT_MAP = {
        "35mm": 3 / 2, "645": 4 / 3, "6x6": 1.0, "6x7": 7 / 6,
        "6x8": 8 / 6, "6x9": 3 / 2, "4x5": 5 / 4,
    }

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
        elif arg == "--format" and i + 1 < len(sys.argv):
            format_hint = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    format_ratio = _FORMAT_MAP.get(format_hint) if format_hint else None

    if not Path(thumb_path).exists():
        result = {"error": f"文件不存在: {thumb_path}"}
        print(json.dumps(result, separators=(",", ":")))
        sys.exit(1)

    try:
        _log(f"analyze_image start: thumb={thumb_path}, frames={expected_frames}, original={original_path}")
        result = analyze_image(thumb_path, expected_frames, cleanup_scale, original_path, aspect_ratio=format_ratio)
        _log(f"analyze_image OK: frameCount={result.get('frameCount')}")
        # Inject diagnostic info so Lightroom (or CLI) can verify which code ran
        result["_diag"] = {
            "pythonExecutable": sys.executable,
            "pythonVersion": sys.version.split()[0],
            "detectorPath": _detector_path,
            "detectorMtime": _detector_mtime,
            "scriptDir": _script_dir,
        }
        output = json.dumps(result, separators=(",", ":"))
        print(output)
        _log(f"output length: {len(output)}")
        _log(f"output JSON: {output[:2000]}")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"analyze_image FAILED: {e}\n{tb}")
        result = {"error": str(e), "traceback": tb}
        print(json.dumps(result, separators=(",", ":")))
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as _e:
        tb = traceback.format_exc()
        _log(f"main FAILED: {_e}\n{tb}")
        print(json.dumps({"error": f"未预期的错误: {_e}", "traceback": tb}, separators=(",", ":")))
        sys.exit(1)
