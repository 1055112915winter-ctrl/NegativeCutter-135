#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

python3 -m unittest discover -s tests -p 'test_*.py' -v

for pattern in \
  test_auto_frame_detection.py \
  test_plugin_hardening.py \
  test_live_crop_preview.py \
  test_preview_dialog_contract.py \
  test_recognition_ui_contract.py \
  test_medium_format_detection.py \
  test_medium_format_real_fixtures.py
do
  PYTHONPATH=NegativeCutter-135.lrplugin python3 -m unittest discover \
    -s NegativeCutter-135.lrplugin/tests -p "$pattern" -v
done

python3 scripts/run_lua_test.py NegativeCutter-135.lrplugin/tests/test_applier_rotation_safety.lua
python3 scripts/run_lua_test.py NegativeCutter-135.lrplugin/tests/test_process_agent_orientation.lua
python3 scripts/run_lua_test.py NegativeCutter-135.lrplugin/tests/test_preview_agent.lua
python3 scripts/run_lua_test.py NegativeCutter-135.lrplugin/tests/test_preview_runtime.lua
python3 scripts/run_lua_test.py NegativeCutter-135.lrplugin/tests/test_process_pipeline.lua
python3 scripts/run_lua_test.py NegativeCutter-135.lrplugin/tests/test_recognition_progress.lua
