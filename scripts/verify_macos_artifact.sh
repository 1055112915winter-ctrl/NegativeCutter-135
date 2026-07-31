#!/usr/bin/env bash
# Validate architecture, deployment target, and distribution signature for a
# staged macOS runtime. This is intentionally independent from PyInstaller.
set -euo pipefail

ROOT=""
TARGET_ARCH="$(uname -m)"
MIN_MACOS="14.0"
REQUIRE_DISTRIBUTION=1
TEAM_ID="${NEGATIVECUTTER_TEAM_ID:-}"

usage() {
  cat <<'EOF'
Usage: verify_macos_artifact.sh --root PATH [--arch arm64|x86_64|universal2]
       [--min-macos VERSION] [--team-id TEAM_ID] [--allow-adhoc]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --arch) TARGET_ARCH="${2:-}"; shift 2 ;;
    --min-macos) MIN_MACOS="${2:-}"; shift 2 ;;
    --team-id) TEAM_ID="${2:-}"; shift 2 ;;
    --allow-adhoc) REQUIRE_DISTRIBUTION=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -d "$ROOT" ]] || { echo "ERROR: artifact root is missing: $ROOT" >&2; exit 2; }
case "$TARGET_ARCH" in arm64|x86_64|universal2) ;; *) echo "ERROR: unsupported target arch: $TARGET_ARCH" >&2; exit 2;; esac

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/filmcrop-artifact-gate.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT
machos=0

version_at_least() {
  python3 - "$1" "$2" <<'PY'
import sys
def parts(value):
    return tuple(int(part) for part in value.split('.')[:3])
raise SystemExit(0 if parts(sys.argv[1]) >= parts(sys.argv[2]) else 1)
PY
}

while IFS= read -r -d '' candidate; do
  [[ -L "$candidate" ]] && continue
  description="$(file -b "$candidate")"
  [[ "$description" == *"Mach-O"* ]] || continue
  machos=$((machos + 1))
  archs="$(lipo -archs "$candidate" 2>/dev/null)" || {
    echo "ERROR: cannot inspect architecture: $candidate" >&2; exit 1;
  }
  case "$TARGET_ARCH" in
    arm64|x86_64) [[ "$archs" == "$TARGET_ARCH" ]] || { echo "ERROR: $candidate has archs '$archs', expected $TARGET_ARCH" >&2; exit 1; } ;;
    universal2) [[ "$archs" == *arm64* && "$archs" == *x86_64* ]] || { echo "ERROR: $candidate is not universal2: $archs" >&2; exit 1; } ;;
  esac
  build_info="$(vtool -show-build "$candidate" 2>&1 || true)"
  minos="$(printf '%s\n' "$build_info" | sed -nE 's/.*minos ([0-9]+(\.[0-9]+){0,2}).*/\1/p' | head -1)"
  [[ -n "$minos" ]] || { echo "ERROR: missing deployment target for $candidate" >&2; exit 1; }
  # A component may target an older macOS, but never a newer one than the
  # declared product minimum. The inverse comparison would reject harmless
  # system-compatible libraries.
  version_at_least "$MIN_MACOS" "$minos" || { echo "ERROR: $candidate targets macOS $minos, which exceeds declared minimum $MIN_MACOS" >&2; exit 1; }
  if (( REQUIRE_DISTRIBUTION )); then
    details="$tmp_dir/details"
    codesign -dvvv "$candidate" >"$details" 2>&1 || { echo "ERROR: signature inspection failed: $candidate" >&2; exit 1; }
    grep -q '^Authority=Developer ID Application:' "$details" || { echo "ERROR: non-Developer-ID signature: $candidate" >&2; exit 1; }
    ! grep -q '^Signature=adhoc' "$details" || { echo "ERROR: ad-hoc signature: $candidate" >&2; exit 1; }
    if [[ -n "$TEAM_ID" ]]; then grep -q "^TeamIdentifier=$TEAM_ID$" "$details" || { echo "ERROR: wrong Team ID: $candidate" >&2; exit 1; }; fi
    codesign --verify --strict "$candidate"
  fi
done < <(find "$ROOT" -type f -print0)

(( machos > 0 )) || { echo "ERROR: artifact contains no Mach-O files: $ROOT" >&2; exit 1; }
if (( REQUIRE_DISTRIBUTION )); then
  codesign --verify --deep --strict "$ROOT"
fi
echo "macOS artifact gate: PASS ($machos Mach-O files, arch=$TARGET_ARCH, min-macos=$MIN_MACOS)"
