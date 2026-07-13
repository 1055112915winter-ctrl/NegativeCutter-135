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
