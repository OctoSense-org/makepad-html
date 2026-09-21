//! Optional native texture adapter. The host computes [`RenderedDocument`] on a
//! worker, rejects stale results using its own document/session generation, then uploads on the UI thread.
//! Activations are emitted in document CSS coordinates for a worker-owned
//! `DocumentSession`. Text selection, accessibility text and editing are not yet provided.
use crate::RenderedDocument;
use makepad_widgets::*;

script_mod! {
    use mod.prelude.widgets.*
    mod.widgets.HtmlView = #(HtmlView::register_widget(vm)) {
        ..mod.widgets.View
        width: Fill height: Fill flow: Down clip_x: true clip_y: true
        viewport := ScrollYView {
            width: Fill height: Fill flow: Down clip_x: true clip_y: true
            document_bitmap := Image {width: Fill height: Fit fit: ImageFit.Horizontal}
        }
    }
}

#[derive(Clone, Debug, Default)]
pub enum HtmlViewAction {
    #[default]
    None,
    Activate {
        x_css: f32,
        y_css: f32,
    },
    ScrollHorizontal {
        x_css: f32,
        y_css: f32,
        delta_css: f32,
    },
}

#[derive(Script, ScriptHook, Widget)]
pub struct HtmlView {
    #[source]
    source: ScriptObjectRef,
    #[deref]
    view: View,
    #[rust]
    width_css: f64,
}
impl Widget for HtmlView {
    fn handle_event(&mut self, cx: &mut Cx, event: &Event, scope: &mut Scope) {
        self.view.handle_event(cx, event, scope);
        let area = self.view.image(cx, ids!(document_bitmap)).area();
        // Share capture with the scroll view; only a stationary primary tap activates.
        let hit = event.hits_with_capture_overload(cx, area, true);
        if let Hit::FingerScroll(fe) = &hit {
            if fe.scroll.x != 0.0 && self.width_css > 0.0 {
                let rect = area.rect(cx);
                let factor = self.width_css / rect.size.x.max(1.0);
                cx.widget_action(
                    self.widget_uid(),
                    HtmlViewAction::ScrollHorizontal {
                        x_css: ((fe.abs.x - rect.pos.x) * factor) as f32,
                        y_css: ((fe.abs.y - rect.pos.y) * factor) as f32,
                        delta_css: (fe.scroll.x * factor) as f32,
                    },
                );
            }
        }
        if let Hit::FingerUp(fe) = hit {
            if fe.is_over && fe.was_tap() && fe.is_primary_hit() && self.width_css > 0.0 {
                let rect = area.rect(cx);
                if rect.size.x > 0.0 {
                    let factor = self.width_css / rect.size.x;
                    cx.widget_action(
                        self.widget_uid(),
                        HtmlViewAction::Activate {
                            x_css: ((fe.abs.x - rect.pos.x) * factor) as f32,
                            y_css: ((fe.abs.y - rect.pos.y) * factor) as f32,
                        },
                    );
                }
            }
        }
    }
    fn draw_walk(&mut self, cx: &mut Cx2d, scope: &mut Scope, walk: Walk) -> DrawStep {
        self.view.draw_walk(cx, scope, walk)
    }
}
impl HtmlView {
    pub fn set_rendered(&mut self, cx: &mut Cx, rendered: &RenderedDocument) {
        self.width_css = f64::from(rendered.width) / f64::from(rendered.scale);
        let texture = Texture::new_with_format(
            cx,
            TextureFormat::VecBGRAu8_32 {
                width: rendered.width as usize,
                height: rendered.height as usize,
                data: Some(rendered.to_bgra_u32()),
                updated: TextureUpdated::Full,
            },
        );
        self.view
            .image(cx, ids!(document_bitmap))
            .set_texture(cx, Some(texture));
        self.view.redraw(cx);
    }
    pub fn scroll_to(&mut self, cx: &mut Cx, y_css: f32) {
        let area = self.view.image(cx, ids!(document_bitmap)).area();
        let factor = area.rect(cx).size.x / self.width_css.max(1.0);
        self.view
            .view(cx, ids!(viewport))
            .set_scroll_pos(cx, dvec2(0., f64::from(y_css) * factor));
        self.view.redraw(cx);
    }
    pub fn clear(&mut self, cx: &mut Cx) {
        self.width_css = 0.0;
        self.view
            .image(cx, ids!(document_bitmap))
            .set_texture(cx, None);
        self.view.redraw(cx);
    }
}
impl HtmlViewRef {
    pub fn scroll_to(&self, cx: &mut Cx, y_css: f32) {
        if let Some(mut inner) = self.borrow_mut() {
            inner.scroll_to(cx, y_css);
        }
    }
    pub fn horizontal_scroll(&self, actions: &Actions) -> Option<(f32, f32, f32)> {
        actions
            .filter_widget_actions_cast::<HtmlViewAction>(self.widget_uid())
            .find_map(|action| match action {
                HtmlViewAction::ScrollHorizontal {
                    x_css,
                    y_css,
                    delta_css,
                } => Some((x_css, y_css, delta_css)),
                _ => None,
            })
    }
    pub fn activation(&self, actions: &Actions) -> Option<(f32, f32)> {
        actions
            .filter_widget_actions_cast::<HtmlViewAction>(self.widget_uid())
            .find_map(|action| match action {
                HtmlViewAction::Activate { x_css, y_css } => Some((x_css, y_css)),
                _ => None,
            })
    }

    pub fn set_rendered(&self, cx: &mut Cx, rendered: &RenderedDocument) {
        if let Some(mut inner) = self.borrow_mut() {
            inner.set_rendered(cx, rendered);
        }
    }
    pub fn clear(&self, cx: &mut Cx) {
        if let Some(mut inner) = self.borrow_mut() {
            inner.clear(cx);
        }
    }
}
