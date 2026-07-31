# Testing

## Deterministic unit suite

```bash
scripts/run_unit_tests.sh
```

This runs the deterministic APP/core Python tests, an explicit allow-list of
deterministic plugin tests, and standalone LuaJIT tests. Fixture-backed tests
are deliberately excluded here, so a green result has no hidden
"expected skip" cases. It also does not discover Lightroom UI/E2E automation
scripts.

Every root `tests/test_*.py` file must be classified as either deterministic or
fixture-backed. `tests/test_test_commands.py` enforces that classification so a
new test cannot be silently omitted from both gates.

## Unified non-Computer-Use gate

Use the composed entrypoint when handing off a local verification result:

```bash
scripts/verify_non_computer_use.sh all
```

Use `quick` for deterministic checks only, or `fixtures` when the large local
sample corpus is already available. The composed gate also runs shell syntax,
Python compilation with a temporary bytecode prefix, and `git diff --check`.
It does not claim Lightroom UI acceptance or distributable-artifact
verification; those remain separate gates.

## macOS distribution gates

The release workflow is intentionally fail-closed:

```bash
scripts/verify_macos_artifact.sh --root NegativeCutter-135.lrplugin/NegativeCutter \
  --arch arm64 --min-macos 14.0
packaging/build_macos_pkg.sh --source-plugin NegativeCutter-135.lrplugin \
  --output /absolute/path/NegativeCutter.pkg --version 2.4.7
```

The first command requires Developer ID signatures by default; use
`--allow-adhoc` only for local structural diagnostics, never as release
evidence. The PKG command requires Developer ID Application/Installer
identities and a `notarytool` keychain profile. It signs nested Mach-O code,
checks architecture and deployment targets, notarizes, staples, and runs
Gatekeeper/package verification. Missing credentials are a blocked release
gate, not a reason to weaken the checks.

## Real recognition fixtures

```bash
scripts/run_fixture_tests.sh
```

By default a worktree locates `test_files/` beside the shared `.git` directory.
Override with `FILMCROP_FIXTURE_ROOT=/path/to/test_files`.

The fixture gate covers:

- 135: `52191`, `52194`, `SHD4001`, `luckyc20013` — six frames, strict 3:2,
  no review, safe rotation;
- DNG: `raw0014` — automatic six-frame regression;
- 120: `Untitled (3)` and `未标题(1)` — four frames in auto and explicit 645
  modes, plus the reviewed pixel-edge truth bands.

The compatibility probe
`NegativeCutter-135.lrplugin/tests/test_dng_decode_gate.py` is not part of the
standard gates because its `subifd` assertion is environment-specific: an
installed `rawpy` loader is expected to win on machines with rawpy available.
Run it only when validating the no-rawpy fallback environment.

## Lightroom E2E

Lightroom UI automation is opt-in and must be run only with Lightroom open and
the intended catalog selected. It is not imported by unit discovery. Record
the application version, plugin bundle, sample, orientation, and resulting
develop settings when running it.

## Adding a regression

Write the smallest test that fails for the observed symptom, verify RED, make
one change, verify GREEN, then run both scripts. A visual overlay is supporting
evidence, not a substitute for coordinate assertions.
