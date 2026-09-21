//! Persistent offline document state. Construct and keep this on one worker.
use crate::{
    MemoryProvider, RenderError, RenderOptions, RenderedDocument, ResourceMap, create_document,
    paint_document,
};
use blitz_html::HtmlDocument;
use html5ever::local_name;
use std::sync::Arc;

/// A host-visible action. Links are never opened or fetched by this library.
#[derive(Clone, Debug, Default, PartialEq)]
pub enum HtmlAction {
    #[default]
    None,
    OpenLink {
        url: String,
    },
    ScrollTo {
        y_css: f32,
    },
    DocumentChanged,
}

/// A persistent DOM with the same immutable resource grants and budgets as
/// `render_html`. This is worker-owned; send events to it rather than moving it
/// across threads. Coordinates are CSS pixels relative to the document bitmap.
pub struct DocumentSession {
    document: HtmlDocument,
    provider: Arc<MemoryProvider>,
    options: RenderOptions,
    width: u32,
    max_height: u32,
    rendered_height: f32,
}
impl DocumentSession {
    pub fn new(
        html: &str,
        options: RenderOptions,
        resources: &ResourceMap,
    ) -> Result<Self, RenderError> {
        let (document, provider, width, max_height) = create_document(html, options, resources)?;
        Ok(Self {
            document,
            provider,
            options,
            width,
            max_height,
            rendered_height: 0.0,
        })
    }
    pub fn render(&mut self) -> Result<RenderedDocument, RenderError> {
        self.rendered_height = 0.0;
        let rendered = paint_document(
            &mut self.document,
            &self.provider,
            self.options,
            self.width,
            self.max_height,
        )?;
        self.rendered_height = rendered.height as f32 / self.options.scale;
        Ok(rendered)
    }
    fn valid_point(&self, x: f32, y: f32) -> bool {
        x.is_finite()
            && y.is_finite()
            && x >= 0.0
            && y >= 0.0
            && x < self.options.width_css as f32
            && y < self.rendered_height
    }
    /// Scroll the nearest horizontal overflow container. The host owns document
    /// scrolling; any overflow reaching Blitz's viewport is discarded.
    pub fn scroll_horizontal(&mut self, x: f32, y: f32, delta_css: f32) -> bool {
        if !self.valid_point(x, y) || !delta_css.is_finite() {
            return false;
        }
        let Some(hit) = self.document.hit(x, y) else {
            return false;
        };
        let mut ancestors = Vec::new();
        let mut current = Some(hit.node_id);
        while let Some(id) = current {
            let node = self.document.get_node(id).unwrap();
            ancestors.push((id, node.scroll_offset().x));
            current = node.layout_parent.get();
        }
        let viewport = self.document.viewport_scroll();
        self.document
            .scroll_node_by_has_changed(hit.node_id, -f64::from(delta_css), 0.0, |_| {});
        self.document.set_viewport_scroll(viewport);
        ancestors
            .iter()
            .any(|(id, before)| self.document.get_node(*id).unwrap().scroll_offset().x != *before)
    }

    /// Activate a link or the first summary of a details disclosure. Non-HTTP
    /// schemes are inert. A fragment returns a host scroll request.
    pub fn activate(&mut self, x: f32, y: f32) -> HtmlAction {
        if !self.valid_point(x, y) {
            return HtmlAction::None;
        }
        let Some(hit) = self.document.hit(x, y) else {
            return HtmlAction::None;
        };
        let mut current = Some(hit.node_id);
        while let Some(id) = current {
            let Some(node) = self.document.get_node(id) else {
                break;
            };
            current = node.parent;
            let Some(element) = node.element_data() else {
                continue;
            };
            if element.name.local == local_name!("a") {
                let Some(href) = element.attr(local_name!("href")) else {
                    continue;
                };
                if let Some(fragment) = href.strip_prefix('#') {
                    let target = if fragment.is_empty() {
                        Some(0.0)
                    } else {
                        self.document
                            .get_element_by_id(fragment)
                            .and_then(|id| self.document.get_client_bounding_rect(id))
                            .map(|r| r.y as f32)
                    };
                    return target
                        .map(|y_css| HtmlAction::ScrollTo { y_css })
                        .unwrap_or_default();
                }
                if let Ok(url) = self.document.base_url().join(href) {
                    if matches!(url.scheme(), "http" | "https") {
                        return HtmlAction::OpenLink {
                            url: url.to_string(),
                        };
                    }
                }
                return HtmlAction::None;
            }
            if element.name.local == local_name!("summary") {
                if let Some(parent) = current {
                    let details = self.document.get_node(parent).unwrap();
                    let first = details.children.iter().find(|child| {
                        self.document
                            .get_node(**child)
                            .and_then(|n| n.element_data())
                            .is_some_and(|e| e.name.local == local_name!("summary"))
                    });
                    if details
                        .element_data()
                        .is_some_and(|e| e.name.local == local_name!("details"))
                        && first == Some(&id)
                    {
                        self.document.toggle_details_open(parent);
                        return HtmlAction::DocumentChanged;
                    }
                }
            }
        }
        HtmlAction::None
    }
}
