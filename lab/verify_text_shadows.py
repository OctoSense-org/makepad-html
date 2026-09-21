#!/usr/bin/env python3
"""Native shadow/none control capture using the standalone viewer, with no account."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'target/debug/examples/viewer'
SOURCE = ROOT / 'lab/wechat-corpus/fixtures/16-text-shadows.html'
OUT = ROOT / 'lab/evidence/text-shadows'
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / 'native-validation.json'
REPORT.unlink(missing_ok=True)
control = ROOT / 'target/text-shadow-parity/control.html'
control.parent.mkdir(parents=True, exist_ok=True)
control.write_text(re.sub(r'text-shadow:[^;"}]+', 'text-shadow:none', SOURCE.read_text()))

def capture(source, output):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    def request(path, **params):
        url = f'http://127.0.0.1:{port}{path}?' + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)
    env = dict(os.environ, MAKEPAD_REMOTE=str(port), MAKEPAD_HIDE_WINDOWS='1', MAKEPAD_NO_FOCUS='1')
    with (control.parent / (output.stem + '.log')).open('w') as log:
        app = subprocess.Popen([str(BINARY), str(source)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                assert app.poll() is None, 'Viewer exited during startup'
                try:
                    status = request('/s')
                    assert status['pid'] == app.pid, 'Bridge belongs to another process'
                    if status['w'] and any('Ready · Offline HTML/CSS' in row.get('t', '') for row in request('/snap')['s']):
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(.2)
            else:
                raise RuntimeError('Viewer did not become ready')
            request('/m', k='move', x=1, y=1, wait=1)
            time.sleep(.3)
            shutil.copyfile(request('/g')['png'], output)
            return status['w']
        finally:
            if app.poll() is None:
                try:
                    assert request('/s')['pid'] == app.pid
                    request('/gq')
                except OSError:
                    app.terminate()
                app.wait(timeout=15)

shadow = OUT / 'native-shadows.png'
plain = OUT / 'native-none-control.png'
window = capture(SOURCE, shadow)
control_window = capture(control, plain)
a, b = Image.open(shadow).convert('RGB'), Image.open(plain).convert('RGB')
assert a.size == b.size
# Window chrome + the viewer title occupy 100 CSS px. CI is commonly DPR 1,
# whereas local Retina captures are DPR 2; a fixed pixel crop includes article
# shadows at DPR 1 and would reject the very feature under test.
assert all(window[0][key] == control_window[0][key] for key in ('sz', 'px', 'dpi'))
header_height = round(100 * window[0]['dpi'])
assert ImageChops.difference(a.crop((0, 0, a.width, header_height)), b.crop((0, 0, b.width, header_height))).getbbox() is None
changed = sum(max(pixel) > 24 for pixel in ImageChops.difference(a, b).getdata())
assert changed > 500, f'Missing native text shadows: only {changed} changed pixels'
ocr = ROOT / 'target/makepad-html-ocr'
if not ocr.exists():
    subprocess.run(['swiftc', str(ROOT / 'lab/ocr.swift'), '-o', str(ocr)], check=True)
text = ' '.join(row['text'] for row in json.loads(subprocess.check_output([str(ocr), str(shadow)], text=True)))
assert '文字阴影与继承回归' in text, text
report = {
    'passed': True, 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'binary_sha256': hashlib.sha256(BINARY.read_bytes()).hexdigest(),
    'window': window, 'header_crop_height_px': header_height,
    'pixels_differing_over_24_rgb': changed,
    'control': 'Identical HTML with text-shadow declarations set to none; no layout rewriting',
    'screenshots': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (shadow, plain)},
    'ocr': text, 'personal_accounts_used': False,
    'qualification': 'Native texture feature check, not a WebKit similarity score',
}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False))
