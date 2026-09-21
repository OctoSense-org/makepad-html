use makepad_html::{DocumentSession, HtmlAction, RenderOptions, ResourceMap};
fn session(body: &str, scale: f32) -> DocumentSession {
    let html = format!(
        "<style>body{{margin:0;font:20px/30px sans-serif}}a,summary{{display:block;height:40px}}</style>{body}"
    );
    let mut doc = DocumentSession::new(
        &html,
        RenderOptions {
            scale,
            ..Default::default()
        },
        &ResourceMap::default(),
    )
    .unwrap();
    doc.render().unwrap();
    doc
}
#[test]
fn links_return_host_actions_and_unsafe_schemes_are_inert() {
    for scale in [1., 2.] {
        let mut doc = session(
            "<a href='https://example.com/article'><b>Open article</b></a><a href='javascript:alert(1)'>Inactive</a>",
            scale,
        );
        assert_eq!(
            doc.activate(30., 15.),
            HtmlAction::OpenLink {
                url: "https://example.com/article".into()
            }
        );
        assert_eq!(doc.activate(30., 55.), HtmlAction::None);
        for (x, y) in [(f32::NAN, 0.), (-1., 0.), (390., 0.), (0., 100000.)] {
            assert_eq!(doc.activate(x, y), HtmlAction::None);
        }
        assert_eq!(doc.render().unwrap().resources.requested, 0);
    }
}
#[test]
fn disclosure_retains_state_and_rerenders_from_same_document() {
    let mut doc = session(
        "<details><summary>Expand</summary><div style='height:120px;background:red'>Revealed content</div></details>",
        1.,
    );
    let closed = doc.render().unwrap();
    assert_eq!(doc.activate(50., 20.), HtmlAction::DocumentChanged);
    let opened = doc.render().unwrap();
    assert_eq!(opened.height, closed.height + 120);
    assert_eq!(doc.render().unwrap().rgba, opened.rgba);
    assert_eq!(doc.activate(50., 20.), HtmlAction::DocumentChanged);
    let again = doc.render().unwrap();
    assert!(
        again.rgba == closed.rgba,
        "collapse failed to restore original image"
    );
}
#[test]
fn fragment_requests_document_scroll_and_missing_targets_are_inert() {
    let mut doc = session(
        "<a href='#target'>Jump</a><div style='height:200px'></div><p id='target' style='margin:0'>Target</p>",
        2.,
    );
    assert_eq!(doc.activate(30., 15.), HtmlAction::ScrollTo { y_css: 240. });
    let mut missing = session("<a href='#missing'>Missing</a>", 1.);
    assert_eq!(missing.activate(30., 15.), HtmlAction::None);
}
#[test]
fn horizontal_overflow_scrolls_without_moving_document_viewport() {
    let mut doc = session(
        "<div style='width:200px;overflow-x:auto;white-space:nowrap'><a href='https://example.com/one' style='display:inline-block;width:200px'>First</a><a href='https://example.com/two' style='display:inline-block;width:200px'>Second</a></div>",
        1.,
    );
    assert_eq!(
        doc.activate(30., 15.),
        HtmlAction::OpenLink {
            url: "https://example.com/one".into()
        }
    );
    let before = doc.render().unwrap();
    assert!(doc.scroll_horizontal(30., 15., 200.));
    let after = doc.render().unwrap();
    assert!(before.rgba != after.rgba);
    assert_eq!(
        doc.activate(30., 15.),
        HtmlAction::OpenLink {
            url: "https://example.com/two".into()
        }
    );
    assert!(!doc.scroll_horizontal(f32::NAN, 15., 200.));
}

#[test]
fn ordinary_text_does_not_consume_horizontal_scroll() {
    let mut doc = session("<p>Plain text</p>", 1.);
    assert!(!doc.scroll_horizontal(10., 20., 200.));
}
