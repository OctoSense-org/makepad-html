# Text-shadow parity pass

Blitz previously omitted CSS `text-shadow`, including article heading shadows
and text made visible only by its shadow. The painter now resolves the inherited
computed list, paints its entries in reverse order behind foreground text, and
reuses glyph and text-decoration geometry. Adjacent runs with equal shadows share
a blur layer. CurrentColor, nested overrides, transparent text, transforms,
clipping and style updates are covered.

The implementation follows the [CSS text-shadow model](https://www.w3.org/TR/css-text-decor-3/#text-shadow-property).
Blur uses Gaussian sigma = CSS blur radius / 2 through AnyRender's single blur
primitive. The host enables `anyrender_vello_cpu/filters`. Shadows do not change
layout or scrollable overflow. Shadow-casting branches bypass geometric box
culling so offscreen text can cast visible shadows; ancestor clip layers remain
in effect. No Makepad source or document rewriting is needed.

## Validation

- 35 default and 37 extended tests passed on aarch64 macOS, Rust 1.98.0.
- Eight new regressions also ran against `c2b7c08`: all eight failed there.
  Hard-shadow references use ordinary translated glyphs/decorations at 1× and
  2×. Other checks cover blur, list order, inheritance, dynamic changes, nested
  spans, overflow, transforms, offscreen ancestors and the production API.
- Native Makepad rendering and scrolling passed. The existing top/bottom
  screenshots are byte-identical to the previous revision.
- A separate hidden native viewer loaded the new fixture, then a control with
  only text-shadow declarations changed to none. The control and positive have
  identical chrome; Chinese OCR identifies the requested fixture. Their
  screenshots differ at 53,138 pixels over the 24/255 threshold. This establishes
  that the effect reaches the native texture, not WebKit similarity. The header
  comparison uses 100 CSS pixels scaled by the reported DPI: the first CI run
  exposed a fixed-pixel crop assumption on its DPR-1 display. Its saved screenshots
  pass the corrected crop, pixel and OCR checks (8,316 differing pixels).
- All 32 corpus captures completed. The previous 15 fixture source hashes are
  unchanged; 26 existing non-shadow full-page PNGs are byte-identical.

| Fixture | Width | Content pixel differences before → after |
| --- | ---: | ---: |
| Heading/quotes | 390 | 15.818% → 14.872% |
| Heading/quotes | 600 | 11.921% → 11.287% |
| Effects card | 390 | 6.144% → 5.389% |
| Effects card | 600 | 4.424% → 3.880% |
| New shadow fixture | 390 | 74.659% → 62.368% |
| New shadow fixture | 600 | 74.655% → 62.358% |

Existing cases compare against `c2b7c08`; the new fixture compares against pinned
upstream's extended build. Both renderers receive the exact same HTML, at DPR 2.
WKWebView references for existing cases are reused; the new fixture has fresh
WKWebView captures. Differences use the union of nonwhite content and a 24/255
threshold, with no image alignment. These numbers are not similarity scores.
The new fixture's remaining font/spacing errors move many pixels. Geometric
measurements are unchanged by this paint-only pass; transformed probe bounds
also differ because Blitz reports layout bounds and WebKit reports transformed
bounds.

[Interactive comparisons](../lab/wechat-corpus/index.html) ·
[Native screenshot](../lab/evidence/text-shadows/native-shadows.png) ·
[Native none control](../lab/evidence/text-shadows/native-none-control.png) ·
[Validation record](text-shadow-parity-validation.json)

## Limits

This is tested initial shadow support, not complete text-rendering parity.
Font weight/rasterization, inter-span whitespace, underline position and dash
phase at differently shadowed decoration fragments still need work. Shadows
are grouped per line; overlapping lines and separate inline formatting contexts
need more stacking tests. Extreme font overhangs and decoration extents remain
outside this fixture set. Conservative shadow-subtree culling increases work for
long documents with shadows; cached ink bounds are a future optimization.

The pinned CPU backend handles a single filter primitive. Enabling filters does
not establish general multi-function CSS filter support. Upstream disables
filters when its multithreading feature is enabled; downstream feature unification
must preserve the tested single-threaded configuration for blur.

The native widget remains a static bitmap preview. Ruby/sup/sub, automatic table
widths, inline borders, legacy code layouts and persistent native interaction
remain separate gaps. The fixture is an authored CSS regression, not a captured
published WeChat article. No complete WeChat compatibility or 9/10 score is claimed.

## Reproduce

```sh
cargo +1.98.0 test --locked
cargo +1.98.0 test --locked --features test-svg,blitz-dom/floats
cargo +1.98.0 build --locked --features makepad --example viewer
python3 lab/verify_native.py target/debug/examples/viewer
# Requires Pillow 11.3.0; CI installs it in a local venv.
python3 lab/verify_text_shadows.py target/debug/examples/viewer
python3 lab/wechat-corpus/build.py patched
python3 lab/wechat-corpus/run.py --patched
python3 lab/wechat-corpus/analyze.py
```

The incremental vendor diff is `vendor/blitz/text-shadow-3.patch`; apply it after
`table-2.patch`. Historical baseline builds retain their original feature set.
Use separate Cargo target directories for before/after worktrees: identically
named path packages can overwrite each other's cached executable artifacts.
The final tests above used rebuilt current painter and host artifacts after the
historical negative checks.
