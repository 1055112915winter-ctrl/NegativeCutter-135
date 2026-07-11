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
FIXTURE_135="${NEGATIVECUTTER_RELEASE_135_FIXTURE:-$SCRIPT_DIR/../test_files/52191.tif}"
FIXTURE_120="${NEGATIVECUTTER_RELEASE_120_FIXTURE:-$SCRIPT_DIR/../test_files/Untitled (3).tif}"
cleanup_failure() { rm -rf "$STAGE"; rm -f "$OUTPUT_ZIP"; }
trap cleanup_failure ERR
trap 'cleanup_failure; exit 1' INT TERM
trap 'rm -rf "$STAGE"' EXIT

[[ -f "$FIXTURE_135" && ! -L "$FIXTURE_135" ]] || { echo "ERROR: missing 135 release fixture: $FIXTURE_135" >&2; exit 1; }
[[ -f "$FIXTURE_120" && ! -L "$FIXTURE_120" ]] || { echo "ERROR: missing 120 release fixture: $FIXTURE_120" >&2; exit 1; }
# Prior interrupted builds leave only reproducible output; discard it before
# classifying the source tree so it can never mask an unknown source entry.
rm -rf build dist NegativeCutter
# Classify every source-tree component before touching build output.  Release
# inclusion is intentionally narrower than this source inventory.
SOURCE_ALLOWLIST=(.gitignore ApplierAgent.lua BatchProcess.lua CropCleaner.lua DetectFrames.lua Feedback.lua INSTALL.md ImportAgent.lua Info.lua Init.lua LICENSE NegativeCutter NegativeCutter.spec PluginInfoProvider.lua ProcessAgent.lua README.md Shutdown.lua Sponsor.lua THIRD-PARTY-LICENSES.md ThumbnailAgent.lua build.sh detect_thumb.py filmcrop install.sh json.lua tests)
for source_item in "$SCRIPT_DIR"/* "$SCRIPT_DIR"/.[!.]*; do
  source_name="$(basename "$source_item")"
  [[ "$source_name" == . || "$source_name" == .. ]] && continue
  case " ${SOURCE_ALLOWLIST[*]} " in *" $source_name "*) ;; *) echo "ERROR: unclassified source entry: $source_name" >&2; exit 1;; esac
  [[ "$source_name" != marketing && "$source_name" != .claude ]] || { echo "ERROR: forbidden source component: $source_name" >&2; exit 1; }
done
# Never retain a previous release.
rm -f "$OUTPUT_ZIP"
python3 -m PyInstaller NegativeCutter.spec
codesign --force --deep --sign - dist/NegativeCutter
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
# These paths are never release components, even if a future allowlist edit is
# attempted without a corresponding review.
find "$STAGE/$PLUGIN_DIR" \( -path '*/marketing/*' -o -path '*/.claude/*' -o -name marketing -o -name .claude \) -print -quit | grep -q . && { echo "ERROR: forbidden marketing/.claude release component" >&2; exit 1; }
cp install.sh "$STAGE/install.sh"
chmod 755 "$STAGE/install.sh"

python3 - "$STAGE/$PLUGIN_DIR" <<'PY'
import re, sys
from pathlib import Path
root = Path(sys.argv[1])
info = (root / 'Info.lua').read_text(encoding='utf-8')
missing = [name for name in re.findall(r'''file\s*=\s*["']([^"']+)["']''', info)
           if not (root / name).is_file()]
if missing:
    raise SystemExit('ERROR: Info.lua references missing files: ' + ', '.join(missing))
PY

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

smoke() {
  local plugin="$1" fixture="$2" frames="$3" format="$4" output
  output="$("$plugin/NegativeCutter/NegativeCutter" "$fixture" --frames "$frames" --format "$format" --original "$fixture")"
  python3 - "$output" "$frames" <<'PY'
import json, sys
result = json.loads(sys.argv[1])
if result.get('error') or result.get('needsReview') is not False or type(result.get('frameCount')) is not int or result['frameCount'] != int(sys.argv[2]):
    raise SystemExit('ERROR: release smoke JSON contract failed')
PY
}
# Both staged and extracted release bundles must run their generation-specific
# inputs before a ZIP can survive this script: --frames 6 --format 35mm --original;
# --frames 4 --format 645 --original.
smoke "$STAGE/$PLUGIN_DIR" "$FIXTURE_135" 6 35mm
smoke "$STAGE/$PLUGIN_DIR" "$FIXTURE_120" 4 645
( cd "$STAGE" && zip -qr "$OUTPUT_ZIP" install.sh "$PLUGIN_DIR" )
mkdir -p "$EXTRACTED"
unzip -q "$OUTPUT_ZIP" -d "$EXTRACTED"
verify_manifest "$EXTRACTED/$PLUGIN_DIR"
codesign --verify --deep --strict "$EXTRACTED/$PLUGIN_DIR/NegativeCutter"
python3 - "$OUTPUT_ZIP" "$STAGE" <<'PY'
import sys, zipfile
from pathlib import Path
archive, stage = map(Path, sys.argv[1:])
expected = {'install.sh'} | {f'NegativeCutter-135.lrplugin/{p.relative_to(stage / "NegativeCutter-135.lrplugin").as_posix()}' for p in (stage / 'NegativeCutter-135.lrplugin').rglob('*') if p.is_file()}
actual = {n for n in zipfile.ZipFile(archive).namelist() if not n.endswith('/')}
if actual != expected: raise SystemExit('ERROR: ZIP does not contain the exact release file set')
if any(not (n == 'install.sh' or n.startswith('NegativeCutter-135.lrplugin/')) for n in actual): raise SystemExit('ERROR: unexpected ZIP top-level entry')
PY
smoke "$EXTRACTED/$PLUGIN_DIR" "$FIXTURE_135" 6 35mm
smoke "$EXTRACTED/$PLUGIN_DIR" "$FIXTURE_120" 4 645
echo "Built $OUTPUT_ZIP"
