# Lightroom v2.5.0 acceptance evidence

This directory keeps durable evidence that is intentionally excluded from the
release ZIP by `NegativeCutter-135.lrplugin/build.sh`'s explicit allowlist.

## Recovered renderer and lifecycle evidence

- `renderer-last-good.jpeg` shows a successful uniform-batch preview for
  `52191.tif` with Confirm enabled.
- `renderer-failure.jpeg` shows the same last-good preview after a reversible
  renderer failure injection. The UI reports the renderer path failure and
  Confirm is disabled.
- SHA-256:
  - `renderer-last-good.jpeg`:
    `bd410662e82ff1321a668172207911366b831e3bf28027b8356460d651749043`
  - `renderer-failure.jpeg`:
    `a5b35d7cca5ad596bc096ba6280232bde7bb0292154d2ef3b4f8092e12013e26`

The original acceptance session is
`/Users/winter/.codex/sessions/2026/07/12/rollout-2026-07-12T23-34-13-019f56f6-f712-7161-9638-7b74730ff787.jsonl`:

- Lines 232–239 record the owner marker, `active.json`, and generation JPEG
  surviving Lightroom TERM, followed by restart cleanup of the marker-owned
  directory (`marked_dirs_after_restart=0`, `all_files_after_restart=0`).
- Lines 277–292 record renderer failure injection, visible error state,
  disabled Confirm, unchanged last-good `active.json`/JPEG hashes, and zero
  `.partial` files.
- Lines 583–584 record restoration from the validated release ZIP.
- Lines 680–681 record preservation of 20 unmarked empty directories.

These references replace the earlier unindexed lifecycle claim. Final v2.5.0
package acceptance evidence is appended here after the exact release ZIP is
installed and Lightroom is restarted.

## Initial failure followed by later success

The direct Lightroom run completed at 2026-07-14 02:07 CST:

- `initial-failure-later-success-selection.jpeg` shows two ordered targets.
  The first grid item is a cropped `52191.tif` virtual copy moved to the top of
  its 13-item stack; the second item is the uncropped `52194.tif` original.
- `NegativeCutter.ProcessAgent.log` lines 643–645 record the first item failing
  at `sourceWidth=2030`, `sourceHeight=3024`, `needsReview=true`.
- The same log lines 647–653 immediately record the later original succeeding
  with six frames at `sourceWidth=291`, `sourceHeight=2677`,
  `needsReview=false`, decoded/LR size `4657x42834`.
- `initial-failure-later-success-result.jpeg` records the single terminal
  result: `部分完成`, processed 2, unprocessed 0, created 6 virtual copies,
  errors 1.
- SHA-256:
  - `initial-failure-later-success-selection.jpeg`:
    `acf97d70db25a7dd698ec25d43fb0e2734d2f77b42ea7958d6d1052a0b3cd535`
  - `initial-failure-later-success-result.jpeg`:
    `2786340afbdfbe4eb63b82858fe518a292fff6d3f2674c291b6af95cfd844e25`

This closes the ordered direct-evidence gap that the deterministic Lua
contract alone could not close.

## Final release artifact

- Artifact: `release/NegativeCutter-135-v2.5.0.zip`
- SHA-256:
  `fd6c5b2a523b785efad3f6a76b69aaf39a4afb4c2aef83c391c896808f2b1790`
- The extracted package is arm64, passes `codesign --verify --deep --strict`,
  has 174 manifest lines and exactly 174 payload files/links, and contains no
  tests, preview state, bytecode, `marketing/`, or `.claude/` content.

The exact ZIP install into `~/Library/Application Support/Adobe/Lightroom/Modules`
was attempted after Lightroom quit, but the managed approval layer rejected
the external write because the current approval quota was exhausted. No
alternate installation path was used. The direct 02:07 behavior run therefore
used the current repository plugin registered in Lightroom (the log identifies
that source path), while the final ZIP was independently built and verified.

The final live HTTP port-binding rerun was likewise rejected by the same
managed approval boundary after sandboxed localhost binding failed. The prior
current-feature HTTP acceptance remains valid for behavior (`/health` 200 and
`/analyze` 200 with six frames); the v2.5.0-only change to that path is version
metadata.
