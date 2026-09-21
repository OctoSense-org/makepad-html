# Inline layout and native document interaction

This pass implements horizontal HTML ruby annotations, superscript/subscript
baseline shifts, atomic inline alignment and persistent native document actions
in the independent makepad-html component. It does not establish full WeChat
HTML/CSS compatibility. Robrix's dependency has not been upgraded in this pass.

Blitz now accumulates inline ancestor baseline shifts, resolves percentages
against the span's own line height, and invalidates shaped layout when the
alignment changes. Vendored Parley 0.11.1 applies these shifts to positioned
glyphs **and line extents / subsequent line advance**. Its opt-in CSS root strut
keeps small shifted text from collapsing the normal line box. Atomic inline
boxes expose their text baseline instead of always aligning their bottom edge;
top, bottom, middle, text-top and text-bottom positioning are handled. Style
boundaries no longer strip word-separating spaces or NBSP.

The horizontal HTML ruby formatter pairs base runs with `rt` annotations and
centers each pair. Anonymous base boxes preserve the original DOM parentage and
are released on reconstruction/removal. `rp` fallback parentheses are hidden.
Servo's Stylo build does not expose CSS ruby display/property values, so this is
an HTML ruby formatting context behind the UA inline-block default. It is **not**
a complete implementation of [CSS Ruby](https://www.w3.org/TR/css-ruby-1/).
Inline alignment follows the [CSS line-box model](https://www.w3.org/TR/CSS22/visudet.html#line-height);
sub/super use the CSS Inline fallback offsets (parent font size / 5 down, / 3 up),
which can differ from WebKit's font-specific offsets.

`DocumentSession` retains DOM state on one worker with immutable `ResourceMap`
grants. `HtmlView` emits document-coordinate taps and horizontal scroll input.
Links return a host request, fragments request scrolling, and details/scroll
changes rerender the retained document. No WebView, JS, network client, automatic
browser launch or credential access was introduced. Hosts drop the session on
grant revocation and reject stale asynchronous results. Existing `render_html`
remains a single-render convenience API over the same renderer.

## Evidence

46 default / 48 extended tests passed, including six new inline and five
persistent-interaction regressions. All three native checks passed on the final
viewer binary. The isolated unpatched baseline build also succeeds.

The existing 16 fixture sources are byte-identical. Added fixture 17 covers
nested superscripts, percentage/length shifts, word spacing, atomic alignment,
multiple ruby pairs and fallback parentheses. All 17 × 2 width captures completed
at DPR 2 with the same HTML/resources as real macOS WKWebView. Twenty existing
full-page captures are byte-identical to d01f383; twelve change in typography,
footnotes, ruby, inline SVG line boxes and whitespace around shadowed spans.

| Probe | Width | Content pixels differing before → after |
| --- | ---: | ---: |
| Typography | 390 | 79.054% → 76.484% |
| Typography | 600 | 84.450% → 82.271% |
| Links/footnotes | 390 | 57.900% → 53.570% |
| Links/footnotes | 600 | 56.263% → 51.809% |
| Ruby | 390 / 600 | 86.649% → 69.552% |
| New inline probe | 390 | 80.854% → 58.900% |
| New inline probe | 600 | 83.486% → 59.035% |

Existing cases compare against d01f383; the new probe compares against pinned
upstream's extended build. These are unregistered pixel differences over the
union of nonwhite pixels, threshold 24/255, **not similarity scores**. Font
rasterization and small position differences affect many pixels. The new probe's
maximum measured rectangle difference is 3.172 CSS px. In fixture 11, the ruby
paragraph height and following paragraph position now equal WKWebView; ruby's
own reported rectangle includes annotations here, while WebKit reports the base
box, leaving a 14px rectangle discrepancy. The sup/sub paragraph height still
differs by 1.53125px. No 9/10 rating or actual WeChat client certification is claimed.

Native pointer tests use a hidden, owned Makepad process. They check link events,
no activation on drag, disclosure open/close pixels, fragment navigation with OCR,
clicking after native scrolling, and scrolling/clicking a second horizontal slide.
The standalone viewer deliberately displays external link requests for review;
applications decide how to handle them.

[Validation record](inline-parity-validation.json) ·
[Interactive comparisons](../lab/wechat-corpus/index.html) ·
[Native interaction evidence](../lab/evidence/interactions/native-validation.json) ·
[Native horizontal slide](../lab/evidence/interactions/native-horizontal-scroll.png)

## Remaining work

- Complex/multilevel ruby (`rtc`), ruby overhang/distribution, line breaks within
  a ruby sequence, `ruby-position`, vertical writing, explicit ruby box sizing,
  padding/borders and full CSS ruby display semantics.
- Top/bottom/text-top/text-bottom/middle on ordinary **text spans**, complete
  nested atomic/span alignment, baseline-sensitive floats, exact font metrics,
  inline borders/backgrounds and all text-decoration geometry.
- Text selection/copy, keyboard link focus, accessibility, vertical nested scroll
  routing, touch carousel dragging, animation and tiling. Horizontal input is
  currently wheel/trackpad based. General form interaction is outside admission.
- Automatic table widths, legacy WebKit code layouts, WeChat private elements
  and JS-driven behavior. Production SVG remains rejected. This corpus is
  authored representative HTML, not an exhaustive official WeChat subset.

## Reproduce

```sh
cargo +1.98.0 test --locked
cargo +1.98.0 test --locked --features test-svg,blitz-dom/floats
cargo +1.98.0 build --locked --features makepad --example viewer
python3 lab/verify_native.py target/debug/examples/viewer
python3 lab/verify_text_shadows.py target/debug/examples/viewer
python3 lab/verify_interactions.py target/debug/examples/viewer
python3 lab/wechat-corpus/build.py patched
python3 lab/wechat-corpus/run.py --patched
python3 lab/wechat-corpus/analyze.py
```

The comparison and native scripts require Pillow; analysis also uses NumPy.
`vendor/blitz/inline-4.patch` applies after text-shadow-3. The Parley source,
licenses and local changes are in `vendor/parley` and are selected by workspace
path dependencies without downstream Cargo overrides.
