# makepad-html

English | [简体中文](README.zh-CN.md)

Reusable native HTML/CSS rendering for Makepad applications. The standalone Rust core lays out and paints documents; the optional `HtmlView` widget displays them with native scrolling. Applications supply HTML, resource bytes, viewport size and lifecycle decisions.

This repository owns the rendering API, Makepad adapter, standalone viewer, Blitz patches and compatibility lab. Robrix’s article editor is one consumer. [Architecture and responsibilities](docs/architecture.md).

The tested engine is [Blitz e99fbdbd](https://github.com/DioxusLabs/blitz/tree/e99fbdbd1d03b9f0aa1622c3f810d95daac92042), not a WebView: html5ever → Stylo → Taffy/Parley → AnyRender/Vello CPU → RGBA. This first integration preserves the input HTML/CSS for rendering; HTML editing and lossless style-preserving import remain separate work.

```rust
use ::makepad_html::{render_html, RenderOptions, ResourceMap};

let mut resources = ResourceMap::default();
// Bytes have already been selected/authorized/downloaded by the host.
let stylesheet_url = resources.insert_css("theme.css", "p { color: #337b60 }")?;
let html = format!("<link rel='stylesheet' href='{stylesheet_url}'><p>你好，世界</p>");
let bitmap = render_html(&html, RenderOptions::default(), &resources)?;
assert_eq!(bitmap.rgba.len(), bitmap.width as usize * bitmap.height as usize * 4);
# Ok::<(), makepad_html::RenderError>(())
```

Run `render_html` on a worker. The host checks that the document and any applicable resource grants are still current before presenting the result. A `ResourceMap` is an immutable grant snapshot, not a persistent authority token. A `DocumentSession` retains that snapshot until the host drops the session. Build a new map after a permission or account change. Never place access tokens, cookies or signed remote URLs in document HTML/CSS or resource identifiers.

## Resource boundary

Only exact URLs under `https://makepad-html.invalid/assets/<id>` which the host inserted can resolve. PNG/JPEG images are decoded with bounds before admission; CSS is UTF-8 and size limited. Relative references resolve into that namespace. Unmapped URLs, including HTTP(S), `file:`, `data:`, CSS `@import`, image/background URLs and `@font-face` URLs, receive empty responses without I/O. Completing denied responses matters because otherwise a denied stylesheet can leave upstream waiting indefinitely.

There is no `blitz-net`, request client, navigation integration, clipboard integration or JavaScript package. Active and subdocument elements (`script`, `iframe`, forms, object/embed), SVG and MathML are rejected. The document is parsed as standards-mode HTML. Event attributes are inert in this renderer; **this is not an HTML sanitizer for subsequent browser use**.

The default `system-fonts` feature intentionally enables OS font discovery and loading. That allows `font-family: "PingFang SC", system-ui, sans-serif` on Apple hosts; it is distinct from document-authorized file loading. `--no-default-features` disables OS font discovery, but then this initial API does not provide a custom font registration interface and text coverage is limited.

Budgets: 256 KiB HTML; conservative token/depth preflight (16,384 tokens, 64 explicit open tags); 48 approved resources, 8 MiB each and 24 MiB total; CSS 64 KiB per resource; images at most 4096 × 4096 with a 64 MiB decoded allocation limit; 128 resource requests; eight resolve passes; at most 16,777,216 output pixels. Output dimensions are capped at 16,384 pixels, below Vello CPU's 16-bit dimension limit. Long content reports `clipped`; hosts must expose that status or use a future paged/tiled implementation instead of silently treating a crop as the whole document.

These limits bound inputs, granted resources and output allocation. They do **not** bound all intermediate Stylo/Taffy/Vello allocations or provide a cancellable CPU deadline. A worker thread keeps the UI responsive but is not process isolation. Do not claim this beta engine is hardened against arbitrary hostile HTML/CSS; untrusted public imports need a separately supervised process and resource controls before broad deployment.

## Makepad adapter

Enable `features = ["makepad"]`, register `makepad_html::makepad::script_mod(vm)` after base Makepad widgets, and instantiate `mod.widgets.HtmlView`. Bring `makepad_html::makepad::HtmlViewWidgetRefExt` into Rust scope:

```rust,ignore
ui.html_view(cx, ids!(html_preview)).set_rendered(cx, &bitmap);
// On logout, grant revocation, or document replacement:
ui.html_view(cx, ids!(html_preview)).clear(cx);
```

Makepad also re-exports its built-in parser as `makepad_html`. When using
`use makepad_widgets::*`, import this external crate with `::makepad_html`
or give it a Cargo dependency alias (Robrix uses `makepad-html-renderer`).

For a `Widget`/`RefMut<Widget>` receiver rather than a `WidgetRef`, import
`HtmlViewWidgetExt` instead.

The adapter converts RGBA to Makepad's `VecBGRAu8_32`, displays the result in a clipped native scroll view, and has no WebView. Makepad is pinned to `47837267faf6970a6cc36acedf9f83846b277307` in this crate's lockfile, using the same source/branch as Robrix to avoid duplicate widget types. Hosts should render at the measured view width and current DPI; changing the view width only scales the existing bitmap until the host renders again.

The adapter emits document-coordinate taps and horizontal wheel/trackpad events.
Keep a `DocumentSession` on a worker, call `activate` / `scroll_horizontal`, then
`render` after a state change. `HtmlAction::OpenLink` is a request to the host;
no browser, HTTP client or navigation happens automatically. Forward `ScrollTo`
to `HtmlViewRef::scroll_to`. The standalone viewer demonstrates this lifecycle,
including links after scrolling, fragment navigation, details disclosures and
nested horizontal scroll containers. Drop the session and clear the widget when
the host replaces a document or revokes grants; reject stale worker results.

Text selection/copy, keyboard link focus, accessibility text and rich-text editing
are not yet supplied. Rendering and texture upload still replace a full bitmap;
this is not a tiled renderer.

## Reproduce

This crate has its own workspace/lockfile so it can be built independently from Robrix. Runtime tests used Rust 1.98.0 on aarch64 macOS. A locked build check also passed on Rust 1.94.0 with default features disabled.

```sh
cargo +1.98.0 test --locked
cargo +1.98.0 test --locked --features test-svg,blitz-dom/floats
cargo +1.98.0 run --locked --example render_fixture -- target/render-evidence
cargo +1.98.0 run --locked --features makepad --example viewer

# View a host-selected document. Resources are explicit ID=PATH grants.
cargo +1.98.0 run --locked --features makepad --example viewer -- \
  page.html theme.css=./theme.css logo.png=./logo.png

# macOS: verify the native widget, screenshot OCR and scrolling.
python3 lab/verify_native.py target/debug/examples/viewer
```

The native script starts only the isolated fixture binary, uses an owned loopback bridge, captures and OCR-checks Chinese text and the table, scrolls the native view, then exits that process. It does not connect a Matrix account. `MAKEPAD_HIDE_WINDOWS=1` keeps this verification off the user's screen.

Evidence and limitations are in `lab/README.md`. Tests prove local behaviors, not a 9/10 WeChat visual score. Upstream remains beta and its CSS support is incomplete: [upstream status](https://blitz.is/status/css).

## Compatibility lab

[WeChat-derived CSS cases](lab/wechat-corpus/README.md) are one compatibility suite,
with original source hashes, pinned upstream and patched Blitz captures, and
real WKWebView reference screenshots. [HTML5 comparisons](lab/comparison/README.md)
cover general HTML. Neither suite depends on the article editor.

Engine patches are owned here under [vendor/blitz](vendor/blitz/README.makepad-html.md).
Consumers use this crate directly; they do not need Cargo patch overrides or a
Robrix checkout. The widget displays a bitmap backed optionally by a persistent offline document.
Selection, keyboard/accessibility integration, animation and more complete gesture
routing remain roadmap work.

## Origin

Extracted from `OctoSense-org/robrix2`'s `wechat-ui` renderer work, based on Robrix
commit `7f24f14ac5c59f65b84f078944443e3977c9f6f0` plus the reviewed CSS fixes.
Original license notices are retained. Blitz source provenance and the exact
local diffs are recorded in `vendor/blitz/UPSTREAM.json`, `wechat-css-1.patch`
and the subsequent `table-2.patch`, `text-shadow-3.patch` and `inline-4.patch`.

The table parity pass fixes merged-cell borders, border conflicts and cell
alignment. It passes 27 default / 29 extended tests and retains the same
production resource policy. See [measured results and remaining gaps](docs/table-parity.md).

The text-shadow pass adds offsets, blur, multiple shadows, inherited colors and
text-decoration shadows. It enables Vello CPU's `filters` feature; the tested
backend uses single-threaded rendering (upstream disables filters when its
`multithreading` feature is unified in). This does not establish general CSS
filter-chain support. See [comparison results and limits](docs/text-shadow-parity.md).

The inline/interaction pass adds horizontal HTML ruby annotations, sup/sub and
nested length/percentage shifts, corrected atomic inline baselines, preserved
inter-span spaces, and worker-owned document interactions. Parley 0.11.1 is
vendored alongside Blitz so downstream apps receive the same layout patch.
See [measurements, native evidence and remaining limits](docs/inline-parity.md).
