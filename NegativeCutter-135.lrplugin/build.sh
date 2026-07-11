#!/usr/bin/env bash
# Build a self-contained Lightroom release.  The checksum and code signature
# checks below detect accidental damage; they do not establish publisher identity.
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
PLUGIN_DIR="NegativeCutter-135.lrplugin"
PLUGIN_NAME="NegativeCutter-135"
VERSION="$(python3 -c "import sys; sys.path.insert(0, '.'); from filmcrop import __version__; print(__version__)")"
OUTPUT_ZIP="$(dirname "$SCRIPT_DIR")/${PLUGIN_NAME}-v${VERSION}.zip"
STAGE="${TMPDIR:-/tmp}/filmcrop-release-$$"
EXTRACTED="$STAGE/extracted"
trap 'rm -rf "$STAGE"; rm -f "$OUTPUT_ZIP"' ERR INT TERM
trap 'rm -rf "$STAGE"' EXIT

rm -rf build dist
python3 -m PyInstaller NegativeCutter.spec
if [[ -d dist/NegativeCutter && -x dist/NegativeCutter/NegativeCutter ]]; then
  rm -rf NegativeCutter
  cp -RL dist/NegativeCutter NegativeCutter
elif [[ ! -x dist/NegativeCutter ]]; then
  echo "ERROR: executable missing from dist/NegativeCutter" >&2
  exit 1
fi

mkdir -p "$STAGE/$PLUGIN_DIR"
# Explicit allowlist: the release must not inherit arbitrary dirty-tree files.
ALLOWLIST=(
  ApplierAgent.lua BatchProcess.lua CropCleaner.lua DetectFrames.lua Feedback.lua
  ImportAgent.lua Info.lua Init.lua PluginInfoProvider.lua ProcessAgent.lua
  Shutdown.lua Sponsor.lua ThumbnailAgent.lua json.lua LICENSE README.md INSTALL.md
  THIRD-PARTY-LICENSES.md detect_thumb.py filmcrop NegativeCutter
)
for item in "${ALLOWLIST[@]}"; do
  [[ -e "$item" && ! -L "$item" ]] || { echo "ERROR: missing or symlinked allowlist entry: $item" >&2; exit 1; }
  cp -RL "$item" "$STAGE/$PLUGIN_DIR/$item"
done
cp install.sh "$STAGE/install.sh"
chmod 755 "$STAGE/install.sh"

python3 - "$STAGE/$PLUGIN_DIR" <<'PY'
import hashlib, sys
from pathlib import Path
root = Path(sys.argv[1])
files = sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'RELEASE-MANIFEST.sha256')
if any(p.is_symlink() for p in files): raise SystemExit('ERROR: symlink in release stage')
(root / 'RELEASE-MANIFEST.sha256').write_text(''.join(
    f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n' for p in files), encoding='utf-8')
PY

verify_manifest() {
  python3 - "$1" <<'PY'
import hashlib, re, sys
from pathlib import Path
root = Path(sys.argv[1]); manifest = root / 'RELEASE-MANIFEST.sha256'
lines = manifest.read_text(encoding='utf-8').splitlines()
seen = set(); expected = set()
for line in lines:
    m = re.fullmatch(r'([0-9a-f]{64})  ([^/][^\n]*)', line)
    if not m: raise SystemExit('ERROR: malformed manifest')
    digest, rel = m.groups()
    if rel.startswith('/') or '..' in Path(rel).parts or rel in seen: raise SystemExit('ERROR: unsafe manifest path')
    seen.add(rel); expected.add(rel)
    path = root / rel
    if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise SystemExit('ERROR: manifest checksum mismatch')
actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name != manifest.name}
if actual != expected: raise SystemExit('ERROR: manifest exact release file set mismatch')
PY
}
verify_manifest "$STAGE/$PLUGIN_DIR"
codesign --verify --deep --strict "$STAGE/$PLUGIN_DIR/NegativeCutter"

( cd "$STAGE" && zip -qr "$OUTPUT_ZIP" install.sh "$PLUGIN_DIR" )
mkdir -p "$EXTRACTED"
unzip -q "$OUTPUT_ZIP" -d "$EXTRACTED"
verify_manifest "$EXTRACTED/$PLUGIN_DIR"
python3 - "$OUTPUT_ZIP" "$STAGE" <<'PY'
import sys, zipfile
from pathlib import Path
archive, stage = map(Path, sys.argv[1:])
expected = {'install.sh'} | {f'NegativeCutter-135.lrplugin/{p.relative_to(stage / "NegativeCutter-135.lrplugin").as_posix()}' for p in (stage / 'NegativeCutter-135.lrplugin').rglob('*') if p.is_file()}
actual = {n for n in zipfile.ZipFile(archive).namelist() if not n.endswith('/')}
if actual != expected: raise SystemExit('ERROR: ZIP does not contain the exact release file set')
if any(not (n == 'install.sh' or n.startswith('NegativeCutter-135.lrplugin/')) for n in actual): raise SystemExit('ERROR: unexpected ZIP top-level entry')
PY

smoke() { "$1/NegativeCutter/NegativeCutter" --help >/dev/null; }
smoke "$EXTRACTED/$PLUGIN_DIR"
for spec in "135:${NEGATIVECUTTER_RELEASE_135_FIXTURE:-}" "120:${NEGATIVECUTTER_RELEASE_120_FIXTURE:-}"; do
  generation="${spec%%:*}"; fixture="${spec#*:}"
  [[ -z "$fixture" ]] && continue
  [[ -f "$fixture" && ! -L "$fixture" ]] || { echo "ERROR: release fixture must be a regular ZIP file" >&2; exit 1; }
  fixture_extract="$STAGE/fixture-$generation"
  mkdir "$fixture_extract"
  unzip -q "$fixture" -d "$fixture_extract"
  smoke "$fixture_extract/NegativeCutter-$generation.lrplugin"
done
echo "Built $OUTPUT_ZIP"
