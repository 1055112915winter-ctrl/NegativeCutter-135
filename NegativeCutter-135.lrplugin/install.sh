#!/usr/bin/env bash
# Integrity checks catch accidental corruption; neither checksums nor signatures prove publisher identity.
set -euo pipefail
umask 077

SOURCE="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/NegativeCutter-135.lrplugin}"
MODULES_DIR="${NEGATIVECUTTER_MODULES_DIR:-$HOME/Library/Application Support/Adobe/Lightroom/Modules}"
[[ -d "$SOURCE" && ! -L "$SOURCE" ]] || { echo "ERROR: source must be a real directory" >&2; exit 1; }
[[ -d "$MODULES_DIR" && ! -L "$MODULES_DIR" ]] || { echo "ERROR: Modules directory must be a real directory" >&2; exit 1; }
NAME="$(basename "$SOURCE")"
TARGET="$MODULES_DIR/$NAME"
STAGED="$MODULES_DIR/.${NAME}.staged"
BACKUP="$MODULES_DIR/.${NAME}.backup"
[[ ! -e "$STAGED" && ! -e "$BACKUP" ]] || { echo "ERROR: staging or backup already exists" >&2; exit 1; }
[[ ! -e "$TARGET" || ( -d "$TARGET" && ! -L "$TARGET" ) ]] || { echo "ERROR: target must be a real directory" >&2; exit 1; }

verify_manifest() {
  python3 - "$1" <<'PY'
import hashlib, re, sys
from pathlib import Path
root = Path(sys.argv[1]); manifest = root / 'RELEASE-MANIFEST.sha256'
if not manifest.is_file() or manifest.is_symlink(): raise SystemExit('ERROR: missing manifest')
seen=set(); expected=set()
for line in manifest.read_text(encoding='utf-8').splitlines():
    m=re.fullmatch(r'([0-9a-f]{64})  ([^/][^\n]*)', line)
    if not m: raise SystemExit('ERROR: malformed manifest')
    digest, rel=m.groups()
    if rel.startswith('/') or '..' in Path(rel).parts or rel in seen: raise SystemExit('ERROR: unsafe manifest path')
    seen.add(rel); expected.add(rel); path=root/rel
    if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise SystemExit('ERROR: manifest checksum mismatch')
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name != manifest.name}
if actual != expected: raise SystemExit('ERROR: manifest exact release file set mismatch')
PY
}

rollback() {
  if [[ -e "$BACKUP" && ! -e "$TARGET" ]]; then mv "$BACKUP" "$TARGET"; fi
  rm -rf "$STAGED"
}
trap 'rollback; echo "Install failed; staged=$STAGED target=$TARGET" >&2' ERR INT TERM
verify_manifest "$SOURCE"
[[ "${NEGATIVECUTTER_TEST_SKIP_CODESIGN:-0}" == 1 ]] || codesign --verify --deep --strict "$SOURCE/NegativeCutter"
cp -RL "$SOURCE" "$STAGED"
find "$STAGED" -type l -print -quit | grep -q . && { echo "ERROR: symlink in staged plugin" >&2; exit 1; }
verify_manifest "$STAGED"
[[ "${NEGATIVECUTTER_TEST_SKIP_CODESIGN:-0}" == 1 ]] || codesign --verify --deep --strict "$STAGED/NegativeCutter"
if [[ -e "$TARGET" ]]; then mv "$TARGET" "$BACKUP"; fi
if [[ "${NEGATIVECUTTER_TEST_FAIL_SECOND_RENAME:-0}" == 1 ]]; then false; fi
mv "$STAGED" "$TARGET"
rm -rf "$BACKUP"
trap - ERR INT TERM
echo "Installed $NAME into $MODULES_DIR"
echo "Installed plugin path: $TARGET"
echo "Restart Lightroom to load the updated plugin."
