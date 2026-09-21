#!/usr/bin/env python3
"""Run offline-approved Blitz snapshots against real native WKWebView captures."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import mimetypes
import subprocess
import threading
import argparse
from PIL import Image

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
corpus=json.loads((ROOT/'corpus.json').read_text())
parser=argparse.ArgumentParser()
parser.add_argument('--only',help='Recheck one case, keeping other results')
parser.add_argument("--patched", action="store_true", help="Capture patched renderer without overwriting either baseline")
options=parser.parse_args()
results_path=ROOT/("run-results-patched.json" if options.patched else "run-results.json")
routes={f'/fixtures/{c["id"]}.html':ROOT/c['file'] for c in corpus['cases']}
routes.update({f'/assets/{p.name}':p for p in (ROOT/'assets').iterdir() if p.is_file()})
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=routes.get(self.path)
        data=path.read_bytes() if path else b''
        self.send_response(200 if path else 404)
        self.send_header('Content-Type',mimetypes.guess_type(self.path)[0] or 'application/octet-stream')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self'; script-src 'none'; form-action 'none'")
        self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}/'
results=json.loads(results_path.read_text()) if options.only and results_path.exists() else []
try:
    for case in corpus['cases']:
        if options.only and case['id']!=options.only:continue
        for width,height in corpus['viewports']:
            out=ROOT/'evidence'/case['id']/str(width)
            out.mkdir(parents=True,exist_ok=True)
            source=ROOT/case['file']
            assert hashlib.sha256(source.read_bytes()).hexdigest()==case['sha256']
            manifest={'base_url':base,'full_page':True,'resources':{base+k.lstrip('/'):str(v) for k,v in routes.items() if k.startswith('/assets/')}}
            manifest_path=out/('manifest-patched.json' if options.patched else 'manifest.json');manifest_path.write_text(json.dumps(manifest,indent=2))
            outcome={'case':case['id'],'width':width,'height':height,'source_sha256':case['sha256']}
            for variant in (['patched'] if options.patched else ['media','extended']):
                target=out if variant=='media' else out/variant
                target.mkdir(exist_ok=True)
                for old in target.glob('blitz-original*'):old.unlink()
                try:
                    with (target/'render.log').open('w') as log:
                        result=subprocess.run([str(REPO/f'target/html-corpus-{variant}'),str(source),str(target),str(width),str(height),'2','original',str(manifest_path)],stdout=log,stderr=subprocess.STDOUT,timeout=15)
                    outcome[variant]={'exit_code':result.returncode}
                except subprocess.TimeoutExpired:
                    phases=[line for line in (target/'render.log').read_text().splitlines() if line.startswith('PHASE ')]
                    outcome[variant]={'exit_code':None,'timeout_seconds':15,'last_phase':phases[-1] if phases else 'not instrumented'}
            existing=out/'webview-original.json'
            reuse=False
            if existing.exists():
                previous=json.loads(existing.read_text())
                reuse=previous['source_sha256']==case['sha256'] and previous['width_css']==width and previous['height_css']==height
            if reuse:
                outcome['webview']={'exit_code':0,'reused_identical_source_capture':True}
            else:
                with (out/'webview.log').open('w') as log:
                    result=subprocess.run([str(REPO/'target/html5-capture'),str(source),str(out),str(width),str(height),'2','original',base+f'fixtures/{case["id"]}.html','capture'],stdout=log,stderr=subprocess.STDOUT,timeout=70)
                outcome['webview']={'exit_code':result.returncode}
            if outcome['webview']['exit_code']==0:
                report=json.loads((out/'webview-original.json').read_text())
                assert report['source_sha256']==case['sha256']
                full=Image.new('RGB',(width*2,report['observation']['content_height_css']*2),'white')
                for tile in report['tiles']:
                    full.paste(Image.open(out/tile['file']).convert('RGB'),(0,tile['y_css']*2))
                full.save(out/'webview-original-full.png')
            results=[r for r in results if not(r['case']==case['id'] and r['width']==width)]
            results.append(outcome)
            results.sort(key=lambda r:(r['case'],r['width']))
            results_path.write_text(json.dumps(results,indent=2))
            print(json.dumps(outcome),flush=True)
finally:
    server.shutdown()
