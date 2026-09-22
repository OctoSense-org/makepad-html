#!/usr/bin/env python3
"""Capture the identical editor exports with the current Blitz and native WebKit."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
import argparse
import base64
import hashlib
import json
import re
import subprocess
import threading
import urllib.parse
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--only', help='Capture one theme, preserving the other results')
args = parser.parse_args()
corpus = json.loads((ROOT/'corpus.json').read_text())
binary = REPO/'target/html-corpus-patched'
wk_binary = REPO/'target/html5-capture'
FONT = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 23)
routes = {'/'+c['file']: ROOT/c['file'] for c in corpus['cases']}
requests = []

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = routes.get(self.path)
        data = path.read_bytes() if path else b''
        requests.append({'path':self.path,'status':200 if path else 404})
        self.send_response(200 if path else 404)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'none'; form-action 'none'")
        self.end_headers();self.wfile.write(data)
    def log_message(self,*_): pass

class EmbeddedResources(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.urls=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        src=attrs.get('src','')
        if src.startswith('data:'): self.urls.add(src)
        for match in re.finditer(r'''url\(\s*(["'])(data:.*?)\1\s*\)''',attrs.get('style','')):
            self.urls.add(match[2])

def call(command, log):
    try:
        with log.open('w') as f:
            p=subprocess.run([str(x) for x in command],stdout=f,stderr=subprocess.STDOUT,timeout=70)
        return {'exit_code':p.returncode}
    except subprocess.TimeoutExpired:
        return {'exit_code':None,'timeout_seconds':70}

def analyze(out,width,run):
    ref=None;img=None
    if run['webview']['exit_code']==0:
        wk=json.loads((out/'webview-original.json').read_text())
        assert wk['source_sha256']==run['source_sha256']
        ref=Image.new('RGB',(width*2,wk['observation']['content_height_css']*2),'white')
        for tile in wk['tiles']:
            ref.paste(Image.open(out/tile['file']).convert('RGB'),(0,tile['y_css']*2))
        ref.save(out/'webview-original-full.png')
        images=wk['observation']['images']
        run['webview_images']={'total':len(images),'decoded':sum(i['complete'] and i['naturalWidth']>0 for i in images)}
    if run['blitz']['exit_code']==0:
        b=json.loads((out/'blitz-original.json').read_text())
        img=Image.open(out/'blitz-original-full.png').convert('RGB')
        run['production_admission']=b['product_admission']
        run['denied_resources']=b['denied_resources']
        run['image_decode_probes']=b['image_decode_probes']
    if img is not None and ref is not None:
        height=max(img.height,ref.height)
        a=Image.new('RGB',(width*2,height),'white');a.paste(img,(0,0))
        z=Image.new('RGB',(width*2,height),'white');z.paste(ref,(0,0))
        aa=np.asarray(a).astype(np.int16);zz=np.asarray(z).astype(np.int16)
        ink=(np.max(255-aa,axis=2)>12)|(np.max(255-zz,axis=2)>12)
        diff=np.max(np.abs(aa-zz),axis=2)>24
        geometries={}
        for sel in ['h1','img','blockquote','pre','table']:
            lhs=b['elements'][sel];rhs=wk['observation']['elements'][sel]
            deltas=[max(abs(x[k]-y[k]) for k in ['x','y','width','height']) for x,y in zip(lhs,rhs) if x and y]
            geometries[sel]={'counts':[len(lhs),len(rhs)],'max_delta_css':round(max(deltas),3) if deltas else None}
        run['metrics']={'content_pixels_differing_over_24_rgb_pct':round(float((diff&ink).sum()/max(1,ink.sum())*100),3),
            'content_union_pixels':int(ink.sum()),'height_css':[img.height/2,ref.height/2],'geometry':geometries}
        Image.fromarray(np.clip(np.abs(aa-zz)*3,0,255).astype(np.uint8)).save(out/'diff.png')
    if ref is None: ref=Image.new('RGB',(width*2,1400),'#f8dddd');ImageDraw.Draw(ref).text((20,40),'WKWebView failed',font=FONT,fill='black')
    if img is None: img=Image.new('RGB',(width*2,1400),'#f8dddd');ImageDraw.Draw(img).text((20,40),'Blitz failed; see log',font=FONT,fill='black')
    pair=Image.new('RGB',(width*4+24,max(img.height,ref.height)+50),'#e8edf1')
    d=ImageDraw.Draw(pair);d.text((12,12),'Blitz / current patches',font=FONT,fill='#172333');d.text((width*2+36,12),'macOS WKWebView',font=FONT,fill='#172333')
    pair.paste(img,(0,50));pair.paste(ref,(width*2+24,50));pair.save(out/'pair.png')
    run['evidence_sha256']={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['pair.png','blitz-original-full.png','webview-original-full.png'] if (out/name).exists()}

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}/'
result_path=ROOT/'results.json'
results=json.loads(result_path.read_text())['results'] if args.only and result_path.exists() else []
try:
    with ThreadPoolExecutor(max_workers=2) as pool:
        for case in corpus['cases']:
            if args.only and case['id']!=args.only:continue
            source=ROOT/case['file'];html=source.read_text()
            assert hashlib.sha256(source.read_bytes()).hexdigest()==case['sha256']
            resources=EmbeddedResources();resources.feed(html)
            resource_dir=REPO/'target/huasheng-embedded';resource_dir.mkdir(exist_ok=True)
            manifest_resources={}
            for uri in resources.urls:
                header,encoded=uri.split(',',1)
                data=base64.b64decode(encoded) if ';base64' in header else urllib.parse.unquote_to_bytes(encoded)
                path=resource_dir/hashlib.sha256(data).hexdigest();path.write_bytes(data)
                manifest_resources[uri]=str(path)
            for width in [390,600]:
                out=ROOT/'evidence'/case['id']/str(width);out.mkdir(parents=True,exist_ok=True)
                for old in out.glob('blitz-original*'):old.unlink()
                for old in out.glob('webview-original*'):old.unlink()
                manifest=out/'resources.json';manifest.write_text(json.dumps({'base_url':base,'full_page':True,'resources':manifest_resources}))
                run={'case':case['id'],'name':case['name'],'width':width,'height':700,'scale':2,'source_sha256':case['sha256']}
                bf=pool.submit(call,[binary,source,out,width,700,2,'original',manifest],out/'blitz.log')
                wf=pool.submit(call,[wk_binary,source,out,width,700,2,'original',base+case['file'],'capture'],out/'webview.log')
                run['blitz']=bf.result();run['webview']=wf.result()
                analyze(out,width,run)
                results=[r for r in results if (r['case'],r['width'])!=(case['id'],width)]+[run]
                report={'revision':corpus['revision'],'blitz_binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'method':'Identical editor-export HTML bytes and embedded resource bytes. Native macOS WKWebView, page JS disabled, 2x DPI. Original theme fonts retained. No image registration or alignment.',
                    'scope':'Editor export compatibility; authored input article. Not published WeChat pages or iOS/Android certification. GIF captures check a static frame only.',
                    'metric_limits':'Content pixel difference is not similarity or a 9/10 score; includes font and layout differences.',
                    'http_requests':requests,'results':results}
                result_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
                print(json.dumps({k:run[k] for k in ['case','width','blitz','webview','webview_images','metrics'] if k in run},ensure_ascii=False),flush=True)
finally:server.shutdown()
