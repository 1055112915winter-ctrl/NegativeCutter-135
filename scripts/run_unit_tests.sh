#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

# Keep fixture-backed tests out of the deterministic gate.  They are run by
# run_fixture_tests.sh with their required assets and must not appear as an
# apparently-green suite full of expected skips here.
for pattern in \
  test_core_compatibility.py \
  test_format_api_routing.py \
  test_format_registry.py \
  'test_gui_*.py' \
  test_lua_adapter_contracts.py \
  test_medium_format_gap_refinement.py \
  test_orientation_contract.py \
  test_package_app.py \
  test_rotation_safety.py \
  test_test_commands.py
do
  python3 -m unittest discover -s tests -p "$pattern" -v
done

for pattern in \
  test_plugin_hardening.py \
  test_live_crop_preview.py \
  test_preview_dialog_contract.py \
  test_recognition_ui_contract.py \
  test_medium_format_detection.py
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
