#!/usr/bin/env python3
"""Audit provenance, capture completeness, and actual image paint in successful runs."""
from pathlib import Path
import hashlib
import json
import subprocess
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
corpus=json.loads((ROOT/'corpus.json').read_text())
report=json.loads((ROOT/'results.json').read_text())
assert len(corpus['cases'])==20 and len(report['results'])==40
checks=[]
for c in corpus['cases']:
    source=(ROOT/c['file']).read_bytes()
    fragment=(ROOT/'exports'/f'{c["id"]}.html').read_bytes()
    preview=(ROOT/'previews'/f'{c["id"]}.html').read_bytes()
    assert hashlib.sha256(source).hexdigest()==c['sha256']
    assert hashlib.sha256(fragment).hexdigest()==c['exported_fragment_sha256']
    assert hashlib.sha256(preview).hexdigest()==c['preview_sha256']
    assert source.endswith(fragment+b'</body></html>'), 'Export body was rewritten'
    assert c['export_inventory']['images']==6 and c['export_inventory']['grid_count']==0
    assert c['export_inventory']['nested_lists']==0 and c['preview_inventory']['nested_lists']==1
    assert c['export_inventory']['links_in_lists']==0 and c['preview_inventory']['links_in_lists']==1
for r in report['results']:
    out=ROOT/'evidence'/r['case']/str(r['width'])
    for name,digest in r['evidence_sha256'].items():
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest
    for engine in ['webview','blitz']:
        if r[engine]['exit_code']!=0:continue
        metrics=json.loads((out/f'{engine}-original.json').read_text())
        if engine=='webview':
            assert metrics['source_sha256']==r['source_sha256']
            assert metrics['page_scripts_enabled'] is False
            rects=metrics['observation']['elements']['img']
            assert r['webview_images']=={'total':6,'decoded':6}
        else:
            rects=metrics['elements']['img']
            assert not metrics['denied_resources']
        assert len(rects)==6
        with Image.open(out/f'{engine}-original-full.png') as image:
            image=image.convert('RGB');paint=[]
            for rect in rects:
                assert rect and rect['width']>0 and rect['height']>0
                x,y,w,h=[rect[k] for k in ['x','y','width','height']]
                box=(max(0,int(x*2)),max(0,int(y*2)),min(image.width,int((x+w)*2)),min(image.height,int((y+h)*2)))
                assert box[2]>box[0] and box[3]>box[1], 'Image outside captured viewport'
                a=np.asarray(image.crop(box)).astype(np.int16)
                # Each calibration image contains red/yellow/green/blue fields.
                colored=(a.max(axis=2)-a.min(axis=2)>65)&(a.min(axis=2)<170)
                paint.append(int(colored.sum()))
                assert paint[-1]>100, 'Image rectangle contains no calibration colors'
        checks.append({'case':r['case'],'width':r['width'],'engine':engine,'painted_image_regions':len(paint),'color_pixels_per_image':paint})
validation={'passed':True,'repository_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
    'lab_renderer_source_sha256':hashlib.sha256((REPO/'examples/compare_html.rs').read_bytes()).hexdigest(),
    'html_sources':20,'capture_pairs':40,'successful_engine_captures':len(checks),
    'visible_image_regions_verified':sum(c['painted_image_regions'] for c in checks),
    'meaning':'Artifact integrity and actual image paint checks, NOT visual parity approval. Four Blitz captures failed; see summary.json.',
    'checks':checks}
(ROOT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in validation.items() if k!='checks'},ensure_ascii=False))
