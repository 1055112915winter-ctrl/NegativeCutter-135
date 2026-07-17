"""Film-format registry.

Format family is explicit because aspect ratio alone cannot distinguish 35mm
from 6x9; both are 3:2 but require different detection pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FilmFormat:
    code: str
    family: str
    aspect_ratio: float
    label: str


FILM_FORMATS = {
    "35mm": FilmFormat("35mm", "135", 3 / 2, "35mm / 135"),
    "645": FilmFormat("645", "120", 4 / 3, "120 6x4.5"),
    "6x6": FilmFormat("6x6", "120", 1.0, "120 6x6"),
    "6x7": FilmFormat("6x7", "120", 7 / 6, "120 6x7"),
    "6x8": FilmFormat("6x8", "120", 8 / 6, "120 6x8"),
    "6x9": FilmFormat("6x9", "120", 3 / 2, "120 6x9"),
    "4x5": FilmFormat("4x5", "sheet", 5 / 4, "4x5 sheet film"),
}

MEDIUM_FORMAT_CODES = frozenset(
    code for code, spec in FILM_FORMATS.items() if spec.family == "120"
)
MEDIUM_FORMAT_ASPECT_RATIOS = tuple(
    dict.fromkeys(
        spec.aspect_ratio for spec in FILM_FORMATS.values() if spec.family == "120"
    )
)
KNOWN_ASPECT_RATIOS = tuple(
    dict.fromkeys(spec.aspect_ratio for spec in FILM_FORMATS.values())
)


def normalize_format_code(code: str | None) -> str | None:
    if code is None:
        return None
    normalized = str(code).strip().lower()
    return normalized or None


def format_spec(code: str | None) -> FilmFormat | None:
    normalized = normalize_format_code(code)
    return FILM_FORMATS.get(normalized) if normalized else None


def format_family(code: str | None) -> str | None:
    spec = format_spec(code)
    return spec.family if spec else None


def format_aspect_ratio(code: str | None) -> float | None:
    spec = format_spec(code)
    return spec.aspect_ratio if spec else None
