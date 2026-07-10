"""Compatibility alias for the canonical NegativeCutter detector core."""

from pathlib import Path
import sys


_SRC = Path(__file__).resolve().parents[2] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from negativecutter_core import detector as _canonical_detector

# A true module alias keeps private helpers and unittest.patch semantics intact.
sys.modules[__name__] = _canonical_detector
