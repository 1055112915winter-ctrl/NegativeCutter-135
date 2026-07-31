#!/usr/bin/env bash
# Code signing helper for NegativeCutter.app.
# Release signing is Developer ID + Hardened Runtime; there is no implicit
# ad-hoc fallback because that produces the Gatekeeper failure this workflow
# is meant to prevent.

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_BUNDLE="${APP_DIR}/NegativeCutter.app"

usage() {
    echo "Usage: $(basename "$0") [sign|verify|status]"
    echo ""
    echo "Commands:"
    echo "  sign    Developer ID sign the app bundle (default if no command given)"
    echo "  verify  Verify the signature and notarization status"
    echo "  status  Show detailed code signing information"
    echo ""
    echo "Environment: NEGATIVECUTTER_DEVELOPER_ID_APPLICATION and optional NEGATIVECUTTER_TEAM_ID"
    exit 1
}

CMD="${1:-sign}"

if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "ERROR: $APP_BUNDLE not found. Run scripts/build_app.sh first."
    exit 1
fi

case "$CMD" in
    sign)
        IDENTITY="${NEGATIVECUTTER_DEVELOPER_ID_APPLICATION:-${CODESIGN_IDENTITY:-}}"
        if [[ -z "$IDENTITY" || "$IDENTITY" == "-" ]]; then
            echo "ERROR: Developer ID Application identity is required; refusing ad-hoc signing" >&2
            exit 2
        fi
        echo "Signing nested code with Developer ID Application ..."
        "${APP_DIR}/../scripts/sign_macos_tree.sh" --root "$APP_BUNDLE" --identity "$IDENTITY"
        codesign --force --options runtime --timestamp --sign "$IDENTITY" "$APP_BUNDLE"
        echo "Done."
        ;;
    verify)
        echo "Verifying signature..."
        if codesign --verify --deep --strict "$APP_BUNDLE" 2>&1; then
            echo "Signature valid."
        else
            echo "Signature verification failed or app is unsigned."
        fi
        echo ""
        echo "Checking Gatekeeper assessment..."
        if spctl --assess --type exec "$APP_BUNDLE" 2>&1; then
            echo "Gatekeeper: app passes assessment"
        else
            echo "Gatekeeper: assessment failed; preserve diagnostics and do not remove quarantine"
        fi
        ;;
    status)
        echo "=== Code Signing Details ==="
        codesign -dv "$APP_BUNDLE" 2>&1
        echo ""
        echo "=== Entitlements ==="
        codesign -d --entitlements - "$APP_BUNDLE" 2>&1 || true
        echo ""
        echo "=== Designated Requirement ==="
        codesign -d -r- "$APP_BUNDLE" 2>&1 || true
        ;;
    -h|--help)
        usage
        ;;
    *)
        echo "Unknown command: $CMD"
        usage
        ;;
esac
