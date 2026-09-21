# Local Parley changes

Source: crates.io parley 0.11.1; upstream git eea3503dd6cf17130cbb07348e0ff2c918300e94
(https://github.com/linebender/parley). Original MIT and Apache-2.0 licenses retained.

Adds resolved CSS inline baseline displacements and root strut metrics, supplied
by Blitz after shaping. Shifted spans affect glyph baselines and line extents /
line advance. Layouts without these opt-in metrics retain the upstream path.

Also supports explicit atomic-inline baseline/top/bottom placement; line advance
uses the final extents. TreeBuilder retains spaces across inline style boundaries
and treats NBSP as content when trimming collapsed ASCII whitespace. White-space
mode transitions flush pending text under its original mode. Regression coverage
is in the host's `tests/inline_regressions.rs`; original upstream source/tests and
license notices are retained.
