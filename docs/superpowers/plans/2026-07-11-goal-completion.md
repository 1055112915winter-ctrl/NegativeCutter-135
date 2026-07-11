# FilmCrop Goal Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not use subagents unless the user explicitly authorizes them in the active turn.

**Goal:** Integrate the verified 135/120 refactor into the authoritative `master`, prove both distributable runtimes work, safely remove confirmed repository garbage, and close the active goal only after a requirement-by-requirement audit.

**Architecture:** Preserve `src/negativecutter_core` as the only detector implementation and keep APP/plugin modules as compatibility adapters. Merge the one local-master GUI launch fix into the feature branch before building, verify artifacts from the exact integrated commit, fast-forward `master`, then clean only reproducible or confirmed-garbage worktree/Git data.

**Tech Stack:** Python 3, unittest, NumPy/Pillow/rawpy, PyQt6, Lua/LuaJIT, Lightroom plugin Lua, PyInstaller, macOS codesign, Git worktrees.

---

## Authoritative state at plan creation

- Repository: `/Users/winter/Documents/临时拷贝/Claude Code/filmcrop`
- Feature worktree: `/Users/winter/Documents/临时拷贝/Claude Code/filmcrop/.claude/worktrees/codex-120-v2.4.5`
- Feature branch: `codex/120-v2.4.5@cec1604`
- Local master: `master@4609d92`
- Common release ancestor: `v2.4.5@c404ab5`
- The only local-master source change to preserve is the `ImportAgent.lua` launch hint in `4609d92`; also preserve its `.gitignore` and `AGENTS.md` changes.
- Known storage issue: 54 interrupted `.git/objects/pack/tmp_pack_*` files totaling about 14.07GiB.
- Completion is not proven until Tasks 1–8 all pass.

## Completion record

- Completed on 2026-07-11 against authoritative `master@6db119f`.
- All 32 execution steps below were completed and independently re-audited.
- Integrated runtime commit: `029fbe6`; documentation-only cleanup record: `6db119f`.
- APP and plugin PyInstaller products passed strict codesign and runtime smoke checks.
- All obsolete worktrees and 54 interrupted pack files were removed; Git reports zero garbage.
- Protected 5.4GB fixture corpus and explicit deliverables were retained; root plugin `build/` and `dist/` intermediates were removed during final closure.

## Files and artifacts in scope

**Tracked integration inputs**

- `src/negativecutter_core/**`
- `APP/filmcrop/**`, `APP/NegativeCutter.spec`, `APP/scripts/**`
- `NegativeCutter-135.lrplugin/**`
- `tests/**`, `scripts/**`, `docs/**`, `.gitignore`, `AGENTS.md`, `README.md`

**Generated verification artifacts (must remain untracked)**

- `APP/NegativeCutter.app`
- `NegativeCutter-135.lrplugin/NegativeCutter`
- `NegativeCutter-135.lrplugin/build/`
- `NegativeCutter-135.lrplugin/dist/`
- `NegativeCutter-135-v<version>.zip`

**Protected local assets**

- `test_files/`
- `test_outputs/`
- `bug反馈/`
- `marketing/`
- Any worktree file that is unique and not yet classified as reproducible or obsolete.

### Task 1: Re-establish the safety baseline

**Files:**
- Read: `task_plan.md`
- Read: `findings.md`
- Read: `progress.md`
- Read: `docs/superpowers/plans/2026-07-11-goal-completion.md`

- [x] **Step 1: Confirm both integration worktrees are clean enough to proceed**

Run from the repository root:

```bash
git status --short --branch
git -C .claude/worktrees/codex-120-v2.4.5 status --short --branch
git worktree list
```

Expected: root shows only the known ignored/untracked local `.codex/` directory; feature worktree has no staged or unstaged files; both branches match the hashes recorded above or any explicitly documented successor commits.

- [x] **Step 2: Reconfirm ancestry and the local-master delta**

```bash
git merge-base --is-ancestor c404ab5 master
git merge-base --is-ancestor c404ab5 codex/120-v2.4.5
git show --stat --oneline 4609d92
git diff --name-status c404ab5..master
```

Expected: both ancestry commands exit 0; master contains only the known cleanup/GUI-hint commit above the release baseline.

- [x] **Step 3: Record current disk and garbage measurements in `progress.md`**

```bash
du -sh .git .claude test_files
git count-objects -vH
```

Expected before cleanup: `.git` is approximately 15GiB and reports 54 garbage files / about 14.07GiB. If measurements differ, update `findings.md` before continuing.

### Task 2: Integrate local master into the feature branch

**Files:**
- Merge: `.gitignore`
- Merge: `AGENTS.md`
- Merge: `NegativeCutter-135.lrplugin/ImportAgent.lua`
- Verify: all files changed by `e920e55`, `32a3af1`, and `cec1604`

- [x] **Step 1: Merge, never rebase or overwrite, local master into the feature branch**

Run from the feature worktree:

```bash
git merge --no-edit master
```

Expected: a clean merge commit. If conflicts occur, preserve the `4609d92` GUI launch hint and the feature branch's detector/test/documentation changes; do not choose one whole side blindly.

- [x] **Step 2: Verify the merged contracts before accepting the merge**

```bash
rg -n "python -m filmcrop.gui" NegativeCutter-135.lrplugin/ImportAgent.lua
test -f AGENTS.md
test -f src/negativecutter_core/detector.py
test -f NegativeCutter-135.lrplugin/tests/test_applier_rotation_safety.lua
git diff --check c404ab5..HEAD
git status --short --branch
```

Expected: all commands succeed and the merged worktree is clean.

- [x] **Step 3: Record the merge hash in `progress.md`**

Do not proceed using the old `cec1604` hash after a merge; all subsequent artifact evidence must name the new integrated `HEAD`.

### Task 3: Run the complete source and fixture regression on the integrated commit

**Files:**
- Test: `scripts/run_unit_tests.sh`
- Test: `scripts/run_fixture_tests.sh`
- Test: `tests/**`
- Test: `NegativeCutter-135.lrplugin/tests/**`

- [x] **Step 1: Run deterministic unit, compatibility, routing, packaging-contract, and Lua tests**

```bash
scripts/run_unit_tests.sh
```

Expected: every executed test passes; only tests intentionally requiring fixture environment variables may report skipped inside the deterministic pass. The explicit plugin allow-list must prevent Lightroom E2E scripts from importing.

- [x] **Step 2: Run all repository-owned real fixtures**

```bash
scripts/run_fixture_tests.sh
```

Expected: four real 135 TIFFs pass the six-frame and safe-angle assertions; `raw0014.dng` returns six frames; both real 120 TIFFs return four frames; explicit 645 routing passes.

- [x] **Step 3: Run static integrity checks**

```bash
python3 -m compileall -q src APP/filmcrop NegativeCutter-135.lrplugin/filmcrop
bash -n APP/scripts/build_app.sh APP/scripts/package_app.sh NegativeCutter-135.lrplugin/build.sh scripts/run_unit_tests.sh scripts/run_fixture_tests.sh
git diff --check c404ab5..HEAD
```

Expected: all exit 0.

- [x] **Step 4: Stop on any regression**

If a test fails, add the exact command/error to `progress.md`, diagnose with `superpowers:systematic-debugging`, fix with `superpowers:test-driven-development`, rerun the narrow failing test, then rerun Tasks 3.1–3.3 in full.

### Task 4: Build and smoke-test the standalone macOS APP

**Files:**
- Execute: `APP/scripts/package_app.sh`
- Verify: `APP/NegativeCutter.app`
- Verify: `APP/NegativeCutter.app/Contents/MacOS/NegativeCutter`

- [x] **Step 1: Build the application from the integrated feature commit**

```bash
APP/scripts/package_app.sh
```

Expected: GUI tests pass, PyInstaller completes using an isolated `/tmp` work/config path, `APP/NegativeCutter.app` exists, and strict codesign verification passes.

- [x] **Step 2: Verify bundle identity, architecture, signature, and canonical core inclusion**

```bash
test -x APP/NegativeCutter.app/Contents/MacOS/NegativeCutter
codesign --verify --deep --strict APP/NegativeCutter.app
file APP/NegativeCutter.app/Contents/MacOS/NegativeCutter
python3 - <<'PY'
import os
import subprocess
import time

binary = "APP/NegativeCutter.app/Contents/MacOS/NegativeCutter"
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "offscreen"
process = subprocess.Popen(
    [binary], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
)
time.sleep(3)
if process.poll() is not None:
    stdout, stderr = process.communicate()
    raise SystemExit(
        f"GUI exited during smoke test with {process.returncode}\n"
        f"stdout={stdout}\nstderr={stderr}"
    )
process.terminate()
try:
    process.wait(timeout=5)
except subprocess.TimeoutExpired:
    process.kill()
    process.wait(timeout=5)
print("APP launch smoke: PASS")
PY
```

Expected: executable exists, signature check exits 0, `file` reports the host-compatible architecture, and the offscreen GUI remains alive for three seconds without an import/startup failure.

- [x] **Step 3: Confirm generated APP files did not dirty tracked source**

```bash
git status --short --branch
```

Expected: no tracked changes. If `APP/NegativeCutter.icns` is regenerated, its tracked bytes must remain identical.

### Task 5: Build and smoke-test the Lightroom plugin distribution

**Files:**
- Execute: `NegativeCutter-135.lrplugin/build.sh`
- Verify: `NegativeCutter-135.lrplugin/NegativeCutter/NegativeCutter`
- Verify: `NegativeCutter-135-v<version>.zip`

- [x] **Step 1: Build the plugin executable and ZIP**

```bash
NegativeCutter-135.lrplugin/build.sh
```

Expected: PyInstaller completes, the plugin-local onedir executable is created, and `NegativeCutter-135-v<version>.zip` is written at repository root.

- [x] **Step 2: Smoke-test the packaged engine against a real 135 fixture**

Determine the exact fixture paths from `scripts/run_fixture_tests.sh`, then run:

```bash
NegativeCutter-135.lrplugin/NegativeCutter/NegativeCutter <real-135-path> --frames 6
```

Expected: valid JSON, six frames, `needsReview=false`, and an applied `cropAngle` within ±3°. Preserve the full JSON in `progress.md` only as summarized metrics, not as a large blob.

- [x] **Step 3: Smoke-test the packaged engine against a real 120 fixture**

```bash
NegativeCutter-135.lrplugin/NegativeCutter/NegativeCutter <real-120-path> --format 645 --frames 4
```

Expected: valid JSON, four frames, 120/645 routing retained, and no large applied rotation.

- [x] **Step 4: Audit ZIP contents and signature**

```bash
unzip -l NegativeCutter-135-v*.zip
codesign --verify --deep --strict NegativeCutter-135.lrplugin/NegativeCutter/NegativeCutter
```

Expected: ZIP contains the plugin and runtime but excludes `tests`, `WORK`, `CLAUDE.md`, `debug_visualize.py`, build directories, and logs; signature check exits 0 if the executable is signed. If the build only creates an unsigned executable, record that accurately and do not claim signed distribution readiness.

- [x] **Step 5: Verify release generation did not alter tracked source**

```bash
git status --short --branch
```

Expected: no staged or unstaged tracked files; generated artifacts remain ignored/untracked release products.

### Task 6: Fast-forward authoritative master and reverify it

**Files:**
- Update branch ref: `master`
- Re-run: `scripts/run_unit_tests.sh`
- Re-run: `scripts/run_fixture_tests.sh`

- [x] **Step 1: Capture the verified integrated commit**

From the feature worktree:

```bash
git rev-parse HEAD
```

Record this as `VERIFIED_HEAD` in `progress.md`.

- [x] **Step 2: Fast-forward local master only**

Run from repository root:

```bash
git merge --ff-only codex/120-v2.4.5
```

Expected: master advances to exactly `VERIFIED_HEAD`; no merge conflict and no new merge commit at this stage.

- [x] **Step 3: Prove the authoritative worktree matches the built commit**

```bash
test "$(git rev-parse HEAD)" = "$(git -C .claude/worktrees/codex-120-v2.4.5 rev-parse HEAD)"
git status --short --branch
scripts/run_unit_tests.sh
scripts/run_fixture_tests.sh
```

Expected: hashes match and both test scripts pass from `master`. `.codex/` may remain local/untracked; it must not be staged or committed unless separately authorized.

- [x] **Step 4: Do not push or publish**

The goal authorizes local cleanup/refactor/verification, not remote push, GitHub Release creation, or uploading artifacts. Stop before any external publication.

### Task 7: Classify and clean worktrees and interrupted Git packs

**Files/directories:**
- Inspect: `.claude/worktrees/**`
- Clean: `.git/worktrees/**` via Git commands
- Clean after safety gate: `.git/objects/pack/tmp_pack_*`
- Preserve: `test_files/`, `test_outputs/`, `bug反馈/`, `marketing/`

- [x] **Step 1: Inventory every remaining worktree and its untracked assets**

```bash
git worktree list
git worktree prune --dry-run --verbose
```

For each worktree, run `git -C <path> status --short --branch`, list untracked files, and compare their hashes/content against current tracked files and reproducible release artifacts. Append a keep/archive/delete table to `findings.md` before deleting anything.

- [x] **Step 2: Apply the classification**

- Reproducible `build/`, `dist/`, `.app`, runtime directories, duplicate ICNS, and duplicate release ZIPs: delete as generated artifacts.
- Unique experimental/debug scripts: inspect first. If they contain reusable detection knowledge not represented by current tests/docs, move only that knowledge into a focused test or `docs/` note and commit it; otherwise classify obsolete and delete.
- Worktrees with no remaining unique changes: remove with `git worktree remove <path>`.
- Never delete `test_files`, `test_outputs`, `bug反馈`, or `marketing` as part of this task.

- [x] **Step 3: Prune stale worktree metadata**

```bash
git worktree prune --verbose
git worktree list
```

Expected: no `[prunable]` entry remains. Keep the main worktree and any worktree still containing explicitly preserved, unique work.

- [x] **Step 4: Verify no active Git pack writer owns the temporary packs**

```bash
pgrep -fl 'git|index-pack|pack-objects'
lsof .git/objects/pack/tmp_pack_* 2>/dev/null
```

Expected safety gate: no `index-pack`, `pack-objects`, `git gc`, fetch, clone, or other process has an open handle to any `tmp_pack_*`. If any owner exists, do not clean packs; record the PID/command and stop this subtask.

- [x] **Step 5: Remove only the confirmed interrupted packs, then compact Git**

After the safety gate passes:

```bash
find .git/objects/pack -maxdepth 1 -type f -name 'tmp_pack_*' -print -delete
git gc --prune=now
git fsck --connectivity-only
git count-objects -vH
du -sh .git .claude test_files
```

Expected: `git fsck --connectivity-only` exits 0, `garbage: 0`, the approximately 14.07GiB garbage allocation is gone, and protected fixture size remains unchanged.

- [x] **Step 6: Commit only meaningful tracked cleanup, if any**

If Task 7 promoted unique knowledge into tests/docs, run the full unit and fixture suites and commit those focused tracked changes. Do not commit generated binaries, `.claude/`, `marketing/`, fixtures, logs, or release ZIPs.

### Task 8: Requirement-by-requirement completion audit

**Files:**
- Update: `task_plan.md`
- Update: `findings.md`
- Update: `progress.md`
- Read: `docs/ARCHITECTURE.md`
- Read: `docs/DETECTION_PIPELINE.md`
- Read: `docs/TESTING.md`
- Read: `docs/ADDING_FILM_FORMATS.md`
- Read: `docs/REPOSITORY_HYGIENE.md`

- [x] **Step 1: Audit every user requirement against authoritative evidence**

Create this table in `progress.md` and fill it with current hashes/commands/artifacts:

| Requirement | Required evidence | Pass condition |
|---|---|---|
| Project cleaned | worktree inventory, `git status`, `git count-objects`, disk sizes | tracked master clean; no unexplained stale worktree; Git garbage 0; protected fixtures retained |
| Long-term modules | source tree and compatibility tests | one canonical detector core; APP/plugin adapters import it; docs match code |
| 135 normal and accurate | real fixtures, rotation regression, packaged engine smoke | six-frame fixtures pass; large angles rejected in Python and Lua; packaged engine passes |
| 120 formats complete | registry/routing tests and real fixtures | 645, 6×6, 6×7, 6×8, 6×9 registered and routed; real 120 fixtures pass |
| Documentation complete | five maintenance documents | architecture, pipeline, testing, format extension, hygiene docs exist and are current |
| Deliverables executable | APP/plugin builds and smoke tests | exact integrated commit builds; APP signature check and both packaged engine smokes pass |
| Authoritative integration | Git hashes | local master equals verified integrated commit and is clean |

- [x] **Step 2: Review documentation against current code**

Correct any stale path, command, supported-format list, or packaging statement found during the audit. Run `git diff --check` and commit documentation-only corrections separately.

- [x] **Step 3: Run final verification from local master**

Use `superpowers:verification-before-completion`, then run:

```bash
scripts/run_unit_tests.sh
scripts/run_fixture_tests.sh
APP/scripts/package_app.sh
git status --short --branch
git fsck --connectivity-only
git count-objects -vH
```

Expected: all tests/build/checks pass, master has no staged or unstaged tracked changes, and Git reports zero garbage.

- [x] **Step 4: Close the goal only if every audit row is proven**

If any evidence is missing—especially packaged 135/120 runtime smoke, master integration, or garbage cleanup—leave the goal active and continue the relevant task. If every row passes and no required work remains, call `update_goal` with `status: complete` and report the final verified master hash, test totals, artifact paths, and reclaimed disk space.
