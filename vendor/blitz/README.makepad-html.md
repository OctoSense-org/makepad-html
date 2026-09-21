# makepad-html renderer patches

Renderer crates copied from DioxusLabs/blitz at
`e99fbdbd1d03b9f0aa1622c3f810d95daac92042` (MIT OR Apache-2.0;
`stylo_taffy` declares MIT OR Apache-2.0 OR MPL-2.0).
Only the six required workspace crates are included. The workspace manifest
retains the upstream dependency versions; unrelated workspace members and
root examples are omitted. The makepad-html workspace uses these sources through internal path dependencies.
Downstream applications require no Cargo patch overrides.

## Patch set: wechat-css-1

- `blitz-dom/src/layout/table.rs` and `construct.rs`: generate missing CSS
  table rows/cells around ordinary content, retain DOM parentage and free
  anonymous nodes through the existing table-owner lifecycle.
- `blitz-dom/src/layout/inline.rs`: honor parent nowrap in contexts containing
  only atomic inline boxes (Parley 0.11 otherwise defaults to Wrap when there
  is no text cluster). Keep internal child wrapping and normal wrapping intact.
  This is deliberately bounded; mixed text/box wrapping still needs upstream work.
- `blitz-dom/src/layout/construct.rs`, `damage.rs`, `node/node.rs`: preserve
  authored currentColor in serialization, seed inline SVG's missing color from
  computed HTML style, and reparse after SVG style damage. Preserve SVG-local
  presentation attributes and CSS. This does not import all external HTML
  stylesheet rules into SVG.

`wechat-css-1.patch` is the review diff against the pinned upstream files.
The root workspace carries the pinned upstream package/dependency metadata for
these six crates. Cargo.upstream.toml records the prior extracted workspace.

Regression tests: `tests/css_regressions.rs`.
Same-source visual evidence and reproduction: `lab/wechat-corpus/README.md`.
Production `makepad-html::render_html` still rejects SVG and active content;
raw SVG tests opt into `test-svg`. No arbitrary resource access was added.
