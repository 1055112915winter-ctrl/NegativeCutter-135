#!/usr/bin/env bash
# Build script for NegativeCutter macOS .app bundle.
# Supports optional universal2 target architecture via --target-arch.

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SPEC="${APP_DIR}/NegativeCutter.spec"
ICON="${APP_DIR}/NegativeCutter.icns"
TARGET_ARCH=""

VERSION=$(python3 - "${APP_DIR}" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from filmcrop import __version__
print(__version__)
PY
)

usage() {
    cat <<EOF
Usage: $(basename "$0") [--target-arch universal2|x86_64|arm64]

Build NegativeCutter macOS .app bundle.

Options:
  --target-arch  Target architecture (universal2, x86_64, arm64)
  --version      Print version and exit
  -h, --help     Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target-arch)
            TARGET_ARCH="${2:-}"
            shift 2
            ;;
        --version)
            echo "NegativeCutter v${VERSION}"
            exit 0
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

echo "==> Building NegativeCutter v${VERSION}"

# Validate target-arch if requested for universal2
if [[ "$TARGET_ARCH" == "universal2" ]]; then
    echo "Checking universal2 dependency compatibility..."
    python3 -c "
import sys
missing = []
for pkg in ('PyQt6.QtCore', 'numpy', 'PIL._imaging'):
    try:
        mod = __import__(pkg, fromlist=['__file__'])
        import subprocess, os
        result = subprocess.run(['file', mod.__file__], capture_output=True, text=True)
        if 'universal' not in result.stdout:
            missing.append(pkg)
    except Exception as e:
        missing.append(f'{pkg} ({e})')
if missing:
    print('WARNING: The following dependencies are not universal2 binaries:')
    for m in missing:
        print(f'  - {m}')
    print('Build will likely fail or produce a non-universal binary.')
    print('Install universal2 wheels, e.g.:')
    print('  pip install --only-binary :all: --force-reinstall PyQt6 numpy Pillow')
    sys.exit(1)
else:
    print('All checked dependencies are universal2 compatible.')
"
fi

# Export target arch for the spec file
if [[ -n "$TARGET_ARCH" ]]; then
    export PYI_TARGET_ARCH="$TARGET_ARCH"
    echo "Building for architecture: $TARGET_ARCH"
else
    echo "Building for default architecture ($(python3 -c 'import platform; print(platform.machine())'))"
fi

# Generate the canonical icon beside the spec. The spec intentionally has no
# cross-worktree fallback, so stale assets cannot enter the bundle.
echo "Generating application icon..."
python3 "${APP_DIR}/generate_icns.py"
if [[ ! -f "$ICON" ]]; then
    echo "ERROR: Icon generation failed — $ICON not found" >&2
    exit 1
fi

# Run PyInstaller with isolated temp directories to avoid worktree sandbox issues
TMP_BASE="${TMPDIR:-/tmp}/negativecutter_build_$(date +%s)"
mkdir -p "$TMP_BASE"

echo "PyInstaller work path: $TMP_BASE"

PYINSTALLER_CONFIG_DIR="$TMP_BASE/pyi_cfg" \
    python3 -m PyInstaller "$SPEC" \
    --clean \
    --workpath "$TMP_BASE/pyi_build" \
    --distpath "$TMP_BASE/pyi_dist"

APP_BUNDLE="$TMP_BASE/pyi_dist/NegativeCutter.app"
if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "ERROR: Build failed — $APP_BUNDLE not found" >&2
    rm -rf "$TMP_BASE"
    exit 1
fi

# Ad-hoc sign the bundle
echo "Signing app bundle..."
codesign --force --deep --sign - "$APP_BUNDLE" 2>/dev/null || true

# Verify signature
echo "Verifying signature..."
codesign -dv "$APP_BUNDLE" 2>&1 | head -5

# Copy to project directory
DEST="${APP_DIR}/NegativeCutter.app"
if [[ -d "$DEST" ]]; then
    rm -rf "$DEST"
fi
cp -R "$APP_BUNDLE" "$DEST"
rm -rf "$TMP_BASE"

echo ""
echo "Build complete: NegativeCutter v${VERSION} → $DEST"
echo ""
echo "To distribute:"
echo "  zip -r -y NegativeCutter-v${VERSION}-macOS-${TARGET_ARCH:-arm64}.zip NegativeCutter.app"
echo ""
echo "  First-launch note: right-click → Open (Gatekeeper)"
