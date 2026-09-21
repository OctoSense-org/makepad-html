//! Inline layout must move both painted glyphs and subsequent line boxes.
use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use makepad_html::{RenderOptions, ResourceMap, render_html};

fn document(body: &str, scale: f32) -> HtmlDocument {
    let mut doc = HtmlDocument::from_html(
        &format!(
            "<!doctype html><style>body{{margin:0;font:24px/32px Arial,sans-serif}}p{{margin:0}}</style>{body}"
        ),
        DocumentConfig {
            viewport: Some(Viewport::new(390, 700, scale, ColorScheme::Light)),
            ..Default::default()
        },
    );
    doc.resolve(0.0);
    doc
}
fn height(doc: &HtmlDocument, id: &str) -> f64 {
    doc.get_client_bounding_rect(doc.get_element_by_id(id).unwrap())
        .unwrap()
        .height
}
fn shift_pixels(value: &str, scale: f32) -> f32 {
    let html = format!(
        "<style>body{{margin:0;font:24px/100px Arial}}span{{font-size:24px;line-height:24px}}</style><span style='color:red'>H</span><span style='color:blue;vertical-align:{value}'>H</span>"
    );
    let output = render_html(
        &html,
        RenderOptions {
            scale,
            ..Default::default()
        },
        &ResourceMap::default(),
    )
    .unwrap();
    let mut red = usize::MAX;
    let mut blue = usize::MAX;
    for (i, p) in output.rgba.chunks_exact(4).enumerate() {
        if p[0] > 160 && p[1] < 80 && p[2] < 80 {
            red = red.min(i / output.width as usize);
        }
        if p[2] > 160 && p[0] < 80 && p[1] < 80 {
            blue = blue.min(i / output.width as usize);
        }
    }
    assert!(red != usize::MAX && blue != usize::MAX, "glyphs missing");
    (red as f32 - blue as f32) / scale
}
#[test]
fn superscripts_subscripts_and_lengths_move_actual_pixels_at_both_dpis() {
    for scale in [1., 2.] {
        for (value, expected) in [
            ("8px", 8.),
            ("-6px", -6.),
            ("50%", 12.),
            ("super", 8.),
            ("sub", -4.8),
            ("baseline", 0.),
        ] {
            let shift = shift_pixels(value, scale);
            assert!(
                (shift - expected).abs() <= 1.,
                "{value} at {scale}x: {shift}, expected {expected}"
            );
        }
    }
}
#[test]
fn shifted_spans_expand_each_line_and_nested_shifts_accumulate() {
    for scale in [1., 2.] {
        let doc = document(
            "<p id='p'>A<span style='vertical-align:30px'>B</span><br>A<span style='vertical-align:-20px'>B</span></p><p id='after'>Next</p>",
            scale,
        );
        assert_eq!(height(&doc, "p"), 114.);
        let after = doc
            .get_client_bounding_rect(doc.get_element_by_id("after").unwrap())
            .unwrap();
        assert_eq!(after.y, 114.);
        let nested = document(
            "<p id='p'>A<span style='vertical-align:10px'><span style='vertical-align:20px'>B</span></span></p>",
            scale,
        );
        assert_eq!(height(&nested, "p"), 62.);
    }
}
#[test]
fn changing_vertical_align_invalidates_layout_and_restores_unshifted_height() {
    let mut doc = document("<p id='p'>A<span id='s'>B</span></p>", 1.);
    let id = doc.get_element_by_id("s").unwrap();
    assert_eq!(height(&doc, "p"), 32.);
    doc.mutate()
        .set_style_property(id, "vertical-align", "30px");
    doc.resolve(0.0);
    assert_eq!(height(&doc, "p"), 62.);
    doc.mutate()
        .set_style_property(id, "vertical-align", "baseline");
    doc.resolve(0.0);
    assert_eq!(height(&doc, "p"), 32.);
}

#[test]
fn whitespace_across_spans_and_nonbreaking_spaces_survive() {
    let doc = document(
        "<p id='p'>Hello<span> world </span><b>again</b><span>&nbsp;中文&nbsp;</span>end</p>",
        1.,
    );
    let node = doc.get_node(doc.get_element_by_id("p").unwrap()).unwrap();
    let text = &node
        .element_data()
        .unwrap()
        .inline_layout_data
        .as_ref()
        .unwrap()
        .text;
    assert_eq!(text, "Hello world again\u{a0}中文\u{a0}end");
}
#[test]
fn ruby_places_annotation_above_base_without_changing_the_dom() {
    let mut doc = document(
        "<p>中文<ruby id='r'><span id='base'>微信</span><rp>(</rp><rt id='rt'>wēi xìn</rt><rp>)</rp></ruby>正文</p>",
        1.,
    );
    let root = doc.get_element_by_id("r").unwrap();
    let annotation = doc.get_element_by_id("rt").unwrap();
    let html = doc.get_node(root).unwrap().outer_html();
    let count = doc.tree().len();
    let r = doc.get_client_bounding_rect(root).unwrap();
    let rt = doc.get_client_bounding_rect(annotation).unwrap();
    assert!(
        rt.width > 20. && rt.height > 5.,
        "annotation vanished: {rt:?}"
    );
    assert!(
        rt.y >= r.y && rt.y + rt.height < r.y + r.height,
        "annotation not above base: {r:?} {rt:?}"
    );
    doc.set_incremental_layout(false);
    for _ in 0..6 {
        doc.resolve(0.);
        assert_eq!(doc.tree().len(), count);
        assert_eq!(doc.get_node(root).unwrap().outer_html(), html);
    }
    let original = r.width;
    let text = doc.get_node(annotation).unwrap().children[0];
    doc.mutate()
        .set_node_text(text, "a much longer pronunciation");
    doc.resolve(0.);
    assert!(doc.get_client_bounding_rect(root).unwrap().width > original);
}
#[test]
fn atomic_inline_top_bottom_and_last_text_baseline() {
    fn rect(doc: &HtmlDocument, id: &str) -> (f64, f64) {
        let r = doc
            .get_client_bounding_rect(doc.get_element_by_id(id).unwrap())
            .unwrap();
        (r.y, r.height)
    }
    let doc = document(
        "<p><span id='a' style='display:inline-block;vertical-align:top;width:40px;height:80px'></span><span id='b' style='display:inline-block;vertical-align:top;width:40px;height:20px'></span></p><p><span id='c' style='display:inline-block;vertical-align:bottom;width:40px;height:80px'></span><span id='d' style='display:inline-block;vertical-align:bottom;width:40px;height:20px'></span></p><p id='p'>A<span style='display:inline-block'>B<br>C</span></p>",
        1.,
    );
    let (ay, _) = rect(&doc, "a");
    let (by, _) = rect(&doc, "b");
    assert_eq!(ay, by);
    let (cy, ch) = rect(&doc, "c");
    let (dy, dh) = rect(&doc, "d");
    assert_eq!(cy + ch, dy + dh);
    assert_eq!(
        height(&doc, "p"),
        64.,
        "inline-block must expose its last text baseline"
    );
}
