#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMMON_DIR=$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)
STORAGE_ROOT=$(CDPATH= cd -- "$COMMON_DIR/.." && pwd)
FIXTURES=${FILMCROP_FIXTURE_ROOT:-"$STORAGE_ROOT/test_files"}

export NEGATIVECUTTER_TEST_DNG="$FIXTURES/raw0014.dng"
export NEGATIVECUTTER_TEST_120_A="$FIXTURES/Untitled (3).tif"
export NEGATIVECUTTER_TEST_120_B="$FIXTURES/未标题(1).tif"
export NEGATIVECUTTER_TEST_135_DIR="$FIXTURES"

for required in \
  "$NEGATIVECUTTER_TEST_DNG" \
  "$NEGATIVECUTTER_TEST_120_A" \
  "$NEGATIVECUTTER_TEST_120_B" \
  "$NEGATIVECUTTER_TEST_135_DIR/52191.tif" \
  "$NEGATIVECUTTER_TEST_135_DIR/52194.tif" \
  "$NEGATIVECUTTER_TEST_135_DIR/SHD4001.tif" \
  "$NEGATIVECUTTER_TEST_135_DIR/luckyc20013.tif"
do
  test -f "$required" || { echo "missing fixture: $required" >&2; exit 1; }
done

cd "$ROOT"
python3 -m unittest tests.test_real_135_fixtures -v
PYTHONPATH=NegativeCutter-135.lrplugin python3 -m unittest discover \
  -s NegativeCutter-135.lrplugin/tests -p test_auto_frame_detection.py -v
PYTHONPATH=NegativeCutter-135.lrplugin python3 -m unittest discover \
  -s NegativeCutter-135.lrplugin/tests -p test_medium_format_real_fixtures.py -v
