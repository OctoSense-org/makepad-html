use makepad_html::{MAX_HTML_BYTES, MAX_RESOURCE_BYTES, ResourceMap};
use std::{fs::File, io::Read, path::Path};

fn read_bounded(path: &Path, limit: usize) -> Result<Vec<u8>, String> {
    let mut bytes = Vec::new();
    File::open(path)
        .map_err(|e| format!("{}: {e}", path.display()))?
        .take(limit as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > limit {
        return Err(format!("{} exceeds the input budget", path.display()));
    }
    Ok(bytes)
}

/// File access belongs to this local demo host, never to the rendered document.
/// Usage: viewer [page.html [theme.css=/path/theme.css logo.png=/path/logo.png]]
pub fn load(args: Vec<String>) -> Result<(String, ResourceMap), String> {
    let mut resources = ResourceMap::default();
    let Some(input) = args.first() else {
        resources
            .insert_css(
                "article.css",
                include_str!("../../tests/fixtures/article.css"),
            )
            .map_err(|e| e.to_string())?;
        resources
            .insert_image(
                "cover.png",
                include_bytes!("../../tests/fixtures/cover.png").to_vec(),
            )
            .map_err(|e| e.to_string())?;
        return Ok((
            include_str!("../../tests/fixtures/article.html").into(),
            resources,
        ));
    };
    let html = String::from_utf8(read_bounded(Path::new(input), MAX_HTML_BYTES)?)
        .map_err(|e| e.to_string())?;
    for grant in &args[1..] {
        let (id, path) = grant
            .split_once('=')
            .ok_or("Resource arguments must be ID=PATH")?;
        if id.ends_with(".css") {
            let css = String::from_utf8(read_bounded(Path::new(path), 64 * 1024)?)
                .map_err(|e| e.to_string())?;
            resources.insert_css(id, &css).map_err(|e| e.to_string())?;
        } else {
            resources
                .insert_image(id, read_bounded(Path::new(path), MAX_RESOURCE_BYTES)?)
                .map_err(|e| e.to_string())?;
        }
    }
    Ok((html, resources))
}
