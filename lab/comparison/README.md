# DigitalOcean HTML: Blitz vs macOS WKWebView

Open [the interactive comparison](index.html). It has side-by-side captures,
desktop/narrow viewport selection, a same-coordinate wipe slider, text crops and
difference images. Raw captures and DOM measurements are in `evidence/`.

Source: [digitalocean/sample-html index.html](https://github.com/digitalocean/sample-html/blob/b658ada1c68912e9ac4026db63d687e8e2aa808a/index.html),
commit `b658ada1c68912e9ac4026db63d687e8e2aa808a`.
SHA-256: `96448c90c3ed0ede400f5f68d904201428bc730aa4355b3a4141f4c4c11071bc`.
Both engines received the exact same 4,394 original bytes. The downloaded source
is kept under ignored `inputs/`; reproduction fetches and verifies the pin.

## Method

- Real macOS 26.6.2 `WKWebView.takeSnapshot` in a nonpersistent data store,
  versus Blitz `e99fbdbd` / Vello CPU pixels from the same renderer dependencies
  used by Robrix. No HTML/CSS rewriting or image registration/alignment.
- Viewports: 800×600 and 390×844 CSS pixels, both DPR 2 and light appearance.
  The narrow viewport is macOS WebKit, **not** an iOS device test.
- Static comparison: WKWebView page JavaScript disabled. Host diagnostic JS
  waits for `document.fonts.ready` and reads computed styles and geometry;
  it does not modify the document. Blitz has no JS engine.
- Dynamic comparison: unchanged original HTML with WKWebView page JS enabled.
  A document-start `WKUserScript` replaces `Math.random` with a seeded LCG for
  reproducible colors. This is a test environment change, not source rewriting.
  Card/body clicks use DOM `.click()`, not native pointer events.
- The production `makepad_html::render_html` entry point rejects this original
  page with `unsupported active/document element: script`. `compare_html.rs`
  is a separate diagnostic raw-engine path with no network provider that can
  load resources. It leaves script elements inert, and does not loosen the
  app's admission policy. Original-source compatibility in Robrix is **not**
  claimed by these successful raw-engine screenshots.

## Results

| Measurement | Blitz | WKWebView |
| --- | ---: | ---: |
| Desktop card x / y, CSS px | 268 / 240.5 | 266.8125 / 240.5 |
| Narrow card x / y, CSS px | 63 / 362.5 | 61.8125 / 362.5 |
| Card width × height, CSS px | 264 × 119 | 266.359375 × 119 |
| Static content | `#000000` | `#000000` |
| Page JS on load | Not executed | `#20bc92` |
| JS card click | No JS runtime | Remains `#20bc92` |
| JS body click | No JS runtime | Changes to `#71da4e` |

The same static geometry differences occurred at both viewports. Flex centering,
100% page height, CSS variables, padding, rem sizing and static colors rendered.
The card rectangles have 99.114% intersection-over-union. Blitz's card is 2.359375
CSS pixels narrower; its left edge is 1.1875 pixels farther right. Although both
engines report the same y coordinate, the observed Blitz card raster starts one
device pixel lower (0.5 CSS pixel at DPR 2).

Pixels with any RGB channel error >16/255:

- Card union region: **4.762%** at either viewport.
- Text union crop, including six device pixels of margin: **16.332%**.
- Whole frame: 0.315% desktop, 0.460% narrow. The matching black background
  dominates these whole-frame numbers; they are not meaningful global fidelity
  scores. Text crops show stroke/antialiasing and glyph spacing differences.
  Font selection, shaping and rasterization have not yet been isolated as causes.

`results.json` includes rectangle values, absolute channel errors, crop bounds,
source and artifact hashes, and explicit test qualifications. Difference PNGs
multiply absolute RGB error by four for visibility. Text zooms use 3× nearest-
neighbor enlargement of identical crop coordinates; original captures are kept.

Conclusion: this sample's static layout is close, with measurable typography and
pixel-snapping differences. Its JS-driven behavior is not reproduced by Blitz.
This one simple color page does not cover article images, tables, complex WeChat
CSS, long documents or editing, and does not establish a 9/10 compatibility score.

## Reproduce

Requires macOS, Swift, Rust 1.98, Python 3, Pillow and NumPy. From the repo root:

```sh
cargo +1.98.0 build --locked --manifest-path Cargo.toml --example compare_html
swiftc lab/comparison/webview.swift -o target/html-comparison-webview
python3 lab/comparison/compare.py --render \
  --blitz-bin target/debug/examples/compare_html \
  --webview-bin target/html-comparison-webview
open lab/comparison/index.html
```

`compare.py` without `--render` only recomputes metrics/composites from existing
native captures. The page's random color behavior is tested, but arbitrary page
JS, external resources, navigation and iOS are outside this experiment.

Local-file inputs, downloaded third-party resources and their captures are ignored.
Reproducible authored fixtures and published captures live in `../wechat-corpus/`.
