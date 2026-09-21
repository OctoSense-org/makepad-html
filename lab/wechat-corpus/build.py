#!/usr/bin/env python3
"""Build pinned upstream baselines or repository-patched comparison binaries."""
import argparse
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('variant', choices=['media', 'extended', 'patched'])
args = parser.parse_args()
source = ROOT
target = Path(os.environ.get('CARGO_TARGET_DIR', ROOT / 'target/html-corpus-build')).resolve()
env = {**os.environ, 'CARGO_TARGET_DIR': str(target),
       'MAKEPAD_HTML_PATCHSET': 'wechat-css-1+table-2+text-shadow-3' if args.variant == 'patched' else 'none'}
features = 'blitz-dom/woff,image/gif'
if args.variant != 'media':
    features += ',blitz-paint/svg,blitz-dom/floats'

# Baselines must not silently pick up repository [patch] overrides. A standalone
# copy outside either workspace retains the exact upstream git revision while
# sharing the same lab renderer and dependency lock versions.
with tempfile.TemporaryDirectory(prefix='makepad-html-upstream-') as temporary:
    manifest = source / 'Cargo.toml'
    if args.variant != 'patched':
        isolated = Path(temporary)
        for name in ['src', 'examples', 'tests']:
            shutil.copytree(source / name, isolated / name)
        shutil.copy2(source / 'Cargo.lock', isolated / 'Cargo.lock')
        manifest = isolated / 'Cargo.toml'
        text = (source / 'Cargo.toml').read_text().split('# Pinned upstream workspace metadata')[0]
        text = text.replace('anyrender_vello_cpu = { version = "=0.17.0", features = ["filters"] }', 'anyrender_vello_cpu = "=0.17.0"')
        text = text.replace('members = [".", "vendor/blitz/packages/*"]', 'members = ["."]')
        for name in ['blitz-dom', 'blitz-html', 'blitz-paint', 'blitz-traits']:
            text = text.replace(f'path = "vendor/blitz/packages/{name}"',
                'git = "https://github.com/DioxusLabs/blitz", rev = "e99fbdbd1d03b9f0aa1622c3f810d95daac92042"')
        manifest.write_text(text)
    command = ['cargo', '+1.98.0', 'build', '--manifest-path', str(manifest),
               '--example', 'compare_html', '--features', features]
    # Isolated baselines replace the six path entries in their temporary lock.
    if args.variant == 'patched':
        command.append('--locked')
    subprocess.run(command, env=env, check=True, cwd=manifest.parent)
    output = ROOT / f'target/html-corpus-{args.variant}'
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target / 'debug/examples/compare_html', output)
    print(output)
