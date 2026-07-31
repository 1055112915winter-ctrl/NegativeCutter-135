#!/usr/bin/env bash
# Build, sign, notarize, staple, and verify the macOS installer package.
# Credentials are read from the keychain/notarytool profile, never files in
# this repository. The script intentionally fails closed when prerequisites
# are absent.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_PLUGIN=""
OUTPUT=""
VERSION=""
APPLICATION_IDENTITY="${NEGATIVECUTTER_DEVELOPER_ID_APPLICATION:-}"
INSTALLER_IDENTITY="${NEGATIVECUTTER_DEVELOPER_ID_INSTALLER:-}"
NOTARY_PROFILE="${NEGATIVECUTTER_NOTARY_PROFILE:-}"
PACKAGE_ID="io.negativecutter.plugin"

usage() {
  cat <<'EOF'
Usage: build_macos_pkg.sh --source-plugin PATH --output PATH --version VERSION
Environment: NEGATIVECUTTER_DEVELOPER_ID_APPLICATION,
NEGATIVECUTTER_DEVELOPER_ID_INSTALLER, NEGATIVECUTTER_NOTARY_PROFILE
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-plugin) SOURCE_PLUGIN="${2:-}"; shift 2 ;;
    --output) OUTPUT="${2:-}"; shift 2 ;;
    --version) VERSION="${2:-}"; shift 2 ;;
    --application-identity) APPLICATION_IDENTITY="${2:-}"; shift 2 ;;
    --installer-identity) INSTALLER_IDENTITY="${2:-}"; shift 2 ;;
    --notary-profile) NOTARY_PROFILE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -d "$SOURCE_PLUGIN" && ! -L "$SOURCE_PLUGIN" ]] || { echo "ERROR: source plugin is missing" >&2; exit 2; }
[[ -n "$OUTPUT" && -n "$VERSION" ]] || { echo "ERROR: output and version are required" >&2; exit 2; }
[[ -n "$APPLICATION_IDENTITY" && -n "$INSTALLER_IDENTITY" ]] || { echo "ERROR: Developer ID Application and Installer identities are required" >&2; exit 2; }
[[ -n "$NOTARY_PROFILE" ]] || { echo "ERROR: NEGATIVECUTTER_NOTARY_PROFILE is required" >&2; exit 2; }
command -v pkgbuild >/dev/null || { echo "ERROR: pkgbuild is unavailable" >&2; exit 2; }
command -v xcrun >/dev/null || { echo "ERROR: xcrun is unavailable" >&2; exit 2; }
TEAM_ARGS=()
if [[ -n "${NEGATIVECUTTER_TEAM_ID:-}" ]]; then TEAM_ARGS=(--team-id "$NEGATIVECUTTER_TEAM_ID"); fi

stage="$(mktemp -d "${TMPDIR:-/tmp}/filmcrop-pkg.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
payload="$stage/payload/Library/Application Support/NegativeCutter"
mkdir -p "$payload"
ditto "$SOURCE_PLUGIN" "$payload/NegativeCutter-135.lrplugin"
ENGINE_ROOT="$payload/NegativeCutter-135.lrplugin/NegativeCutter"
"$ROOT/scripts/sign_macos_tree.sh" --root "$ENGINE_ROOT" --identity "$APPLICATION_IDENTITY"
codesign --force --options runtime --timestamp --sign "$APPLICATION_IDENTITY" "$ENGINE_ROOT"
"$ROOT/scripts/verify_macos_artifact.sh" --root "$ENGINE_ROOT" \
  --arch "${NEGATIVECUTTER_TARGET_ARCH:-$(uname -m)}" \
  --min-macos "${NEGATIVECUTTER_MIN_MACOS_VERSION:-14.0}" \
  "${TEAM_ARGS[@]}"

pkgbuild --root "$stage/payload" --identifier "$PACKAGE_ID" --version "$VERSION" \
  --install-location / --scripts "$ROOT/packaging/pkg-scripts" \
  --sign "$INSTALLER_IDENTITY" "$OUTPUT"

xcrun notarytool submit "$OUTPUT" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$OUTPUT"
xcrun stapler validate "$OUTPUT"
pkgutil --check-signature "$OUTPUT"
spctl -a -vv --type install "$OUTPUT"
echo "Built notarized installer: $OUTPUT"
