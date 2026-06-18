#!/usr/bin/env bash
# Code signing helper for NegativeCutter.app
# Provides ad-hoc signing, verification, and distribution guidance.

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_BUNDLE="${APP_DIR}/NegativeCutter.app"

usage() {
    echo "Usage: $(basename "$0") [sign|verify|status]"
    echo ""
    echo "Commands:"
    echo "  sign    Ad-hoc sign the app bundle (default if no command given)"
    echo "  verify  Verify the signature and notarization status"
    echo "  status  Show detailed code signing information"
    echo ""
    echo "Notes:"
    echo "  - Ad-hoc signed apps (codesign -s -) require right-click > Open on first launch"
    echo "  - For distribution, enroll in Apple Developer Program and use:"
    echo "      codesign --sign 'Developer ID Application: Your Name' --deep --force NegativeCutter.app"
    echo "  - Then notarize: xcrun notarytool submit NegativeCutter.zip --apple-id ..."
    exit 1
}

CMD="${1:-sign}"

if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "ERROR: $APP_BUNDLE not found. Run scripts/build_app.sh first."
    exit 1
fi

case "$CMD" in
    sign)
        echo "Ad-hoc signing $APP_BUNDLE ..."
        codesign --force --deep --sign - "$APP_BUNDLE"
        echo "Done."
        echo ""
        echo "First-launch instructions for users:"
        echo "  1. Right-click NegativeCutter.app"
        echo "  2. Select 'Open'"
        echo "  3. Click 'Open' in the security dialog"
        echo ""
        echo "To remove the security warning permanently:"
        echo "  System Settings → Privacy & Security → Security → 'Open Anyway'"
        ;;
    verify)
        echo "Verifying signature..."
        if codesign --verify --verbose "$APP_BUNDLE" 2>&1; then
            echo "Signature valid."
        else
            echo "Signature verification failed or app is unsigned."
        fi
        echo ""
        echo "Checking Gatekeeper assessment..."
        if spctl --assess --type exec "$APP_BUNDLE" 2>&1; then
            echo "Gatekeeper: app passes assessment"
        else
            echo "Gatekeeper: app will be blocked on first launch (expected for ad-hoc signing)"
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
