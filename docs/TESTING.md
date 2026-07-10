# Testing

## Deterministic unit suite

```bash
scripts/run_unit_tests.sh
```

This runs APP/core Python tests, an explicit allow-list of plugin tests, and
standalone LuaJIT tests. It deliberately does not discover Lightroom UI/E2E
automation scripts.

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
  modes.

## Lightroom E2E

Lightroom UI automation is opt-in and must be run only with Lightroom open and
the intended catalog selected. It is not imported by unit discovery. Record
the application version, plugin bundle, sample, orientation, and resulting
develop settings when running it.

## Adding a regression

Write the smallest test that fails for the observed symptom, verify RED, make
one change, verify GREEN, then run both scripts. A visual overlay is supporting
evidence, not a substitute for coordinate assertions.
