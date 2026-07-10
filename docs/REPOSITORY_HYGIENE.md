# Repository Hygiene

## Authoritative surfaces

- core source: `src/negativecutter_core/`
- product adapters: `APP/`, `NegativeCutter-135.lrplugin/`
- deterministic tests: `tests/`, plugin tracked tests, `scripts/run_*_tests.sh`
- maintained documentation: `docs/`
- explicit release products only: `release/*.zip`, DMG, or named deliverables

## Local assets that stay ignored

- `test_files/` (about 5.4GB): irreplaceable recognition fixtures;
- `test_outputs/`: reproducible overlays and investigation output;
- packaged binaries, caches, logs, ZIPs, `.claude/`, marketing material.

Ignored does not mean disposable. Test fixtures and feedback evidence are
retained until their facts are encoded in durable regression tests.

## Measured cleanup backlog (2026-07-11)

- `.git`: about 15GB, including 54 interrupted `tmp_pack_*` files totaling
  14.07GiB;
- `.claude`: about 868MB with nine registered worktrees;
- `release`: about 443MB of historical local packages;
- plugin runtime: about 131MB;
- `test_files`: about 5.4GB and intentionally retained.

Before removing a worktree, run `git status --short`, identify its branch and
HEAD, and confirm all useful changes are reachable or migrated. Before deleting
`tmp_pack_*`, confirm no Git pack/index process is active. Destructive cleanup
is a separate approval boundary; do not mix it with detector changes.

Never upload `marketing/`, `.claude/`, tests, feedback bundles, or local
investigation files as GitHub Release attachments.
