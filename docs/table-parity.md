# Table parity pass

The old collapsed-border painter repeated the first cell's border across every
grid line. This drew through merged cells, lost mixed borders, and could disagree
with the widths used while measuring content.

The renderer now resolves edge intervals, applies winning half-widths during
layout, and paints those edges after cell backgrounds. Cells retain their full
grid area while top/middle/bottom alignment positions their contents. Rowspan
placement, rowspan=0 and row-group boundaries use the same cell coordinates as
border painting. These are engine changes; no Makepad source or editor schema
changes are needed.

Conflict precedence follows the [CSS table border rules](https://www.w3.org/TR/CSS22/tables.html#border-conflict-resolution):
hidden, visible width/style, element origin, then logical start/top. Resources,
active-content admission and SVG restrictions are unchanged.

## Evidence

The 14 previous fixture source hashes remain unchanged. A fifteenth fixture
adds merged cells, border conflicts, row/column groups, RTL, multiple line
styles and cell alignment. Both engines receive identical HTML at 390 and 600
CSS pixels, DPR 2. Existing exact-source WKWebView captures are reused; the new
fixture has fresh native WKWebView captures.

| Fixture | Before: maximum probe error | After | Content pixel differences before → after |
| --- | ---: | ---: | --- |
| Existing article table, 390px | 6.75px | 0.75px | 38.420% → 31.696% |
| Existing article table, 600px | 6.75px | 0.75px | 34.996% → 28.520% |
| New edge fixture, 390px | 66px | 2px | 90.662% → 64.411% |
| New edge fixture, 600px | 66px | 2px | 90.750% → 64.411% |

The first two rows compare with makepad-html `4920a99`; the new fixture compares
with pinned upstream Blitz's extended build. Pixel differences are measured over
nonwhite content at the existing 24/255 threshold, without image alignment.
They are diagnostic differences, not similarity scores. A small geometric error
can still move many border pixels; neither metric replaces screenshot review.

- 27 default and 29 extended tests passed on aarch64 macOS, Rust 1.98.0.
- Nine table regressions cover pixel output, geometry, RTL, row/column origins,
  span placement, style changes and dotted borders at 1× and 2×. The first eight
  were also run against `4920a99`: all eight failed there.
- All 30 patched fixture captures completed. The 26 screenshots for the 13
  unchanged non-table cases are byte-identical to the previous revision.
- Native Makepad texture upload, Chinese screenshot text, table visibility and
  scrolling passed. OCR checks several independent row labels and saves its raw
  output, allowing one recognition miss.

Open [the comparison page](../lab/wechat-corpus/index.html) and choose either
table fixture. Machine-readable results are in [table-parity-validation.json](table-parity-validation.json).
The independent [lab instructions](../lab/wechat-corpus/README.md) reproduce the
builds and captures. `vendor/blitz/table-2.patch` is the incremental source diff.

## Remaining work

Automatic column distribution still differs from WebKit, and a cell spanning
unequal borders can have different height metrics. Dash rhythm, dotted placement
and multi-border junctions need further calibration. Shared row baselines,
vertical writing modes and the full CSS tables specification are not covered.

The next article-layout gaps are ruby/sup/sub baselines, legacy WebKit code-block
layout, inline decorations/text shadows and positioned containing blocks.
Persistent DOM, nested scrolling, selection and links remain a separate native
interaction stage. This pass does not establish complete WeChat compatibility,
iOS/Android parity, or a 9/10 score.
