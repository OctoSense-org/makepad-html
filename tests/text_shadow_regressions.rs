//! Pixel reftests for CSS text shadows. References use ordinary translated text,
//! so these fail when shadow drawing is absent even if layout/paint succeeds.
use anyrender::{PaintScene as _, render_to_buffer};
use anyrender_vello_cpu::VelloCpuImageRenderer;
use blitz_dom::{DocumentConfig, util::Color};
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use peniko::{Fill, kurbo::Rect};

fn document(body: &str, scale: f32) -> HtmlDocument {
    let mut doc = HtmlDocument::from_html(
        &format!(
            "<!doctype html><style>body{{margin:0;background:white;font:32px/48px Arial,sans-serif}}p{{margin:40px;width:220px}}</style>{body}"
        ),
        DocumentConfig {
            viewport: Some(Viewport::new(320, 240, scale, ColorScheme::Light)),
            ..Default::default()
        },
    );
    doc.resolve(0.0);
    doc
}
fn paint(doc: &mut HtmlDocument, scale: f32) -> Vec<u8> {
    let (width, height) = ((320.0 * scale) as u32, (240.0 * scale) as u32);
    render_to_buffer::<VelloCpuImageRenderer, _>(
        |scene| {
            scene.fill(
                Fill::NonZero,
                Default::default(),
                Color::WHITE,
                None,
                &Rect::new(0., 0., width as f64, height as f64),
            );
            blitz_paint::paint_scene(scene, doc, scale as f64, width, height, 0, 0);
        },
        width,
        height,
    )
}
fn image(html: &str, scale: f32) -> Vec<u8> {
    paint(&mut document(html, scale), scale)
}
fn red_pixels(rgba: &[u8]) -> usize {
    rgba.chunks_exact(4)
        .filter(|p| p[0] > 200 && p[1] < 230 && p[2] < 230)
        .count()
}
fn assert_same(actual: &[u8], expected: &[u8]) {
    let different = actual
        .chunks_exact(4)
        .zip(expected.chunks_exact(4))
        .filter(|(a, b)| a != b)
        .count();
    assert_eq!(
        different, 0,
        "{different} pixels differ from translated-text reference"
    );
}

#[test]
fn hard_shadow_matches_translated_text_and_decorations_at_both_dpis() {
    for scale in [1.0, 2.0] {
        for decoration in ["none", "underline", "overline", "line-through"] {
            let actual = image(
                &format!(
                    "<p style='color:transparent;text-decoration:{decoration};text-shadow:24px 12px 0 red'>文章 Abg</p>"
                ),
                scale,
            );
            let reference = image(
                &format!(
                    "<p style='color:red;text-decoration:{decoration};transform:translate(24px,12px)'>文章 Abg</p>"
                ),
                scale,
            );
            assert!(red_pixels(&reference) > 100);
            assert_same(&actual, &reference);
        }
    }
}

#[test]
fn multiple_shadows_paint_first_on_top_and_never_cover_foreground() {
    let actual = image(
        "<p style='color:transparent;text-shadow:24px 12px red,24px 12px blue'>HHH</p>",
        1.0,
    );
    assert_same(
        &actual,
        &image(
            "<p style='position:absolute;left:24px;top:12px;color:blue'>HHH</p><p style='position:absolute;left:24px;top:12px;color:red'>HHH</p>",
            1.0,
        ),
    );
    let ordinary = image("<p><span>HHH</span><span>HHH</span></p>", 1.0);
    let shadowed = image(
        "<p><span>HHH</span><span style='text-shadow:-40px 0 red'>HHH</span></p>",
        1.0,
    );
    assert!(red_pixels(&shadowed) > 20);
    for (plain, with_shadow) in ordinary.chunks_exact(4).zip(shadowed.chunks_exact(4)) {
        if plain == [0, 0, 0, 255] {
            assert_eq!(with_shadow, plain, "later shadow covered foreground text");
        }
    }
}

#[test]
fn inherited_current_color_shadow_and_none_override_update_without_relayout() {
    let mut doc = document(
        "<p id='p' style='color:red;text-shadow:24px 12px currentColor'><span id='span' style='color:blue'>HHH</span></p>",
        1.0,
    );
    let id = doc.get_element_by_id("span").unwrap();
    let rect = doc
        .get_client_bounding_rect(doc.get_element_by_id("p").unwrap())
        .unwrap();
    assert_same(
        &paint(&mut doc, 1.0),
        &image(
            "<p><span style='color:blue;text-shadow:24px 12px blue'>HHH</span></p>",
            1.0,
        ),
    );
    assert!(
        paint(&mut doc, 1.0) != image("<p><span style='color:blue'>HHH</span></p>", 1.0),
        "inherited shadow is missing"
    );
    doc.mutate().set_style_property(id, "color", "#16836a");
    doc.resolve(0.0);
    assert_same(
        &paint(&mut doc, 1.0),
        &image(
            "<p><span style='color:#16836a;text-shadow:24px 12px #16836a'>HHH</span></p>",
            1.0,
        ),
    );
    doc.mutate().set_style_property(id, "color", "blue");
    doc.mutate().set_style_property(id, "text-shadow", "none");
    doc.resolve(0.0);
    assert_same(
        &paint(&mut doc, 1.0),
        &image("<p><span style='color:blue'>HHH</span></p>", 1.0),
    );
    let after = doc
        .get_client_bounding_rect(doc.get_element_by_id("p").unwrap())
        .unwrap();
    assert_eq!(
        (rect.x, rect.y, rect.width, rect.height),
        (after.x, after.y, after.width, after.height)
    );
}

#[test]
fn nested_inherited_spans_do_not_duplicate_translucent_blurred_shadows() {
    let plain = image(
        "<p style='color:transparent;text-shadow:16px 6px 8px #ff000088'>HHHHHH</p>",
        1.0,
    );
    assert!(red_pixels(&plain) > 100);
    let nested = image(
        "<p style='color:transparent;text-shadow:16px 6px 8px #ff000088'>HH<span>HH<span>HH</span></span></p>",
        1.0,
    );
    assert_same(&nested, &plain);
}

#[test]
fn blur_softens_and_expands_shadow_at_both_dpis() {
    for scale in [1.0, 2.0] {
        let hard = image(
            "<p style='color:transparent;text-shadow:20px 10px red'>HHH</p>",
            scale,
        );
        let blurred = image(
            "<p style='color:transparent;text-shadow:20px 10px 8px red'>HHH</p>",
            scale,
        );
        assert!(red_pixels(&hard) > 100);
        assert!(
            red_pixels(&blurred) > red_pixels(&hard),
            "blur must spread beyond hard glyph edges at {scale}x"
        );
        assert!(
            blurred.chunks_exact(4).filter(|p| p[1] < 5).count()
                < hard.chunks_exact(4).filter(|p| p[1] < 5).count(),
            "blur must soften glyph cores"
        );
    }
}

#[test]
fn shadow_is_clipped_by_scrollport_and_transforms_with_text() {
    let actual = image(
        "<div style='margin:40px;width:90px;height:70px;overflow:hidden'><p style='margin:0;color:transparent;text-shadow:40px 10px red'>HHHH</p></div>",
        1.0,
    );
    assert!(red_pixels(&actual) > 20);
    for (i, p) in actual.chunks_exact(4).enumerate() {
        if i % 320 >= 130 {
            assert_eq!(p, [255, 255, 255, 255], "shadow escaped overflow clip");
        }
    }
    assert_same(
        &image(
            "<p style='transform:scale(1.25);color:transparent;text-shadow:20px 10px red'>HHH</p>",
            1.0,
        ),
        &image(
            "<p style='transform:scale(1.25) translate(20px,10px);color:red'>HHH</p>",
            1.0,
        ),
    );
}

#[test]
fn production_api_renders_shadows_with_no_resource_grants() {
    use makepad_html::{RenderOptions, ResourceMap, render_html};
    let resources = ResourceMap::default();
    let plain = render_html(
        "<p style='font:32px Arial;color:transparent'>HHH</p>",
        RenderOptions::default(),
        &resources,
    )
    .unwrap();
    let shadow = render_html(
        "<p style='font:32px Arial;color:transparent;text-shadow:10px 4px 3px red'>HHH</p>",
        RenderOptions::default(),
        &resources,
    )
    .unwrap();
    assert_eq!((plain.width, plain.height), (shadow.width, shadow.height));
    assert!(red_pixels(&shadow.rgba) > red_pixels(&plain.rgba) + 100);
}

#[test]
fn offscreen_text_can_cast_visible_shadow_through_ancestors() {
    let reference = image("<div><p style='color:red'>HHH</p></div>", 1.0);
    for offset in [-400, 400] {
        let actual = image(
            &format!(
                "<div style='transform:translateY({offset}px)'><p style='color:transparent;text-shadow:0 {}px red'>HHH</p></div>",
                -offset
            ),
            1.0,
        );
        assert_same(&actual, &reference);
    }
}
