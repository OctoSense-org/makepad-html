#!/usr/bin/env python3
"""Pin upstream sources; execute real editor export without using the OS clipboard."""
from pathlib import Path
import base64
import hashlib
import json
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
REV = '3c69a5a106737f439fe30430b12e6f4b50de66b2'
CACHE = REPO / 'target/huasheng-export'
CACHE.mkdir(parents=True, exist_ok=True)
sources = {
    name: f'https://raw.githubusercontent.com/alchaincyf/huasheng_editor/{REV}/{name}'
    for name in ['app.js', 'styles.js', 'LICENSE']
}
sources.update({
    'vue.js': 'https://cdn.jsdelivr.net/npm/vue@3.4.15/dist/vue.global.prod.js',
    'markdown-it.js': 'https://cdn.jsdelivr.net/npm/markdown-it@14.0.0/dist/markdown-it.min.js',
})
provenance = []
for name, url in sources.items():
    path = CACHE / name
    if not path.exists():
        with urllib.request.urlopen(url, timeout=30) as response:
            path.write_bytes(response.read())
    provenance.append({'file': name, 'url': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
markdown = (ROOT / 'article.md').read_text()
resources = []
for ext, mime in [('png','png'), ('jpg','jpeg'), ('gif','gif'), ('webp','webp')]:
    src = REPO / f'lab/wechat-corpus/assets/chart.{ext}'
    data = src.read_bytes()
    uri = f'data:image/{mime};base64,' + base64.b64encode(data).decode()
    markdown = markdown.replace('ASSET_' + ext.upper(), uri)
    resources.append({'file': str(src.relative_to(REPO)), 'sha256': hashlib.sha256(data).hexdigest()})
(CACHE / 'article.md').write_text(markdown)
shutil.copy2(ROOT / 'export.js', CACHE / 'export.js')
(CACHE / 'editor.html').write_text('''<!doctype html><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src data:;">
<div id="app"></div><script src="vue.js"></script><script src="markdown-it.js"></script>
<script>
const create = Vue.createApp;
Vue.createApp = (...args) => {
  const app = create(...args), mount = app.mount;
  app.mount = (...args) => {const vm=mount(...args);window.testEditor=vm;return vm;};
  return app;
};
</script><script src="styles.js"></script><script src="app.js"></script>''')
subprocess.run(['swiftc', str(ROOT/'export.swift'), '-o', str(CACHE/'exporter')], check=True)
with (CACHE/'export.log').open('w') as log:
    subprocess.run([str(CACHE/'exporter'), str(CACHE), str(CACHE/'exports.json')], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=100)
export = json.loads((CACHE/'exports.json').read_text())
assert len(export['cases']) == 20
manifest = {k:v for k,v in export.items() if k != 'cases'}
manifest.update(revision=REV, upstream_sources=provenance, input_assets=resources,
    input_sha256=hashlib.sha256((ROOT/'article.md').read_bytes()).hexdigest(), cases=[])
for folder in ['fixtures','exports','previews']:
    (ROOT/folder).mkdir(exist_ok=True)
for case in export['cases']:
    cid = case['id']
    fragment = case.pop('exported')
    preview = case.pop('preview')
    (ROOT/f'exports/{cid}.html').write_text(fragment)
    (ROOT/f'previews/{cid}.html').write_text(preview)
    # Only the document shell is added; the exported body fragment is unchanged.
    html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+case['name']+'</title></head><body style="margin:0">'+fragment+'</body></html>'
    (ROOT/f'fixtures/{cid}.html').write_text(html)
    for stage in ['preview_inventory','export_inventory']:
        case[stage]['image_source_hashes'] = [hashlib.sha256(s.encode()).hexdigest() for s in case[stage].pop('image_sources')]
    case.update(file=f'fixtures/{cid}.html', sha256=hashlib.sha256(html.encode()).hexdigest(), bytes=len(html.encode()),
        exported_fragment_sha256=hashlib.sha256(fragment.encode()).hexdigest(), preview_sha256=hashlib.sha256(preview.encode()).hexdigest())
    manifest['cases'].append(case)
shutil.copy2(CACHE/'LICENSE', ROOT/'UPSTREAM-LICENSE')
(ROOT/'corpus.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
print(json.dumps({'exported_themes':len(manifest['cases']), 'max_html_bytes':max(c['bytes'] for c in manifest['cases']), 'method':manifest['method']}, ensure_ascii=False))
