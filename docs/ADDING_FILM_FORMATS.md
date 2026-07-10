# Adding Film Formats

1. Add one `FilmFormat` entry in `src/negativecutter_core/formats.py`.
2. Choose the real family (`135`, `120`, or another explicitly implemented
   family). Do not infer family from aspect ratio.
3. Add registry tests for normalized code, family, and ratio.
4. Add route tests for horizontal and vertical storage.
5. Add explicit frame-count and auto-mode tests.
6. Add at least one real fixture with independently reviewed frame boundaries.
7. Add the option to both APP and Lightroom selectors only after core tests are
   green.
8. Run unit, fixture, Lua orientation, and packaging gates.

## Current supported matrix

| Code | Family | Ratio | Scope |
|---|---|---:|---|
| `35mm` | 135 | 3:2 | single strip |
| `645` | 120 | 4:3 | single strip |
| `6x6` | 120 | 1:1 | single strip |
| `6x7` | 120 | 7:6 | single strip |
| `6x8` | 120 | 4:3 | single strip |
| `6x9` | 120 | 3:2 | single strip |

Equal ratios are not aliases: 35mm and 6x9 use different detector families.
Multi-row scans and 110 film remain unsupported until real fixtures and a
separate detection model exist.
