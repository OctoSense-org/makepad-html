//! Raw-engine regressions, independent of the production HTML admission policy.
use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

fn document(body: &str) -> HtmlDocument {
    let mut doc = HtmlDocument::from_html(
        &format!("<!doctype html><style>body{{margin:0;font:16px/24px sans-serif}}</style>{body}"),
        DocumentConfig {
            viewport: Some(Viewport::new(390, 700, 1.0, ColorScheme::Light)),
            ..Default::default()
        },
    );
    doc.resolve(0.0);
    doc
}

fn rect(doc: &HtmlDocument, id: &str) -> [f32; 4] {
    let id = doc.get_element_by_id(id).unwrap();
    let r = doc.get_client_bounding_rect(id).unwrap();
    [r.x as f32, r.y as f32, r.width as f32, r.height as f32]
}

#[test]
fn css_table_bare_text_matches_an_explicit_row_and_cell() {
    let doc = document(
        "<section id='implicit' style='display:table;padding:6px 18px;margin:auto'>Theme <strong>title</strong></section><section id='explicit' style='display:table;padding:6px 18px;margin:auto'><div style='display:table-row'><div style='display:table-cell'>Theme <strong>title</strong></div></div></section>",
    );
    let a = rect(&doc, "implicit");
    let b = rect(&doc, "explicit");
    assert!(a[2] > 80.0 && a[3] >= 36.0, "title disappeared: {a:?}");
    assert_eq!((a[0], a[2], a[3]), (b[0], b[2], b[3]));
}

#[test]
fn anonymous_table_boxes_preserve_dom_and_do_not_leak() {
    let mut doc = document(
        "<div id='table' style='display:table'>Before<span id='span'> title</span><div style='display:table-row'><div style='display:table-cell'>Existing row</div></div>After</div>",
    );
    let table = doc.get_element_by_id("table").unwrap();
    let span = doc.get_element_by_id("span").unwrap();
    let original = doc.get_node(table).unwrap().outer_html();
    let count = doc.tree().len();
    assert_eq!(doc.get_node(span).unwrap().parent, Some(table));
    assert!(doc.tree().iter().filter(|(_, n)| n.is_anonymous()).count() >= 4);
    doc.set_incremental_layout(false);
    for _ in 0..12 {
        doc.resolve(0.0);
        assert_eq!(doc.tree().len(), count);
        assert_eq!(doc.get_node(table).unwrap().outer_html(), original);
    }
    let anonymous = doc.get_node(table).unwrap().anonymous_blocks.clone();
    doc.mutate().remove_and_drop_node(table);
    for id in anonymous {
        assert!(doc.tree().get(id).is_none());
    }
}

#[test]
fn anonymous_table_text_updates_after_editing_and_restyling() {
    let mut doc = document("<div id='title' style='display:table'>Short</div>");
    let title = doc.get_element_by_id("title").unwrap();
    let text = doc.get_node(title).unwrap().children[0];
    doc.mutate().set_style_property(title, "font-size", "24px");
    doc.mutate()
        .set_style_property(title, "line-height", "40px");
    doc.resolve(0.0);
    let fresh_style = document(
        "<div id='title' style='display:table;font-size:24px;line-height:40px'>Short</div>",
    );
    assert_eq!(rect(&doc, "title"), rect(&fresh_style, "title"));
    doc.mutate()
        .set_node_text(text, "A much longer edited title");
    doc.resolve(0.0);
    let fresh = document(
        "<div id='title' style='display:table;font-size:24px;line-height:40px'>A much longer edited title</div>",
    );
    assert_eq!(rect(&doc, "title"), rect(&fresh, "title"));
}

#[test]
fn atomic_gallery_respects_parent_nowrap_but_wraps_internal_text() {
    for mode in ["nowrap", "normal"] {
        let doc = document(&format!(
            "<div style='width:200px;white-space:{mode};overflow-x:auto'><section id='first' style='display:inline-block;width:100%;min-height:100px;white-space:normal;vertical-align:top'>Some text that is long enough to wrap inside the first card</section><section id='second' style='display:inline-block;width:100%;min-height:100px;white-space:normal;vertical-align:top'>Second card</section></div>"
        ));
        let a = rect(&doc, "first");
        let b = rect(&doc, "second");
        assert!(a[3] >= 48.0, "internal text did not wrap: {a:?}");
        if mode == "nowrap" {
            assert_eq!(b[0] - a[0], 200.0);
            assert!((b[1] - a[1]).abs() < 1.0, "gallery wrapped: {a:?} {b:?}");
        } else {
            assert_eq!(a[0], b[0]);
            assert!(b[1] >= a[1] + a[3]);
        }
    }
}

#[cfg(feature = "test-svg")]
mod svg {
    use super::*;
    use anyrender::{PaintScene as _, render_to_buffer};
    use anyrender_vello_cpu::VelloCpuImageRenderer;
    use blitz_dom::util::Color;
    use peniko::{Fill, kurbo::Rect};

    fn pixel(doc: &mut HtmlDocument) -> Vec<u8> {
        let rgba = render_to_buffer::<VelloCpuImageRenderer, _>(
            |scene| {
                scene.fill(
                    Fill::NonZero,
                    Default::default(),
                    Color::WHITE,
                    None,
                    &Rect::new(0.0, 0.0, 390.0, 700.0),
                );
                blitz_paint::paint_scene(scene, doc, 1.0, 390, 700, 0, 0);
            },
            390,
            700,
        );
        rgba[(10 * 390 + 10) * 4..][..4].to_vec()
    }

    #[test]
    fn svg_current_color_inherits_and_updates_without_mutating_html() {
        let mut doc = document(
            "<section id='parent' style='color:#16836a'><svg id='svg' width='40' height='40'><rect width='40' height='40' fill='currentColor'/></svg></section>",
        );
        let svg = doc.get_element_by_id("svg").unwrap();
        let source = doc.get_node(svg).unwrap().outer_html();
        assert_eq!(pixel(&mut doc), [22, 131, 106, 255]);
        let parent = doc.get_element_by_id("parent").unwrap();
        doc.mutate().set_style_property(parent, "color", "#123456");
        doc.resolve(0.0);
        assert_eq!(pixel(&mut doc), [18, 52, 86, 255]);
        assert_eq!(doc.get_node(svg).unwrap().outer_html(), source);
    }

    #[test]
    fn svg_local_color_overrides_html_inheritance() {
        for local in ["color='#b03040'", "style='color:#b03040'", ""] {
            let inner = if local.is_empty() {
                "<style>svg{color:#b03040}</style>"
            } else {
                ""
            };
            let mut doc = document(&format!(
                "<div style='color:#16836a'><svg width='40' height='40' {local}>{inner}<rect width='40' height='40' fill='currentColor'/></svg></div>"
            ));
            assert_eq!(pixel(&mut doc), [176, 48, 64, 255], "override {local}");
        }
    }
}
