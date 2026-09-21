#!/usr/bin/env python3
"""Render the pasted fixture and keep a real two-pane macOS window open.

Only reviewed fixture files are served, on an ephemeral loopback port.
The original page bytes and assets are unchanged; page scripts are disabled.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import hashlib
import json
import os
import re
import subprocess
import threading
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--media", action="store_true", help="Use a renderer built with blitz-dom/woff,image/gif")
options = parser.parse_args()

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT / "inputs/html5-user.html"
ASSETS = ROOT / "inputs/html5-assets"
OUTPUT = ROOT / "evidence" / ("html5-media" if options.media else "html5-user")
OUTPUT.mkdir(parents=True, exist_ok=True)
routes = {"/index.html": (SOURCE, "text/html; charset=utf-8")}
for local, remote, mime in [
    ("stylesheet.css", "/assets/css/stylesheet.css?v=1", "text/css"),
    ("scripts.js", "/assets/js/scripts.js", "application/javascript"),
    ("Neris-Light-webfont.woff", "/assets/fonts/Neris-Light-webfont.woff", "font/woff"),
    ("Neris-Thin-webfont.woff", "/assets/fonts/Neris-Thin-webfont.woff", "font/woff"),
    ("Neris-SemiBold-webfont.woff", "/assets/fonts/Neris-SemiBold-webfont.woff", "font/woff"),
]:
    routes[remote] = (ASSETS / local, mime)
requests = []

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        entry = routes.get(self.path)
        status = 200 if entry else 404
        data = entry[0].read_bytes() if entry else b""
        self.send_response(status)
        self.send_header("Content-Type", entry[1] if entry else "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; script-src 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(data)
        requests.append({"path": self.path, "status": status, "bytes": len(data)})
        (OUTPUT / "webview-requests.json").write_text(json.dumps(requests, indent=2))

    def log_message(self, fmt, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_port}/"
resources = {base + remote.lstrip("/"): str(entry[0]) for remote, entry in routes.items()}
html = SOURCE.read_text()
for index, url in enumerate(re.findall(r'src="(data:image/gif;base64,[^"]+)"', html)):
    path = ASSETS / f"inline-{index}.gif"
    path.write_bytes(base64.b64decode(url.split(",", 1)[1], validate=True))
    resources[url] = str(path)
manifest = {"base_url": base, "resources": resources, "full_page": True}
manifest_path = OUTPUT / "resource-manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2))
provenance = {
    "source": "Exact HTML pasted by the user; no source transformation",
    "source_path": str(SOURCE), "source_bytes": SOURCE.stat().st_size,
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "resource_origin_confirmed_by_user": "https://html5example.com/",
    "resource_snapshot": [{"original_url": "https://html5example.com" + remote,
                           "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                          for remote, (path, _) in routes.items() if remote != "/index.html"],
    "page_scripts_enabled": False,
    "reason": "Compare static HTML/CSS; original site script contains analytics and landing-page-only copy button code.",
    "missing_origin_images": ["/assets/images/image.png", "/assets/images/image2.png", "/assets/images/image.webp"],
    "blitz_configuration": "Diagnostic build with blitz-dom/woff,image/gif; production admission unchanged." if options.media else "Current makepad-html default features; WOFF and GIF decoders not enabled.",
}
(OUTPUT / "source.json").write_text(json.dumps(provenance, indent=2))
binary = Path(os.environ.get("CARGO_TARGET_DIR", REPO / "target")) / "debug/examples/compare_html"
args = [str(SOURCE), str(OUTPUT), "600", "600", "2", "original"]
with (OUTPUT / "blitz.log").open("w") as log:
    subprocess.run([str(binary), *args, str(manifest_path)], check=True, stdout=log, stderr=subprocess.STDOUT)
print(f"BLITZ_READY input={SOURCE} sha256={provenance['source_sha256']}", flush=True)
try:
    subprocess.run([str(REPO / "target/html5-comparison"), *args, base + "index.html"], check=True)
finally:
    server.shutdown()
