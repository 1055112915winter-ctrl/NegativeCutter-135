# Architecture

FilmCrop has one detection product with two adapters:

```text
Standalone APP ─┐
                ├─> src/negativecutter_core ─> frames + diagnostics
Lightroom Lua ──┘
```

## Ownership

- `src/negativecutter_core/detector.py` is the only detector implementation.
- `formats.py` owns film codes, families, and aspect ratios.
- `medium_format.py` owns the decision to enter the isolated 120 route.
- `rotation.py` owns rotation estimation and safety rejection.
- `orientation.py` owns pure AB/BC/CD/DA rectangle and angle transforms.
- `APP/filmcrop/detector.py` and
  `NegativeCutter-135.lrplugin/filmcrop/detector.py` are module aliases. Do not
  add detector policy to either adapter.
- APP GUI/export code stays under `APP/filmcrop`.
- Lightroom metadata, virtual copies, and develop settings stay in Lua.

## Compatibility boundary

Callers continue to import `filmcrop.detector`. The adapter aliases that module
to `negativecutter_core.detector`, including private helpers used by existing
tests and `unittest.patch`. PyInstaller specs explicitly include `src` and all
core modules.

## Change rule

Behavior changes start with a failing core test. Adapter tests cover only data
mapping, process invocation, and product-specific UI. Never copy the canonical
detector back into APP or the plugin.
