//! Standalone native HTML viewer. No editor, login, Matrix, or OctoSense runtime.
use ::makepad_html::{
    self as html_renderer, RenderOptions, RenderedDocument, makepad::HtmlViewWidgetRefExt,
    render_html,
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
enum ViewerAction {
    Rendered(Result<Arc<RenderedDocument>, String>),
}
#[derive(Script, ScriptHook)]
pub struct App {
    #[live]
    ui: WidgetRef,
}
impl MatchEvent for App {
    fn handle_startup(&mut self, _cx: &mut Cx) {
        let args = std::env::args().skip(1).collect();
        std::thread::spawn(move || {
            let result = support::load(args).and_then(|(html, resources)| {
                render_html(
                    &html,
                    RenderOptions {
                        width_css: 440,
                        scale: 2.0,
                        ..Default::default()
                    },
                    &resources,
                )
                .map(Arc::new)
                .map_err(|e| e.to_string())
            });
            Cx::post_action(ViewerAction::Rendered(result));
        });
    }
    fn handle_actions(&mut self, cx: &mut Cx, actions: &Actions) {
        for action in actions {
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
