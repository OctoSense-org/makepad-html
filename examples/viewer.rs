//! Standalone native HTML viewer. No editor, login, Matrix, or OctoSense runtime.
use ::makepad_html::{
    self as html_renderer, DocumentSession, HtmlAction, RenderOptions, RenderedDocument,
    makepad::HtmlViewWidgetRefExt,
};
pub use makepad_widgets;
use makepad_widgets::*;
use std::sync::Arc;
mod support;

app_main!(App);
script_mod! {
    use mod.prelude.widgets.*
    use mod.widgets.*
    startup() do #(App::script_component(vm)) {
        ui: Root {
            main_window := Window {
                window.inner_size: vec2(440, 880)
                body +: {
                    flow: Down
                    title := Label {width: Fill height: 44 padding: 12 text: "Makepad HTML"}
                    document := HtmlView {width: Fill height: Fill}
                    status := Label {width: Fill height: 44 text: "Rendering…"}
                }
            }
        }
    }
}
#[derive(Clone, Debug)]
enum ViewerInput {
    Activate(f32, f32),
    Scroll(f32, f32, f32),
}
#[derive(Clone, Debug)]
enum ViewerAction {
    Rendered(Result<Arc<RenderedDocument>, String>),
    Interaction(HtmlAction),
}
#[derive(Script, ScriptHook)]
pub struct App {
    #[live]
    ui: WidgetRef,
    #[rust]
    events: Option<std::sync::mpsc::Sender<ViewerInput>>,
}
impl MatchEvent for App {
    fn handle_startup(&mut self, _cx: &mut Cx) {
        let args = std::env::args().skip(1).collect();
        let (sender, receiver) = std::sync::mpsc::channel();
        self.events = Some(sender);
        std::thread::spawn(move || {
            let result = support::load(args).and_then(|(html, resources)| {
                DocumentSession::new(
                    &html,
                    RenderOptions {
                        width_css: 440,
                        scale: 2.0,
                        ..Default::default()
                    },
                    &resources,
                )
                .map_err(|e| e.to_string())
            });
            let mut session = match result {
                Ok(session) => session,
                Err(error) => {
                    Cx::post_action(ViewerAction::Rendered(Err(error)));
                    return;
                }
            };
            Cx::post_action(ViewerAction::Rendered(
                session.render().map(Arc::new).map_err(|e| e.to_string()),
            ));
            while let Ok(input) = receiver.recv() {
                let action = match input {
                    ViewerInput::Activate(x, y) => session.activate(x, y),
                    ViewerInput::Scroll(x, y, delta) => {
                        if session.scroll_horizontal(x, y, delta) {
                            HtmlAction::DocumentChanged
                        } else {
                            HtmlAction::None
                        }
                    }
                };
                if action == HtmlAction::DocumentChanged {
                    Cx::post_action(ViewerAction::Rendered(
                        session.render().map(Arc::new).map_err(|e| e.to_string()),
                    ));
                } else {
                    Cx::post_action(ViewerAction::Interaction(action));
                }
            }
        });
    }

    fn handle_actions(&mut self, cx: &mut Cx, actions: &Actions) {
        if let Some(point) = self.ui.html_view(cx, ids!(document)).activation(actions) {
            if let Some(sender) = &self.events {
                let _ = sender.send(ViewerInput::Activate(point.0, point.1));
            }
        }
        if let Some((x, y, delta)) = self
            .ui
            .html_view(cx, ids!(document))
            .horizontal_scroll(actions)
        {
            if let Some(sender) = &self.events {
                let _ = sender.send(ViewerInput::Scroll(x, y, delta));
            }
        }
        for action in actions {
            if let Some(ViewerAction::Interaction(action)) = action.downcast_ref::<ViewerAction>() {
                match action {
                    HtmlAction::OpenLink { url } => {
                        eprintln!("LINK_REQUEST {url}");
                        self.ui
                            .label(cx, ids!(status))
                            .set_text(cx, &format!("Link requested: {url}"));
                    }
                    HtmlAction::ScrollTo { y_css } => {
                        self.ui.html_view(cx, ids!(document)).scroll_to(cx, *y_css)
                    }
                    _ => {}
                }
            }
            if let Some(ViewerAction::Rendered(result)) = action.downcast_ref::<ViewerAction>() {
                match result {
                    Ok(bitmap) => {
                        self.ui
                            .html_view(cx, ids!(document))
                            .set_rendered(cx, bitmap);
                        self.ui.label(cx, ids!(status)).set_text(
                            cx,
                            if bitmap.clipped {
                                "Ready · Document exceeds preview limit"
                            } else {
                                "Ready · Offline HTML/CSS"
                            },
                        );
                    }
                    Err(error) => {
                        eprintln!("HTML render failed: {error}");
                        self.ui
                            .label(cx, ids!(status))
                            .set_text(cx, &format!("Unable to render: {error}"));
                    }
                }
            }
        }
    }
}
impl AppMain for App {
    fn script_mod(vm: &mut ScriptVm) -> ScriptValue {
        makepad_widgets::script_mod(vm);
        html_renderer::makepad::script_mod(vm);
        self::script_mod(vm)
    }
    fn handle_event(&mut self, cx: &mut Cx, event: &Event) {
        self.match_event(cx, event);
        self.ui.handle_event(cx, event, &mut Scope::empty());
    }
}
