//! CSS 2.2 collapsed borders. Resolve grid-edge intervals, never a dense slot
//! matrix: a large rowspan must not allocate rows × columns border entries.
use super::table::{TableCell, TableColumn, TableRow};
use crate::{BaseDocument, NodeId};
use std::collections::BTreeMap;
use style::values::{computed::BorderStyle, specified::box_::DisplayInside};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BorderSide {
    Top,
    Right,
    Bottom,
    Left,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CollapsedBorder {
    pub node_id: NodeId,
    pub side: BorderSide,
    pub width: f32,
    pub style: BorderStyle,
    priority: u8,
    order: usize,
}

impl CollapsedBorder {
    pub fn used_width(&self) -> f32 {
        if self.style.none_or_hidden() {
            0.0
        } else {
            self.width
        }
    }

    fn rank(&self) -> (bool, bool, u32, u8, u8, std::cmp::Reverse<usize>) {
        let style = match self.style {
            BorderStyle::Hidden => 9,
            BorderStyle::Double => 8,
            BorderStyle::Solid => 7,
            BorderStyle::Dashed => 6,
            BorderStyle::Dotted => 5,
            BorderStyle::Ridge => 4,
            BorderStyle::Outset => 3,
            BorderStyle::Groove => 2,
            BorderStyle::Inset => 1,
            BorderStyle::None => 0,
        };
        // Nonnegative finite computed widths have monotonically ordered bits.
        (
            self.style == BorderStyle::Hidden,
            self.style != BorderStyle::None,
            self.width.to_bits(),
            style,
            self.priority,
            std::cmp::Reverse(self.order),
        )
    }
}

#[derive(Clone, Debug)]
pub struct CollapsedBorderSegment {
    pub horizontal: bool,
    pub line: usize,
    pub start: usize,
    pub end: usize,
    pub border: CollapsedBorder,
}

#[derive(Clone)]
struct Candidate {
    start: usize,
    end: usize,
    border: CollapsedBorder,
}

fn sides(
    doc: &BaseDocument,
    node_id: NodeId,
    priority: u8,
    order: usize,
) -> Option<[CollapsedBorder; 4]> {
    let style = doc.nodes[node_id].primary_styles()?;
    let b = style.get_border();
    Some(
        [
            (BorderSide::Top, b.border_top_width.0, b.border_top_style),
            (
                BorderSide::Right,
                b.border_right_width.0,
                b.border_right_style,
            ),
            (
                BorderSide::Bottom,
                b.border_bottom_width.0,
                b.border_bottom_style,
            ),
            (BorderSide::Left, b.border_left_width.0, b.border_left_style),
        ]
        .map(|(side, width, style)| CollapsedBorder {
            node_id,
            side,
            width: width.to_f32_px(),
            style,
            priority,
            order,
        }),
    )
}

pub(super) fn resolve(
    doc: &BaseDocument,
    root: NodeId,
    cells: &[TableCell],
    rows: &[TableRow],
    columns: &[TableColumn],
    column_count: usize,
) -> Vec<CollapsedBorderSegment> {
    let row_count = rows.len();
    let rtl = doc.nodes[root]
        .primary_styles()
        .is_some_and(|s| s.clone_direction() == style::computed_values::direction::T::Rtl);
    if row_count == 0 || column_count == 0 {
        return Vec::new();
    }
    let mut edges: BTreeMap<(bool, usize), Vec<Candidate>> = BTreeMap::new();
    let mut add = |id, priority, order, r0, r1, c0, c1| {
        if let Some(borders) = sides(doc, id, priority, order) {
            let (left, right) = if rtl {
                (borders[1], borders[3])
            } else {
                (borders[3], borders[1])
            };
            for (horizontal, line, start, end, border) in [
                (true, r0, c0, c1, borders[0]),
                (false, c1, r0, r1, right),
                (true, r1, c0, c1, borders[2]),
                (false, c0, r0, r1, left),
            ] {
                if start < end {
                    edges
                        .entry((horizontal, line))
                        .or_default()
                        .push(Candidate { start, end, border });
                }
            }
        }
    };
    add(root, 0, 0, 0, row_count, 0, column_count);
    // Equal-origin ties use logical start/top order, including RTL tables.
    for (i, column) in columns.iter().take(column_count).enumerate() {
        add(column.node_id, 2, i, 0, row_count, i, i + 1);
    }
    for (i, row) in rows.iter().enumerate() {
        add(row.node_id, 4, i, i, i + 1, 0, column_count);
    }
    let mut groups: BTreeMap<NodeId, (u8, usize, usize)> = BTreeMap::new();
    for (priority, items) in [
        (1, columns.iter().map(|c| c.node_id).collect::<Vec<_>>()),
        (3, rows.iter().map(|r| r.node_id).collect()),
    ] {
        for (i, id) in items.iter().enumerate() {
            let mut parent = doc.nodes[*id].parent;
            while let Some(id) = parent.filter(|id| *id != root) {
                let node = &doc.nodes[id];
                let group = node.primary_styles().is_some_and(|s| {
                    matches!(
                        s.clone_display().inside(),
                        DisplayInside::TableColumnGroup
                            | DisplayInside::TableRowGroup
                            | DisplayInside::TableHeaderGroup
                            | DisplayInside::TableFooterGroup
                    )
                });
                if group {
                    let range = groups.entry(id).or_insert((priority, i, i + 1));
                    range.1 = range.1.min(i);
                    range.2 = range.2.max(i + 1);
                    break;
                }
                parent = node.parent;
            }
        }
    }
    for (id, (priority, start, end)) in groups {
        if priority == 1 {
            add(
                id,
                priority,
                start,
                0,
                row_count,
                start,
                end.min(column_count),
            );
        } else {
            add(id, priority, start, start, end, 0, column_count);
        }
    }
    for (i, cell) in cells.iter().enumerate() {
        add(
            cell.node_id,
            5,
            i,
            cell.row,
            cell.row_end,
            cell.column,
            cell.column_end,
        );
    }
    drop(add);

    let mut result: Vec<CollapsedBorderSegment> = Vec::new();
    for ((horizontal, line), candidates) in edges {
        let mut points: Vec<_> = candidates.iter().flat_map(|c| [c.start, c.end]).collect();
        // A spanning cell suppresses *all* borders inside it, including row and
        // column borders. Its endpoints can split a longer candidate edge.
        let spans: Vec<_> = cells
            .iter()
            .filter_map(|c| {
                let (lo, hi, start, end) = if horizontal {
                    (c.row, c.row_end, c.column, c.column_end)
                } else {
                    (c.column, c.column_end, c.row, c.row_end)
                };
                (lo < line && line < hi).then_some((start, end))
            })
            .collect();
        for &(start, end) in &spans {
            points.extend([start, end]);
        }
        points.sort_unstable();
        points.dedup();
        for pair in points.windows(2) {
            let (start, end) = (pair[0], pair[1]);
            if spans.iter().any(|&(lo, hi)| lo <= start && end <= hi) {
                continue;
            }
            let Some(winner) = candidates
                .iter()
                .filter(|c| c.start <= start && end <= c.end)
                .max_by_key(|c| c.border.rank())
            else {
                continue;
            };
            if let Some(last) = result.last_mut().filter(|last| {
                last.horizontal == horizontal
                    && last.line == line
                    && last.end == start
                    && last.border == winner.border
            }) {
                last.end = end;
            } else {
                result.push(CollapsedBorderSegment {
                    horizontal,
                    line,
                    start,
                    end,
                    border: winner.border,
                });
            }
        }
    }
    result
}

/// Half the winning edge width is reserved inside each adjacent cell.
pub(super) fn cell_widths(
    cell: &TableCell,
    edges: &[CollapsedBorderSegment],
    rtl: bool,
) -> taffy::Rect<f32> {
    let width = |horizontal, line, start, end| {
        edges
            .iter()
            .filter(|e| {
                e.horizontal == horizontal && e.line == line && e.start < end && start < e.end
            })
            .map(|e| e.border.used_width() / 2.0)
            .fold(0.0, f32::max)
    };
    taffy::Rect {
        top: width(true, cell.row, cell.column, cell.column_end),
        bottom: width(true, cell.row_end, cell.column, cell.column_end),
        left: width(
            false,
            if rtl { cell.column_end } else { cell.column },
            cell.row,
            cell.row_end,
        ),
        right: width(
            false,
            if rtl { cell.column } else { cell.column_end },
            cell.row,
            cell.row_end,
        ),
    }
}
