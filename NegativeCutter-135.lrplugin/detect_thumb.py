#!/usr/bin/env python3
"""
FilmCrop 缩略图分析 - 兼容 CLI 入口
版本: v2.5.0 - 核心算法已提取到 filmcrop 包

向后兼容原有命令行接口：
    python3 detect_thumb.py <thumb_path> [--frames N] [--cleanup-scale X.X] [--original <path>]
"""

import json
import os
import sys
import traceback
from pathlib import Path

# Prevent Python from writing bytecode caches that can mask source changes
sys.dont_write_bytecode = True

# File diagnostics are opt-in. Normal Lightroom runs already return structured
# diagnostics on stdout and must not write source paths beside the plugin.
_LOG_ENV = os.environ.get("NEGATIVECUTTER_DEBUG_LOG")
_LOG_PATH = Path(_LOG_ENV).expanduser() if _LOG_ENV else None
_MAX_LOG_BYTES = 512 * 1024

def _log(msg):
    if _LOG_PATH is None:
        return
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if _LOG_PATH.exists() and _LOG_PATH.stat().st_size > _MAX_LOG_BYTES:
            with open(_LOG_PATH, "rb") as existing:
                existing.seek(-(_MAX_LOG_BYTES // 2), 2)
                tail = existing.read()
            _LOG_PATH.write_bytes(tail)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

_log("detect_thumb.py started")

# Force local filmcrop package to take precedence over any system installation
_script_dir = str(Path(__file__).parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)
elif sys.path[0] != _script_dir:
    sys.path.remove(_script_dir)
    sys.path.insert(0, _script_dir)

def _load_detector():
    """Delay detector loading so preview rendering remains a lightweight path."""
    try:
        from filmcrop.detector import analyze_image
        import filmcrop.detector as detector_mod
    except ImportError:
        _log("ImportError from filmcrop, trying fallback paths")
        if _script_dir not in sys.path:
            sys.path.insert(0, _script_dir)
        from filmcrop.detector import analyze_image
        import filmcrop.detector as detector_mod
    detector_path = getattr(detector_mod, "__file__", "unknown")
    try:
        detector_mtime = int(Path(detector_path).stat().st_mtime)
    except (OSError, ValueError):
        detector_mtime = 0
    _log("import analyze_image OK")
    return analyze_image, detector_path, detector_mtime


def _preview_error(message):
    print(json.dumps({"error": str(message)}, separators=(",", ":")))
    print(str(message), file=sys.stderr)
    return 2


def _render_preview_cli(args):
    from filmcrop.preview import adjust_frames, render_preview

    required = ("input", "frames_json", "source_width", "source_height", "output")
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        return _preview_error("missing required preview arguments: " + ", ".join(missing))
    try:
        payload = json.loads(Path(args.frames_json).read_text(encoding="utf-8"))
        frames = payload.get("frames") if isinstance(payload, dict) else payload
        if not isinstance(frames, list):
            raise ValueError("frames JSON must be a list or an object with a frames list")
        adjusted = adjust_frames(frames, args.source_width, args.source_height, {
            "top": args.top_px, "bottom": args.bottom_px,
            "left": args.left_px, "right": args.right_px,
        })
        output = render_preview(args.input, adjusted, args.output)
    except Exception as exc:
        _log(f"render preview FAILED: {exc}\n{traceback.format_exc()}")
        return _preview_error(exc)
    print(json.dumps({"previewPath": str(output), "frameCount": len(adjusted), "frames": adjusted}, separators=(",", ":")))
    return 0


def main():
    if "--render-preview" in sys.argv[1:]:
        import argparse
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--render-preview", action="store_true")
        parser.add_argument("--input")
        parser.add_argument("--frames-json", dest="frames_json")
        parser.add_argument("--source-width", dest="source_width", type=int)
        parser.add_argument("--source-height", dest="source_height", type=int)
        parser.add_argument("--top-px", dest="top_px", type=float, default=0)
        parser.add_argument("--bottom-px", dest="bottom_px", type=float, default=0)
        parser.add_argument("--left-px", dest="left_px", type=float, default=0)
        parser.add_argument("--right-px", dest="right_px", type=float, default=0)
        parser.add_argument("--output")
        try:
            args = parser.parse_args(sys.argv[1:])
        except SystemExit:
            return _preview_error("invalid preview arguments")
        return _render_preview_cli(args)

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
    lr_width = None
    lr_height = None

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
        elif arg == "--lr-width" and i + 1 < len(sys.argv):
            lr_width = int(sys.argv[i + 1])
            i += 2
        elif arg == "--lr-height" and i + 1 < len(sys.argv):
            lr_height = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    if not Path(thumb_path).exists():
        result = {"error": f"文件不存在: {thumb_path}"}
        print(json.dumps(result, separators=(",", ":")))
        sys.exit(1)

    try:
        analyze_image, detector_path, detector_mtime = _load_detector()
        from negativecutter_core.formats import FILM_FORMATS

        format_ratio = (
            FILM_FORMATS[format_hint].aspect_ratio if format_hint else None
        )
        _log(f"analyze_image start: thumb={thumb_path}, frames={expected_frames}, original={original_path}")
        result = analyze_image(
            thumb_path,
            expected_frames,
            cleanup_scale,
            original_path,
            aspect_ratio=format_ratio,
            lr_width=lr_width,
            lr_height=lr_height,
            film_format=format_hint,
        )
        _log(f"analyze_image OK: frameCount={result.get('frameCount')}")
        # Inject diagnostic info so Lightroom (or CLI) can verify which code ran
        result["_diag"] = {
            "pythonExecutable": sys.executable,
            "pythonVersion": sys.version.split()[0],
            "detectorPath": detector_path,
            "detectorMtime": detector_mtime,
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
        diagnostics = getattr(e, "diagnostics", None)
        if isinstance(diagnostics, dict):
            result.update(diagnostics)
        print(json.dumps(result, separators=(",", ":")))
        sys.exit(1)


if __name__ == "__main__":
    try:
        status = main()
        if status:
            sys.exit(status)
    except SystemExit:
        raise
    except Exception as _e:
        tb = traceback.format_exc()
        _log(f"main FAILED: {_e}\n{tb}")
        print(json.dumps({"error": f"未预期的错误: {_e}", "traceback": tb}, separators=(",", ":")))
        sys.exit(1)
