use anyrender::{PaintScene as _, render_to_buffer};
use anyrender_vello_cpu::VelloCpuImageRenderer;
use blitz_dom::{DocumentConfig, util::Color};
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use peniko::{Fill, kurbo::Rect};

fn document(body: &str) -> HtmlDocument {
    let mut doc = HtmlDocument::from_html(
        &format!(
            "<!doctype html><style>body{{margin:20px;background:white}}table{{border-collapse:collapse}}td{{border:2px solid red;padding:0;width:60px;height:40px}}</style>{body}"
        ),
        DocumentConfig {
            viewport: Some(Viewport::new(300, 300, 1.0, ColorScheme::Light)),
            ..Default::default()
        },
    );
    doc.resolve(0.0);
    doc
}
fn rect(doc: &HtmlDocument, id: &str) -> Rect {
    let r = doc
        .get_client_bounding_rect(doc.get_element_by_id(id).unwrap())
        .unwrap();
    Rect::new(r.x, r.y, r.x + r.width, r.y + r.height)
}
fn paint(doc: &mut HtmlDocument) -> Vec<u8> {
    render_to_buffer::<VelloCpuImageRenderer, _>(
        |scene| {
            scene.fill(
                Fill::NonZero,
                Default::default(),
                Color::WHITE,
                None,
                &Rect::new(0., 0., 300., 300.),
            );
            blitz_paint::paint_scene(scene, doc, 1.0, 300, 300, 0, 0);
        },
        300,
        300,
    )
}
fn pixel(rgba: &[u8], x: f64, y: f64) -> &[u8] {
    &rgba[((y as usize) * 300 + x as usize) * 4..][..4]
}

#[test]
fn merged_cells_have_no_internal_border_and_keep_adjacent_edges() {
    let mut doc = document(
        "<table><tr><td id='a' rowspan='2'></td><td id='b'></td></tr><tr><td id='c'></td></tr><tr><td id='d' colspan='2'></td></tr></table>",
    );
    let rgba = paint(&mut doc);
    let a = rect(&doc, "a");
    let b = rect(&doc, "b");
    let c = rect(&doc, "c");
    let d = rect(&doc, "d");
    assert_eq!(pixel(&rgba, a.center().x, c.y0), [255, 255, 255, 255]);
    assert_eq!(pixel(&rgba, b.center().x, c.y0), [255, 0, 0, 255]);
    assert_eq!(pixel(&rgba, b.x0, d.center().y), [255, 255, 255, 255]);
}

#[test]
fn wider_cell_border_wins_and_hidden_suppresses_neighbors() {
    let mut doc = document(
        "<table><tr><td id='a' style='border-right:6px solid blue'></td><td id='b' style='border-left:4px solid green'></td></tr></table>",
    );
    let b = rect(&doc, "b");
    assert_eq!(
        pixel(&paint(&mut doc), b.x0, b.center().y),
        [0, 0, 255, 255]
    );
    let id = doc.get_element_by_id("b").unwrap();
    doc.mutate().set_style_property(id, "border-left", "hidden");
    doc.resolve(0.0);
    let b = rect(&doc, "b");
    assert_eq!(
        pixel(&paint(&mut doc), b.x0, b.center().y),
        [255, 255, 255, 255]
    );
}

#[test]
fn table_cell_vertical_alignment_moves_contents_inside_full_cell() {
    for (align, fraction) in [("top", 0.), ("middle", 0.5), ("bottom", 1.)] {
        let doc = document(&format!(
            "<table><tr><td id='cell' style='height:80px;vertical-align:{align}'><div id='mark' style='height:10px;width:10px;background:blue'></div></td></tr></table>"
        ));
        let cell = rect(&doc, "cell");
        let mark = rect(&doc, "mark");
        let expected = cell.y0 + 1. + (cell.height() - 2. - 10.) * fraction;
        assert!(
            (mark.y0 - expected).abs() < 1.,
            "{align}: {cell:?} {mark:?}, expected {expected}"
        );
    }
}

#[test]
fn equal_borders_prefer_logical_start_cell_in_ltr_and_rtl() {
    for direction in ["ltr", "rtl"] {
        let mut doc = document(&format!(
            "<table style='direction:{direction}'><tr><td id='a' style='border-color:blue'></td><td id='b' style='border-color:green'></td></tr></table>"
        ));
        let a = rect(&doc, "a");
        let edge = if direction == "ltr" { a.x1 } else { a.x0 };
        assert_eq!(
            pixel(&paint(&mut doc), edge, a.center().y),
            [0, 0, 255, 255],
            "{direction}"
        );
    }
}

#[test]
fn border_conflicts_include_rows_columns_groups_and_table() {
    for (table, colgroup, col, rowgroup, row, cell, expected) in [
        ("blue", "", "", "", "", "none", [0, 0, 255, 255]),
        ("blue", "green", "", "", "", "none", [0, 128, 0, 255]),
        ("blue", "green", "red", "", "", "none", [255, 0, 0, 255]),
        ("blue", "green", "red", "blue", "", "none", [0, 0, 255, 255]),
        (
            "blue",
            "green",
            "red",
            "blue",
            "green",
            "none",
            [0, 128, 0, 255],
        ),
        (
            "blue",
            "green",
            "red",
            "blue",
            "green",
            "red",
            [255, 0, 0, 255],
        ),
    ] {
        let border = |color: &str| {
            if color.is_empty() || color == "none" {
                "border:none".to_string()
            } else {
                format!("border:4px solid {color}")
            }
        };
        let mut doc = document(&format!(
            "<table style='{}'><colgroup style='{}'><col style='{}'></colgroup><tbody style='{}'><tr style='{}'><td id='cell' style='{}'></td></tr></tbody></table>",
            border(table),
            border(colgroup),
            border(col),
            border(rowgroup),
            border(row),
            border(cell)
        ));
        let r = rect(&doc, "cell");
        assert_eq!(pixel(&paint(&mut doc), r.center().x, r.y0), expected);
    }
}

#[test]
fn rowspan_zero_stops_at_row_group_and_does_not_shift_next_group() {
    let doc = document(
        "<table><tbody><tr><td id='a' rowspan='0'></td><td id='b'></td></tr><tr><td id='c'></td></tr></tbody><tbody><tr><td id='d'></td><td id='e'></td></tr></tbody></table>",
    );
    let a = rect(&doc, "a");
    let c = rect(&doc, "c");
    let d = rect(&doc, "d");
    assert_eq!(a.x0, d.x0);
    assert_eq!(a.y1, c.y1);
    assert_eq!(d.y0, c.y1);
    assert!(rect(&doc, "e").x0 > d.x0);
}

#[test]
fn cell_alignment_and_collapsed_borders_update_without_accumulating_offsets() {
    let mut doc = document(
        "<table id='table'><tr><td id='cell' style='height:80px;vertical-align:middle'><span id='mark' style='display:inline-block;width:10px;height:10px;background:blue'></span></td></tr></table>",
    );
    let cell = doc.get_element_by_id("cell").unwrap();
    let mut previous_top = None;
    for align in ["bottom", "top", "middle", "bottom", "middle"] {
        doc.mutate()
            .set_style_property(cell, "vertical-align", align);
        doc.resolve(0.0);
        let fresh = document(&format!(
            "<table id='table'><tr><td id='cell' style='height:80px;vertical-align:{align}'><span id='mark' style='display:inline-block;width:10px;height:10px;background:blue'></span></td></tr></table>"
        ));
        assert_eq!(rect(&doc, "mark"), rect(&fresh, "mark"), "{align}");
        if align == "top" {
            previous_top = Some(rect(&doc, "mark").y0);
        }
        if align == "bottom" {
            if let Some(top) = previous_top {
                assert!(rect(&doc, "mark").y0 - top > 40.0);
            }
        }
    }
    let table = doc.get_element_by_id("table").unwrap();
    for collapse in ["separate", "collapse", "separate", "collapse"] {
        doc.mutate()
            .set_style_property(table, "border-collapse", collapse);
        doc.resolve(0.0);
        let fresh = document(&format!(
            "<table id='table' style='border-collapse:{collapse}'><tr><td id='cell' style='height:80px;vertical-align:middle'><span id='mark' style='display:inline-block;width:10px;height:10px;background:blue'></span></td></tr></table>"
        ));
        assert_eq!(rect(&doc, "mark"), rect(&fresh, "mark"), "{collapse}");
        assert_eq!(rect(&doc, "cell"), rect(&fresh, "cell"), "{collapse}");
    }
}

#[test]
fn double_and_dashed_borders_keep_gaps_and_winning_style() {
    for (style, color) in [("double", [0, 0, 255, 255]), ("dashed", [0, 0, 255, 255])] {
        let mut doc = document(&format!(
            "<table><tr><td id='cell' style='width:150px;border-top:6px {style} blue'></td></tr></table>"
        ));
        let cell = rect(&doc, "cell");
        let rgba = paint(&mut doc);
        if style == "double" {
            assert_eq!(pixel(&rgba, cell.center().x, cell.y0), [255, 255, 255, 255]);
            assert_eq!(pixel(&rgba, cell.center().x, cell.y0 - 2.0), color);
            assert_eq!(pixel(&rgba, cell.center().x, cell.y0 + 2.0), color);
        } else {
            let samples: Vec<_> = ((cell.x0 as usize + 10)..(cell.x1 as usize - 10))
                .map(|x| pixel(&rgba, x as f64, cell.y0))
                .collect();
            assert!(samples.contains(&color.as_slice()));
            assert!(samples.contains(&[255, 255, 255, 255].as_slice()));
        }
    }
}

#[test]
fn dotted_collapsed_border_paints_real_dots_at_both_dpis() {
    for scale in [1, 2] {
        let mut doc = document(
            "<table><tr><td id='cell' style='width:150px;border-top:6px dotted blue'></td></tr></table>",
        );
        let cell = rect(&doc, "cell");
        let size = 300 * scale;
        let rgba = render_to_buffer::<VelloCpuImageRenderer, _>(
            |scene| {
                scene.fill(
                    Fill::NonZero,
                    Default::default(),
                    Color::WHITE,
                    None,
                    &Rect::new(0., 0., size as f64, size as f64),
                );
                blitz_paint::paint_scene(scene, &mut doc, scale as f64, size, size, 0, 0);
            },
            size,
            size,
        );
        let y = (cell.y0 * scale as f64) as usize;
        let colors: Vec<_> = (((cell.x0 + 10.) * scale as f64) as usize
            ..((cell.x1 - 10.) * scale as f64) as usize)
            .map(|x| &rgba[(y * size as usize + x) * 4..][..4])
            .collect();
        assert!(
            colors.contains(&[0, 0, 255, 255].as_slice()),
            "missing dots at {scale}x"
        );
        assert!(
            colors.contains(&[255, 255, 255, 255].as_slice()),
            "missing gaps at {scale}x"
        );
    }
}
