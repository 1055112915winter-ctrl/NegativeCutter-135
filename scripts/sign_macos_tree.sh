#!/usr/bin/env bash
# Sign every Mach-O inside a PyInstaller tree before signing its outer bundle.
# This deliberately requires a real Developer ID identity; ad-hoc signing is
# useful for local diagnostics only and is never an implicit fallback.
set -euo pipefail

ROOT=""
IDENTITY="${NEGATIVECUTTER_DEVELOPER_ID_APPLICATION:-${CODESIGN_IDENTITY:-}}"

usage() {
  cat <<'EOF'
Usage: sign_macos_tree.sh --root PATH --identity 'Developer ID Application: ...'
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --identity) IDENTITY="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$ROOT" && -d "$ROOT" ]] || { echo "ERROR: --root must be a directory" >&2; exit 2; }
[[ -n "$IDENTITY" && "$IDENTITY" != "-" ]] || {
  echo "ERROR: Developer ID Application identity is required; refusing ad-hoc signing" >&2
  exit 2
}
command -v codesign >/dev/null || { echo "ERROR: codesign is unavailable" >&2; exit 2; }

signed=0
while IFS= read -r -d '' candidate; do
  [[ -L "$candidate" ]] && continue
  if file -b "$candidate" | grep -q 'Mach-O'; then
    echo "Signing $candidate"
    codesign --force --options runtime --timestamp --sign "$IDENTITY" "$candidate"
    signed=$((signed + 1))
  fi
done < <(find "$ROOT" -type f -print0)

(( signed > 0 )) || { echo "ERROR: no Mach-O files found under $ROOT" >&2; exit 1; }
echo "Signed $signed Mach-O files with Developer ID Application"
