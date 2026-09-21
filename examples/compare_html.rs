//! Diagnostic raw-engine comparison only. Does not change the product admission
//! policy: render_html still rejects script. Supply the reviewed, pinned fixture.
use anyrender::{PaintScene as _, render_to_buffer};
use anyrender_vello_cpu::VelloCpuImageRenderer;
use blitz_dom::{DocumentConfig, util::Color};
use blitz_html::HtmlDocument;
use blitz_paint::paint_scene;
use blitz_traits::{
    net::{Bytes, NetHandler, NetProvider, Request},
    shell::{ColorScheme, Viewport},
};
use makepad_html::{BLITZ_REVISION, RenderOptions, ResourceMap, render_html};
use peniko::{Fill, kurbo::Rect};
use std::{
    collections::BTreeMap,
    fs,
    path::PathBuf,
    sync::{Arc, Mutex},
};

#[derive(Default)]
struct SnapshotNetwork {
    resources: BTreeMap<String, Bytes>,
    requests: Mutex<Vec<serde_json::Value>>,
}
impl NetProvider for SnapshotNetwork {
    fn fetch(&self, _: usize, request: Request, handler: Box<dyn NetHandler>) {
        let url = request.url.to_string();
        let bytes = self.resources.get(&url).cloned();
        self.requests.lock().unwrap().push(serde_json::json!({
            "url": url, "served": bytes.is_some(), "bytes": bytes.as_ref().map_or(0, Bytes::len)
        }));
        handler.bytes(url, bytes.unwrap_or_default());
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    if !(7..=8).contains(&args.len()) {
        return Err(
            "usage: compare_html INPUT OUTPUT_DIR WIDTH HEIGHT SCALE LABEL [RESOURCE_MANIFEST]"
                .into(),
        );
    }
    let input = fs::read_to_string(&args[1])?;
    // This executable is a bounded lab probe, never the app's HTML entry point.
    if input.len() > 16_384 {
        return Err("comparison fixture too large".into());
    }
    let out = PathBuf::from(&args[2]);
    fs::create_dir_all(&out)?;
    let width: u32 = args[3].parse()?;
    let height: u32 = args[4].parse()?;
    let scale: u32 = args[5].parse()?;
    if !(64..=1600).contains(&width) || !(64..=1200).contains(&height) || !(1..=2).contains(&scale)
    {
        return Err("comparison viewport outside budget".into());
    }
    let label = &args[6];
    eprintln!("PHASE product_admission");
    let product_admission = match render_html(
        &input,
        RenderOptions {
            width_css: width,
            viewport_height_css: height,
            scale: scale as f32,
            ..Default::default()
        },
        &ResourceMap::default(),
    ) {
        Ok(_) => "accepted".to_string(),
        Err(error) => error.to_string(),
    };
    let manifest: serde_json::Value = if let Some(path) = args.get(7) {
        serde_json::from_slice(&fs::read(path)?)?
    } else {
        serde_json::json!({})
    };
    let mut network = SnapshotNetwork::default();
    if let Some(resources) = manifest["resources"].as_object() {
        if resources.len() > 32 {
            return Err("too many fixture resources".into());
        }
        for (url, path) in resources {
            let bytes = fs::read(path.as_str().ok_or("invalid resource path")?)?;
            if bytes.len() > 1_048_576 {
                return Err("fixture resource too large".into());
            }
            network.resources.insert(url.clone(), Bytes::from(bytes));
        }
    }
    let network = Arc::new(network);
    // Identical original HTML bytes; scripts are inert because no JS engine is
    // supplied. This intentionally bypasses ONLY the product's preflight check.
    eprintln!("PHASE raw_document");
    let mut document = HtmlDocument::from_html(
        &input,
        DocumentConfig {
            base_url: Some(
                manifest["base_url"]
                    .as_str()
                    .unwrap_or("https://comparison.invalid/")
                    .into(),
            ),
            net_provider: Some(network.clone()),
            viewport: Some(Viewport::new(
                width * scale,
                height * scale,
                scale as f32,
                ColorScheme::Light,
            )),
            ..Default::default()
        },
    );
    for _ in 0..8 {
        document.resolve(0.0);
    }
    if document.has_pending_critical_resources() {
        return Err("unsettled fixture resources".into());
    }
    let card = document
        .get_element_by_id("color")
        .and_then(|id| document.get_client_bounding_rect(id))
        .map(|r| serde_json::json!({"x":r.x,"y":r.y,"width":r.width,"height":r.height}));
    let root_height = document.root_element().final_layout().size.height;
    let mut elements = serde_json::Map::new();
    for selector in [
        "[data-probe]",
        "h1",
        "nav",
        "article",
        "article > p",
        "article > ul",
        "article > ol",
        "aside",
        "img",
        "button",
        "blockquote",
        "details",
        "pre",
        "section",
        "table",
        "form",
        "input",
        "textarea",
        "body > footer",
    ] {
        let rects: Vec<_> = document
            .query_selector_all(selector)
            .unwrap_or_default()
            .into_iter()
            .map(|id| {
                document
                    .get_client_bounding_rect(id)
                    .map(|r| serde_json::json!({"x":r.x,"y":r.y,"width":r.width,"height":r.height}))
            })
            .collect();
        elements.insert(selector.into(), serde_json::json!(rects));
    }
    let full_page = manifest["full_page"].as_bool().unwrap_or(false);
    let full_height = if full_page {
        (root_height.ceil() as u32).max(height)
    } else {
        height
    };
    let width_px = width * scale;
    let height_px = full_height * scale;
    if full_height > 8192 || u64::from(width_px) * u64::from(height_px) > 16_777_216 {
        return Err("full page exceeds diagnostic pixel budget".into());
    }
    eprintln!("PHASE paint");
    let rgba = render_to_buffer::<VelloCpuImageRenderer, _>(
        |scene| {
            scene.fill(
                Fill::NonZero,
                Default::default(),
                Color::WHITE,
                Default::default(),
                &Rect::new(0.0, 0.0, width_px as f64, height_px as f64),
            );
            paint_scene(
                scene,
                &mut document,
                scale as f64,
                width_px,
                height_px,
                0,
                0,
            );
        },
        width_px,
        height_px,
    );
    for (suffix, image_height) in [("", height * scale), ("-full", height_px)] {
        if suffix == "-full" && !full_page {
            continue;
        }
        let mut encoder = png::Encoder::new(
            fs::File::create(out.join(format!("blitz-{label}{suffix}.png")))?,
            width_px,
            image_height,
        );
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        encoder
            .write_header()?
            .write_image_data(&rgba[..width_px as usize * image_height as usize * 4])?;
    }
    let requests = network.requests.lock().unwrap().clone();
    let denied: Vec<_> = requests
        .iter()
        .filter(|r| r["served"] == false)
        .map(|r| r["url"].clone())
        .collect();
    // ImageFormat::can_read reports library knowledge, not compiled features.
    // Decode actual fixture bytes instead of treating that as a capability check.
    let decoded_images: Vec<_> = network.resources.iter().filter_map(|(url, bytes)| {
        let format = image::guess_format(bytes).ok()?;
        Some(match image::load_from_memory(bytes) {
            Ok(img) => serde_json::json!({"url":url,"format":format!("{format:?}"),"decoded":true,"width":img.width(),"height":img.height()}),
            Err(error) => serde_json::json!({"url":url,"format":format!("{format:?}"),"decoded":false,"error":error.to_string()}),
        })
    }).collect();
    let report = serde_json::json!({"engine":"Blitz raw HTML/CSS (no JS)","revision":BLITZ_REVISION,"local_patch":option_env!("MAKEPAD_HTML_PATCHSET").unwrap_or("wechat-css-1+table-2"),"width_css":width,"height_css":height,"scale":scale,"width_px":width_px,"height_px":height*scale,"full_height_px":height_px,"product_admission":product_admission,"card_rect_css":card,"denied_resources":denied,"resource_requests":requests,"elements":elements,"root_content_height_css":root_height,"image_decode_probes":decoded_images});
    fs::write(
        out.join(format!("blitz-{label}.json")),
        serde_json::to_vec_pretty(&report)?,
    )?;
    println!("{report}");
    Ok(())
}
