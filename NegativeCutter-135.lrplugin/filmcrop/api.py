"""
FilmCrop local HTTP API server (FastAPI).

Endpoints:
  POST /analyze   → detect frames
  POST /crop      → export cropped images
  GET  /health    → service status
"""

from pathlib import Path
from typing import Any, List, Optional

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# Module-level server state
_request_count: int = 0
_server_instance: Any = None

app = FastAPI(title="FilmCrop API", version="2.4.3")

if HAS_FASTAPI:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


class AnalyzeRequest(BaseModel):
    image_path: str
    expected_frames: int = 6
    cleanup_scale: float = 0.5
    original_path: Optional[str] = None
    aspect_ratio: Optional[float] = None
    format_hint: Optional[str] = None
    lr_width: Optional[int] = None
    lr_height: Optional[int] = None


_FORMAT_RATIOS = {
    "35mm": 3 / 2,
    "645": 4 / 3,
    "6x6": 1.0,
    "6x7": 7 / 6,
    "6x8": 8 / 6,
    "6x9": 3 / 2,
    "4x5": 5 / 4,
}


def _resolve_aspect_ratio(req: "AnalyzeRequest") -> Optional[float]:
    """Explicit aspect_ratio wins over format_hint. format_hint='auto' falls
    through to detector auto-detection (None). Default is 3/2 to keep legacy
    callers (no fields set) byte-for-byte identical."""
    if req.aspect_ratio is not None:
        return float(req.aspect_ratio)
    hint = (req.format_hint or "").strip().lower()
    if not hint:
        return 3 / 2
    if hint == "auto":
        return None
    if hint in _FORMAT_RATIOS:
        return _FORMAT_RATIOS[hint]
    return 3 / 2


class CropRequest(BaseModel):
    image_path: str
    frames: list
    output_dir: str
    fmt: str = "tiff"
    quality: int = 95


def _inc_request() -> None:
    global _request_count
    _request_count += 1


@app.get("/health")
def health():
    _inc_request()
    return {"status": "ok", "service": "filmcrop"}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    from filmcrop.detector import analyze_image

    _inc_request()
    if not Path(req.image_path).exists():
        return {"error": f"file not found: {req.image_path}"}
    try:
        result = analyze_image(
            req.image_path,
            expected_frames=req.expected_frames,
            cleanup_scale=req.cleanup_scale,
            original_path=req.original_path,
            aspect_ratio=_resolve_aspect_ratio(req),
            lr_width=req.lr_width,
            lr_height=req.lr_height,
        )
        return result
    except Exception as e:
        import traceback
        result = {"error": str(e), "traceback": traceback.format_exc()}
        diagnostics = getattr(e, "diagnostics", None)
        if isinstance(diagnostics, dict):
            result.update(diagnostics)
        return result


@app.post("/crop")
def crop(req: CropRequest):
    from filmcrop.export import crop_and_save

    _inc_request()
    if not Path(req.image_path).exists():
        return {"error": f"file not found: {req.image_path}"}
    try:
        paths = crop_and_save(
            req.image_path,
            req.frames,
            req.output_dir,
            fmt=req.fmt,
            quality=req.quality,
        )
        return {"output_paths": paths, "count": len(paths)}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


def get_request_count() -> int:
    return _request_count


def get_api_address(host: str = "127.0.0.1", port: int = 8765) -> str:
    return f"http://{host}:{port}"


def has_api() -> bool:
    return HAS_FASTAPI


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    global _server_instance
    if not HAS_FASTAPI:
        raise RuntimeError("FastAPI is not installed. Run: pip install fastapi uvicorn")
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    _server_instance = uvicorn.Server(config)
    _server_instance.run()


def stop_server() -> None:
    global _server_instance
    if _server_instance is not None:
        _server_instance.should_exit = True
        _server_instance = None


if __name__ == "__main__":
    run_server()
