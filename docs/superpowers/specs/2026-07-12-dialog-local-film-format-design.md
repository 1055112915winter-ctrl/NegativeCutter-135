# Lightroom Dialog-Local Film Format Design

## Problem

Lightroom selected the known 135 fixture `52191.tif`, but Batch Process reopened with the previously persisted `120 6×4.5` format and `4` expected frames. The recognition entry therefore supplied an explicit 645/4-frame hint before the detector ran. This is a settings-state defect, not a 135 detector failure.

## Decision

Film format and expected frame count are local to each newly opened Detect Frames or Batch Process settings dialog.

- Every new dialog starts with `Auto` format.
- Auto starts with the existing 35mm-compatible six-frame default while passing no explicit format hint, allowing the established detector routing to decide the family.
- Selecting a format in the current dialog immediately replaces the expected-frame field with that format's default: Auto=6, 35mm=6, 645=4, 6×6=3, 6×7=3, 6×8=2, 6×9=2. The existing 4×5 option keeps the current `defaultExpectedFrames` fallback of 6; this change does not define new 4×5 detection behavior.
- A manual expected-frame edit remains valid for the current dialog and current format only.
- `DetectFrames.lua` and `BatchProcess.lua` no longer directly read or write `filmFormat`, `expectedFrames`, or `expectedFramesFormat` in Lightroom preferences.
- Detect Frames and Batch Process continue to remember their independent preview modes. Film type behavior remains unchanged.
- Existing legacy preference keys are neither migrated nor deleted. `ProcessAgent`, ImportAgent, PluginInfoProvider, and Feedback behavior remains outside this fix.

## Scope

Modify only the settings initialization/persistence contracts in:

- `NegativeCutter-135.lrplugin/DetectFrames.lua`
- `NegativeCutter-135.lrplugin/BatchProcess.lua`
- `NegativeCutter-135.lrplugin/tests/test_recognition_ui_contract.py`

Do not change detector algorithms, format routing, ProcessAgent detection behavior, CropCleaner, virtual-copy creation, HTTP recognition, or the standalone APP.

## Runtime Flow

1. Open either recognition entry.
2. Construct the property table with Auto selected and six expected frames.
3. If the user changes format, refresh the frame count from `ProcessAgent.defaultExpectedFrames`.
4. On confirmation, pass the dialog-local values into the existing staged pipeline.
5. Persist only the entry-specific preview mode and the existing film-type preference.
6. On the next invocation, repeat from Auto/6 regardless of the prior dialog's format.

## Verification

- Static contract test first fails against the current persisted-format code.
- Focused contract preloads stale 645/4 preferences and proves both recognition entries still initialize Auto index/6 without directly reading or writing the three removed preference keys.
- Existing format-change contracts continue to prove format-specific defaults.
- Existing independent preview-mode persistence contracts remain green.
- Focused cases cover Detect→Batch and Batch→Detect isolation; reopening after both OK and Cancel; resetting a manual expected-frame edit on reopen; Auto, 4×5, and every registered format observer default; and preview-mode persistence while format resets.
- Full deterministic and real fixture suites remain green.
- Rebuild and install the validated ZIP, restart Lightroom, select `52191.tif`, and confirm both recognition dialogs open as Auto/6 and produce six-frame preview/copies.
- Reopen after selecting 645 in a prior run and confirm the next dialog again opens as Auto/6.

## Failure Handling

If Auto/6 causes a real fixture regression, stop at the failing evidence; do not compensate by changing detector heuristics. If the installed plugin does not match the rebuilt source hashes, reinstall from the extracted validated ZIP before repeating Lightroom acceptance.
