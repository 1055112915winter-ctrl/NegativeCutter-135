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
rm -rf __pycache__
# Classify every source-tree component before touching build output.  Release
# inclusion is intentionally narrower than this source inventory.
SOURCE_ALLOWLIST=(.gitignore ApplierAgent.lua BatchProcess.lua CropCleaner.lua DetectFrames.lua Feedback.lua INSTALL.md ImportAgent.lua Info.lua Init.lua LICENSE NegativeCutter NegativeCutter.spec PluginInfoProvider.lua PreviewAgent.lua PreviewRuntime.lua ProcessAgent.lua README.md Shutdown.lua Sponsor.lua THIRD-PARTY-LICENSES.md ThumbnailAgent.lua build.sh detect_thumb.py filmcrop install.sh json.lua tests)
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
  ditto dist/NegativeCutter NegativeCutter
elif [[ ! -x dist/NegativeCutter ]]; then
  echo "ERROR: executable missing from dist/NegativeCutter" >&2
  exit 1
fi

mkdir -p "$STAGE/$PLUGIN_DIR"
# Explicit allowlist: the release must not inherit arbitrary dirty-tree files.
ALLOWLIST=(
  ApplierAgent.lua BatchProcess.lua CropCleaner.lua DetectFrames.lua Feedback.lua
  ImportAgent.lua Info.lua Init.lua PluginInfoProvider.lua PreviewAgent.lua PreviewRuntime.lua ProcessAgent.lua
  Shutdown.lua Sponsor.lua ThumbnailAgent.lua json.lua LICENSE README.md INSTALL.md
  THIRD-PARTY-LICENSES.md detect_thumb.py filmcrop NegativeCutter
)
for item in "${ALLOWLIST[@]}"; do
  [[ -e "$item" && ! -L "$item" ]] || { echo "ERROR: missing or symlinked allowlist entry: $item" >&2; exit 1; }
  if [[ "$item" == "NegativeCutter" ]]; then
    ditto "$item" "$STAGE/$PLUGIN_DIR/$item"
  else
    cp -RL "$item" "$STAGE/$PLUGIN_DIR/$item"
  fi
done
# These paths are never release components, even if a future allowlist edit is
# attempted without a corresponding review.
find "$STAGE/$PLUGIN_DIR" \( -path '*/marketing/*' -o -path '*/.claude/*' -o -name marketing -o -name .claude \) -print -quit | grep -q . && { echo "ERROR: forbidden marketing/.claude release component" >&2; exit 1; }
cp install.sh "$STAGE/install.sh"
chmod 755 "$STAGE/install.sh"
find "$STAGE/$PLUGIN_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$STAGE/$PLUGIN_DIR" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

verify_preview_runtime() {
  local root="$1"
  [[ -f "$root/PreviewAgent.lua" && -f "$root/PreviewRuntime.lua" ]] || {
    echo "ERROR: preview runtime missing from release inventory" >&2; exit 1;
  }
}
reject_preview_artifacts() {
  local root="$1" leaked
  leaked="$(find "$root" \( -path '*/tests/*' -o -name '*.frames.json' -o -name active.json \
    -o -name 'preview-*.jpg' -o -name '*.partial' -o -name '.negativecutter-preview-owner' \
    -o -name NegativeCutterPreview \) -print -quit)"
  [[ -z "$leaked" ]] || { echo "ERROR: preview development/runtime artifact leaked: $leaked" >&2; exit 1; }
}
verify_preview_runtime "$STAGE/$PLUGIN_DIR"
reject_preview_artifacts "$STAGE/$PLUGIN_DIR"

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
entries=[]
for p in sorted(root.rglob('*')):
    if p.is_symlink(): entries.append(f'link  {p.relative_to(root).as_posix()} -> {p.readlink()}\n')
    elif p.is_file() and p.name != 'RELEASE-MANIFEST.sha256': entries.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n')
(root / 'RELEASE-MANIFEST.sha256').write_text(''.join(entries), encoding='utf-8')
PY

verify_manifest() {
  python3 - "$1" <<'PY'
import hashlib, re, sys
from pathlib import Path
root = Path(sys.argv[1]); manifest = root / 'RELEASE-MANIFEST.sha256'
lines = manifest.read_text(encoding='utf-8').splitlines(); seen = set(); expected = set(); root_real=root.resolve()
for line in lines:
    target=None
    if line.startswith('link  '): rel, sep, target=line[6:].partition(' -> '); digest=None; assert sep
    else:
        m = re.fullmatch(r'([0-9a-f]{64})  ([^/][^\n]*)', line)
        if not m: raise SystemExit('ERROR: malformed manifest')
        digest, rel = m.groups()
    if rel.startswith('/') or '..' in Path(rel).parts or rel in seen: raise SystemExit('ERROR: unsafe manifest path')
    seen.add(rel); expected.add(rel)
    path = root / rel
    if target is not None:
        if not path.is_symlink() or Path(target).is_absolute() or not (path.parent / target).resolve().is_relative_to(root_real): raise SystemExit('ERROR: unsafe manifest symlink')
    elif not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise SystemExit('ERROR: manifest checksum mismatch')
actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if (p.is_file() or p.is_symlink()) and p.name != manifest.name}
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
render_smoke() {
  local plugin="$1" fixture="$2" work frames input output payload
  work="$(mktemp -d "$STAGE/render-smoke.XXXXXX")"
  frames="$work/frames.json"
  input="$work/input.png"
  output="$work/preview.jpg"
  python3 - "$frames" "$input" <<'PY'
import json, sys
from pathlib import Path
from PIL import Image
Path(sys.argv[1]).write_text(json.dumps({"frames": [{
    "index": 1, "relativeTop": .1, "relativeBottom": .9,
    "relativeLeft": .2, "relativeRight": .8,
}]}, separators=(",", ":")), encoding="utf-8")
Image.new("RGB", (1000, 500), "white").save(sys.argv[2])
PY
  payload="$("$plugin/NegativeCutter/NegativeCutter" --render-preview --input "$input" \
    --frames-json "$frames" --source-width 1000 --source-height 500 \
    --top-px 10 --bottom-px 20 --left-px -30 --right-px 40 --output "$output")"
  python3 - "$payload" "$output" <<'PY'
import json, sys
from pathlib import Path
payload = json.loads(sys.argv[1]); output = Path(sys.argv[2])
expected = {"top": 40, "bottom": 470, "left": 230, "right": 840,
            "relativeTop": .08, "relativeBottom": .94,
            "relativeLeft": .23, "relativeRight": .84}
frames = payload.get("frames")
if payload.get("error") or payload.get("previewPath") != str(output) or payload.get("frameCount") != 1 or not output.is_file():
    raise SystemExit("ERROR: packaged render smoke output contract failed")
if not isinstance(frames, list) or len(frames) != 1 or any(frames[0].get(key) != value for key, value in expected.items()):
    raise SystemExit("ERROR: packaged render smoke adjusted frames mismatch")
PY
  rm -rf "$work"
}
# Both staged and extracted release bundles must run their generation-specific
# inputs before a ZIP can survive this script: --frames 6 --format 35mm --original;
# --frames 4 --format 645 --original.
smoke "$STAGE/$PLUGIN_DIR" "$FIXTURE_135" 6 35mm
smoke "$STAGE/$PLUGIN_DIR" "$FIXTURE_120" 4 645
render_smoke "$STAGE/$PLUGIN_DIR" "$FIXTURE_135"
ARCHIVE_ROOT="$STAGE/archive-root"
mkdir "$ARCHIVE_ROOT"
ditto "$STAGE/install.sh" "$ARCHIVE_ROOT/install.sh"
ditto "$STAGE/$PLUGIN_DIR" "$ARCHIVE_ROOT/$PLUGIN_DIR"
( cd "$ARCHIVE_ROOT" && ditto -c -k --sequesterRsrc . "$OUTPUT_ZIP" )
mkdir -p "$EXTRACTED"
ditto -x -k "$OUTPUT_ZIP" "$EXTRACTED"
verify_preview_runtime "$EXTRACTED/$PLUGIN_DIR"
reject_preview_artifacts "$EXTRACTED/$PLUGIN_DIR"
verify_manifest "$EXTRACTED/$PLUGIN_DIR"
codesign --verify --deep --strict "$EXTRACTED/$PLUGIN_DIR/NegativeCutter"
python3 - "$OUTPUT_ZIP" "$STAGE" <<'PY'
import sys, zipfile
from pathlib import Path
archive, stage = map(Path, sys.argv[1:])
names = {n for n in zipfile.ZipFile(archive).namelist() if not n.endswith('/')}
# __MACOSX and AppleDouble (._*) are ditto metadata, not release payload.
metadata = {n for n in names if n.startswith('__MACOSX/') or '/._' in n or n.startswith('._')}
actual = names - metadata
if any(not (n == 'install.sh' or n.startswith('NegativeCutter-135.lrplugin/')) for n in actual): raise SystemExit('ERROR: unexpected ZIP top-level entry')
if any('/marketing/' in n or '/.claude/' in n or n.startswith('marketing/') or n.startswith('.claude/') for n in actual): raise SystemExit('ERROR: forbidden ZIP payload entry')
if any('/__pycache__/' in n or n.endswith(('.pyc', '.pyo')) for n in actual): raise SystemExit('ERROR: bytecode leaked into ZIP payload')
for name in actual:
    parts = Path(name).parts
    base = parts[-1]
    if ('tests' in parts or base.endswith('.frames.json') or base == 'active.json' or
        (base.startswith('preview-') and base.endswith('.jpg')) or base.endswith('.partial') or
        base == '.negativecutter-preview-owner' or 'NegativeCutterPreview' in parts):
        raise SystemExit('ERROR: preview runtime artifact leaked into ZIP payload: ' + name)
if not {'install.sh', 'NegativeCutter-135.lrplugin/RELEASE-MANIFEST.sha256'} <= actual: raise SystemExit('ERROR: ZIP payload missing required roots; payload count=' + str(len(actual)))
PY
smoke "$EXTRACTED/$PLUGIN_DIR" "$FIXTURE_135" 6 35mm
smoke "$EXTRACTED/$PLUGIN_DIR" "$FIXTURE_120" 4 645
render_smoke "$EXTRACTED/$PLUGIN_DIR" "$FIXTURE_135"
echo "Built $OUTPUT_ZIP"
