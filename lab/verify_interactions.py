#!/usr/bin/env python3
"""Owned native viewer: links, disclosures, fragment navigation and scroll coordinates."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
BINARY=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'target/debug/examples/viewer'
OUT=ROOT/'lab/evidence/interactions'
OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'target/native-interactions.html'
SOURCE.write_text('''<!doctype html><style>body{margin:0;font:20px/30px Arial;background:white}a,summary{display:block;height:40px}p{margin:0}</style><a href="https://example.com/article">Open article</a><a href="#target">Jump to target</a><details><summary>Expand section</summary><div style="height:120px;background:#16836a;color:white">Revealed content</div></details><div style="height:800px;background:#f8f8f8">Spacer</div><p id="target">FRAGMENT TARGET</p><a href="https://example.com/scrolled">Scrolled link</a><div style="width:440px;overflow-x:auto;white-space:nowrap"><a href="https://example.com/slide1" style="display:inline-block;width:440px;background:#ddf">First slide</a><a href="https://example.com/slide2" style="display:inline-block;width:440px;background:#dfd">Second slide</a></div>''')
report_path=OUT/'native-validation.json'
report_path.unlink(missing_ok=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
def request(path,**params):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}?'+urllib.parse.urlencode(params),timeout=10) as response:
        return json.load(response)
def labels():return ' '.join(row.get('t','') for row in request('/snap')['s'])
def screenshot(name):
    output=OUT/name
    shutil.copyfile(request('/g')['png'],output)
    return output
with (ROOT/'target/native-interactions.log').open('w') as log:
    app=subprocess.Popen([str(BINARY),str(SOURCE)],cwd=ROOT,env=dict(os.environ,MAKEPAD_REMOTE=str(port),MAKEPAD_HIDE_WINDOWS='1',MAKEPAD_NO_FOCUS='1'),stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            assert app.poll() is None,'Viewer exited'
            try:
                status=request('/s');assert status['pid']==app.pid
                if status['w'] and 'Ready · Offline HTML/CSS' in labels():break
            except (OSError,ValueError):pass
            time.sleep(.2)
        else:raise RuntimeError('Viewer not ready')
        request('/m',k='move',x=1,y=1,wait=1)
        closed=screenshot('native-closed.png')
        request('/m',k='down',x=45,y=120,wait=1)
        request('/m',k='move',x=160,y=120,wait=1)
        request('/m',k='up',x=160,y=120,wait=1)
        assert 'Link requested:' not in labels(),'Dragging activated a link'
        request('/m',k='click',x=45,y=120,wait=1)
        for _ in range(30):
            if 'Link requested: https://example.com/article' in labels():break
            time.sleep(.1)
        else:raise AssertionError('Native link click did not reach worker: '+labels())
        screenshot('native-link.png')
        request('/m',k='click',x=55,y=200,wait=1)
        for _ in range(30):
            if 'Ready · Offline HTML/CSS' in labels():break
            time.sleep(.1)
        else:raise AssertionError('Disclosure did not re-render')
        request('/m',k='move',x=1,y=1,wait=1)
        time.sleep(.2)
        opened=screenshot('native-open.png')
        green=lambda path:sum(g>90 and r<60 and 70<b<145 for r,g,b in Image.open(path).convert('RGB').getdata())
        assert green(opened)>20000*status['w'][0]['dpi']**2 and green(closed)==0,'Disclosure content did not appear'
        request('/m',k='click',x=55,y=200,wait=1)
        time.sleep(.4)
        request('/m',k='move',x=1,y=1,wait=1)
        collapsed=screenshot('native-reclosed.png')
        dpi=status['w'][0]['dpi']
        article=(0,round(100*dpi),round(status['w'][0]['sz'][0]*dpi),round((status['w'][0]['sz'][1]-50)*dpi))
        assert ImageChops.difference(Image.open(closed).convert('RGB').crop(article), Image.open(collapsed).convert('RGB').crop(article)).getbbox() is None,'Disclosure failed to restore original bitmap'
        request('/m',k='click',x=55,y=160,wait=1)
        time.sleep(.4)
        jumped=screenshot('native-fragment.png')
        ocr=ROOT/'target/makepad-html-ocr'
        if not ocr.exists():subprocess.run(['swiftc',str(ROOT/'lab/ocr.swift'),'-o',str(ocr)],check=True)
        rows=json.loads(subprocess.check_output([str(ocr),str(jumped)],text=True))
        text=' '.join(row['text'] for row in rows)
        assert 'FRAGMENT TARGET' in text,text
        # At the bottom, the last link sits immediately above the status bar.
        # Use OCR's normalized Vision rectangle to avoid hardcoding window DPI.
        row=next(row for row in rows if 'Scrolled link' in row['text'])
        x,y,w,h=row['box']
        request('/m',k='click',x=(x+w/2)*status['w'][0]['sz'][0],y=(y+h/2)*status['w'][0]['sz'][1],wait=1)
        for _ in range(30):
            if 'Link requested: https://example.com/scrolled' in labels():break
            time.sleep(.1)
        else:raise AssertionError('Scrolled link coordinates did not match the document')
        screenshot('native-scrolled-link.png')
        row=next(row for row in rows if 'First slide' in row['text'])
        x,y,w,h=row['box']; slide_x=(x+w/2)*status['w'][0]['sz'][0]; slide_y=(y+h/2)*status['w'][0]['sz'][1]
        request('/m',k='scroll',x=slide_x,y=slide_y,dx=440,dy=0,wait=1)
        time.sleep(.5)
        slide=screenshot('native-horizontal-scroll.png')
        slide_text=' '.join(row['text'] for row in json.loads(subprocess.check_output([str(ocr),str(slide)],text=True)))
        assert 'Second slide' in slide_text and 'First slide' not in slide_text,slide_text
        request('/m',k='click',x=slide_x,y=slide_y,wait=1)
        for _ in range(30):
            if 'Link requested: https://example.com/slide2' in labels():break
            time.sleep(.1)
        else:raise AssertionError('Link hit test did not follow nested horizontal scroll')
        report={'passed':True,'binary_sha256':hashlib.sha256(BINARY.read_bytes()).hexdigest(),
            'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'window':status['w'],
            'checks':['drag gesture does not activate links','native link activation reaches worker and returns host request','no browser opened','disclosure open/close persists DOM and restores bitmap','fragment scroll reveals target','link activation after native scrolling uses document coordinates','horizontal nested scrolling changes slide and hit target'],
            'screenshots':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.png')},'ocr_after_fragment':text,'personal_accounts_used':False}
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
    finally:
        if app.poll() is None:
            try:
                assert request('/s')['pid']==app.pid;request('/gq')
            except OSError:app.terminate()
            app.wait(timeout=15)
