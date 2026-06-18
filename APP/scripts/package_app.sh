#!/usr/bin/env bash
# Verify, rebuild, and sign-check NegativeCutter.app.

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "${APP_DIR}/.." && pwd)"
BUILD_SCRIPT="${APP_DIR}/scripts/build_app.sh"
APP_BUNDLE="${APP_DIR}/NegativeCutter.app"
BUILD_ARGS=()

usage() {
    cat <<EOF
Usage: $(basename "$0") [--target-arch universal2|x86_64|arm64]

Runs the GUI tests, rebuilds APP/NegativeCutter.app, and verifies its signature.

Options:
  --target-arch  Forward the target architecture to build_app.sh
  -h, --help     Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target-arch)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --target-arch requires a value" >&2
                exit 2
            fi
            BUILD_ARGS+=("--target-arch" "$2")
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

echo "==> Running GUI tests"
cd "$REPO_ROOT"
QT_QPA_PLATFORM=offscreen python3 -m unittest discover \
    -s "$REPO_ROOT/tests" \
    -p 'test_gui_*.py' \
    -v

echo "==> Building NegativeCutter.app"
if [[ ${#BUILD_ARGS[@]} -gt 0 ]]; then
    "$BUILD_SCRIPT" "${BUILD_ARGS[@]}"
else
    "$BUILD_SCRIPT"
fi

if [[ ! -x "$APP_BUNDLE/Contents/MacOS/NegativeCutter" ]]; then
    echo "ERROR: Built application executable is missing" >&2
    exit 1
fi

echo "==> Verifying application signature"
codesign --verify --deep --strict "$APP_BUNDLE"

echo "==> Package ready: $APP_BUNDLE"
