#!/usr/bin/env python3
"""Reproduce native renderer captures and compare original, unaligned pixels.

Requires macOS, Pillow and NumPy. The downloaded upstream HTML stays untracked.
No WebView screenshot is synthesized; both PNG sets come from real renderers.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import plistlib
import subprocess
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def box(mask):
    y, x = np.where(mask)
    return [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1]


def compare(label):
    a = np.asarray(Image.open(EVIDENCE / f"blitz-{label}.png").convert("RGB"))
    b = np.asarray(Image.open(EVIDENCE / f"webview-{label}-static.png").convert("RGB"))
    assert a.shape == b.shape
    blitz = json.loads((EVIDENCE / f"blitz-{label}.json").read_text())
    wk = json.loads((EVIDENCE / f"webview-{label}-static.json").read_text())
    assert wk["observations"][0]["text"] == "#000000"
    assert wk["observations"][0]["viewport"]["dpr"] == blitz["scale"] == 2
    assert blitz["product_admission"] == "unsupported active/document element: script"
    # The document contains one white card on a black background. Detect its
    # rendered pixels independently of each engine's DOM rectangle measurement.
    card_a, card_b = box((a >= 250).all(2)), box((b >= 250).all(2))
    x0 = min(card_a[0], card_b[0]); y0 = min(card_a[1], card_b[1])
    x1 = max(card_a[2], card_b[2]); y1 = max(card_a[3], card_b[3])
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    roi = diff[y0:y1, x0:x1]
    # Text-only union crop excludes the large matching page background/padding.
    boxes = []
    for pixels, card in [(a, card_a), (b, card_b)]:
        left, top, right, bottom = card
        text_box = box((pixels[top+12:bottom-12, left+12:right-12] < 128).all(2))
        boxes.append([text_box[0]+left+12, text_box[1]+top+12, text_box[2]+left+12, text_box[3]+top+12])
    tx0, ty0 = min(r[0] for r in boxes)-6, min(r[1] for r in boxes)-6
    tx1, ty1 = max(r[2] for r in boxes)+6, max(r[3] for r in boxes)+6
    text_diff = diff[ty0:ty1, tx0:tx1]
    Image.fromarray(np.minimum(diff * 4, 255).astype(np.uint8)).save(EVIDENCE / f"difference-{label}.png")
    pair(EVIDENCE / f"blitz-{label}.png", EVIDENCE / f"webview-{label}-static.png", EVIDENCE / f"side-by-side-{label}.png", "Blitz | original HTML, no JS", "WKWebView | same HTML, JS disabled")
    zoom_a = Image.fromarray(a[ty0:ty1, tx0:tx1]).resize(((tx1-tx0)*3,(ty1-ty0)*3), Image.Resampling.NEAREST)
    zoom_b = Image.fromarray(b[ty0:ty1, tx0:tx1]).resize(zoom_a.size, Image.Resampling.NEAREST)
    pair_images(zoom_a, zoom_b, EVIDENCE / f"text-zoom-{label}.png", "Blitz: 3x nearest-neighbor crop", "WKWebView: identical crop")
    ra = blitz["card_rect_css"]; rb = wk["observations"][0]["cardRect"]
    intersection = max(0, min(ra["x"]+ra["width"],rb["x"]+rb["width"])-max(ra["x"],rb["x"])) * max(0,min(ra["y"]+ra["height"],rb["y"]+rb["height"])-max(ra["y"],rb["y"]))
    iou = intersection / (ra["width"]*ra["height"]+rb["width"]*rb["height"]-intersection)
    return {
        "viewport_css": [blitz["width_css"], blitz["height_css"]], "dpr":2,
        "blitz_card_css":ra,"webview_card_css":rb,
        "card_delta_css_blitz_minus_webview":{k:ra[k]-rb[k] for k in ra},
        "card_rectangle_iou":iou,
        "blitz_card_pixel_bounds":card_a,"webview_card_pixel_bounds":card_b,
        "full_frame_mean_absolute_channel_error_0_255":float(diff.mean()),
        "full_frame_pixels_with_channel_error_over_16_percent":float((diff.max(2)>16).mean()*100),
        "card_union_mean_absolute_channel_error_0_255":float(roi.mean()),
        "card_union_pixels_with_channel_error_over_16_percent":float((roi.max(2)>16).mean()*100),
        "text_union_mean_absolute_channel_error_0_255":float(text_diff.mean()),
        "text_union_pixels_with_channel_error_over_16_percent":float((text_diff.max(2)>16).mean()*100),
        "text_crop_pixel_bounds":[tx0,ty0,tx1,ty1],
        "product_admission":blitz["product_admission"],
        "network_requests":blitz["denied_resources"],
    }


def pair_images(a, b, destination, left, right):
    header=64; gap=24
    canvas=Image.new("RGB",(a.width+b.width+gap,max(a.height,b.height)+header),(235,237,240))
    draw=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf",24)
    except OSError: font=ImageFont.load_default()
    draw.text((16,18),left,fill=(25,30,40),font=font)
    draw.text((a.width+gap+16,18),right,fill=(25,30,40),font=font)
    canvas.paste(a,(0,header));canvas.paste(b,(a.width+gap,header));canvas.save(destination)


def pair(a,b,destination,left,right):
    pair_images(Image.open(a).convert("RGB"),Image.open(b).convert("RGB"),destination,left,right)


def page(report):
    desk=report["static"]["desktop"]; mobile=report["static"]["mobile"]
    rows="".join(f'<tr><td>{name}</td><td>{data["blitz_card_css"]["width"]:.3f} × {data["blitz_card_css"]["height"]:.3f}</td><td>{data["webview_card_css"]["width"]:.3f} × {data["webview_card_css"]["height"]:.3f}</td><td>{data["card_union_pixels_with_channel_error_over_16_percent"]:.2f}%</td><td>{data["text_union_pixels_with_channel_error_over_16_percent"]:.2f}%</td></tr>' for name,data in [("桌面 800×600",desk),("窄屏 390×844",mobile)])
    template='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Blitz × WKWebView 实测</title>
<style>body{margin:0;background:#f1f3f5;color:#20272c;font:16px/1.7 -apple-system,"PingFang SC",sans-serif}main{max-width:1400px;margin:auto;padding:32px}h1{line-height:1.2}p{max-width:1050px}.notice{padding:16px 20px;background:#fff3d3;border-radius:12px}select,input,button{font:inherit;padding:8px;margin:8px 16px 8px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.panel{min-width:0;background:white;padding:12px;border-radius:12px}.panel img{display:block;width:100%;height:auto}.panel h3{margin:0 0 10px}table{border-collapse:collapse;width:100%;background:white}th,td{padding:12px;text-align:left;border-bottom:1px solid #ddd}.overlay{position:relative;width:min(100%,800px);margin:12px auto}.overlay img{display:block;width:100%}.overlay .top{position:absolute;inset:0;clip-path:inset(0 0 0 50%)}details img{max-width:100%}code{font-size:.85em}a{color:#086cbd}@media(max-width:720px){main{padding:16px}.pair{grid-template-columns:1fr}table{font-size:12px}}</style>
<main><h1>同一份 HTML：Blitz × WKWebView</h1><p>DigitalOcean sample-html · 固定源码 <a href="SOURCE">COMMIT</a> · macOS WKWebView / WebKit 与 Blitz REV。原文件字节完全相同，未改 HTML/CSS。静态对照关闭 WebView 的页面脚本，Blitz 没有 JS 运行时。</p>
<p class="notice"><strong>产品入口与引擎实验有区别：</strong>Robrix 当前的安全入口拒绝原文件的 <code>&lt;script&gt;</code>。左侧是独立实验程序直接调用 Blitz 静态引擎的结果，并非已允许此网页作为 Robrix 小程序运行。生产权限策略未修改。</p>
<select id="size"><option value="desktop">桌面 800 × 600 · DPR 2</option><option value="mobile">窄屏 390 × 844 · DPR 2</option></select><select id="mode"><option value="static">静态 HTML/CSS：页面脚本关闭</option><option value="dynamic-initial">开启 WebView JS：首次加载</option><option value="dynamic-body-click">开启 WebView JS：点击背景后</option></select><p id="note"></p>
<div class="pair"><section class="panel"><h3>Blitz · 无 JavaScript</h3><img id="left"></section><section class="panel"><h3 id="rightTitle">WKWebView</h3><img id="right"></section></div>
<h2>测量结果</h2><p>矩形单位为 CSS 像素。差异像素：任意 RGB 通道的绝对误差 &gt;16/255。直接比较同一坐标，未做平移配准。卡片和文字区域单独统计，避免大面积相同背景掩盖字形差异。</p><table><tr><th>视口</th><th>Blitz 卡片</th><th>WebView 卡片</th><th>卡片区域差异像素</th><th>文字区域差异像素</th></tr>ROWS</table>
<h2>同坐标叠加检查</h2><p>拖动滑块：左侧 Blitz，右侧 WKWebView。原始 PNG 都为 DPR 2，此处仅按显示宽度缩放。</p><input type="range" id="wipe" min="0" max="100" value="50"><div class="overlay"><img id="under"><img class="top" id="over"></div>
<details open><summary>文字放大（3 倍最近邻，同一裁剪坐标）</summary><img id="zoom"></details><details><summary>绝对差异图（RGB 差值放大 4 倍）</summary><img id="diff"></details>
<p><strong>范围：</strong>这是单个简单页面的实测。窄屏也是 macOS WKWebView，不代表 iOS WebKit 真机。未覆盖微信公众号复杂样式、正文插图、表格、长文或编辑交互，不能据此给出 9/10 微信兼容评分。</p><p><a href="results.json">完整 JSON / 输入和截图哈希</a> · <a href="README.md">复现说明</a></p></main>
<script>const $=id=>document.getElementById(id);function update(){let s=$('size').value,m=$('mode').value;if(s==='mobile'&&m!=='static'){$('size').value='desktop';s='desktop'}const a=`evidence/blitz-${s}.png`,b=`evidence/webview-${s}-${m}.png`;$('left').src=$('under').src=a;$('right').src=$('over').src=b;$('zoom').src=`evidence/text-zoom-${s}.png`;$('diff').src=`evidence/difference-${s}.png`;$('rightTitle').textContent=m==='static'?'WKWebView · 页面脚本关闭':'WKWebView · 页面脚本开启';$('note').textContent=m==='static'?'两边都呈现原始 #000000 静态状态。':'使用固定随机种子复现原网页逻辑。WebView 执行页面 JS 后换色；Blitz 保持原始静态状态。行为差异不计入静态排版测量。'}$('size').onchange=$('mode').onchange=update;$('wipe').oninput=()=>{$('over').style.clipPath=`inset(0 0 0 ${$('wipe').value}%)`};update();</script></html>'''
    source=report['source']
    return template.replace('SOURCE',html.escape(source['source_url'],quote=True)).replace('COMMIT',source['commit'][:12]).replace('REV',report['blitz_revision'][:12]).replace('ROWS',rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--blitz-bin',type=Path)
    parser.add_argument('--webview-bin',type=Path)
    args=parser.parse_args()
    source=json.loads((ROOT/'source.json').read_text())
    original=ROOT/'inputs/digitalocean-original.html'
    if not original.exists():
        original.parent.mkdir(parents=True,exist_ok=True)
        url=f'https://raw.githubusercontent.com/digitalocean/sample-html/{source["commit"]}/index.html'
        original.write_bytes(urllib.request.urlopen(url,timeout=30).read())
    assert digest(original)==source['sha256']
    EVIDENCE.mkdir(exist_ok=True)
    if args.render:
        if not args.blitz_bin or not args.webview_bin:parser.error('--render needs both binary paths')
        for label,w,h in [('desktop',800,600),('mobile',390,844)]:
            tail=[str(original),str(EVIDENCE),str(w),str(h),'2',label]
            subprocess.run([str(args.blitz_bin.resolve()),*tail],check=True,timeout=45)
            subprocess.run([str(args.webview_bin.resolve()),*tail,'static'],check=True,timeout=45)
        subprocess.run([str(args.webview_bin.resolve()),str(original),str(EVIDENCE),'800','600','2','desktop','dynamic'],check=True,timeout=45)
    static={label:compare(label) for label in ['desktop','mobile']}
    dynamic=json.loads((EVIDENCE/'webview-desktop-dynamic.json').read_text())
    states=dynamic['observations']
    assert states[0]['text']!= '#000000'
    assert states[0]['text']==states[1]['text']
    assert states[1]['text']!=states[2]['text']
    pair(EVIDENCE/'blitz-desktop.png',EVIDENCE/'webview-desktop-dynamic-initial.png',EVIDENCE/'side-by-side-js-enabled.png','Blitz | original static state','WKWebView | original JS executed')
    assert digest(original)==source['sha256']
    report={
        'created_at_utc':datetime.now(timezone.utc).isoformat(),'source':source,
        'blitz_revision':json.loads((EVIDENCE/'blitz-desktop.json').read_text())['revision'],
        'method':{'same_input_bytes':True,'input_rewritten':False,'capture':'Blitz raw CPU pixels and real macOS WKWebView.takeSnapshot','static_webview_page_js':False,'raw_blitz_has_js_engine':False,'production_admission_bypassed_in_lab_only':True,'production_policy_changed':False,'dynamic_webview_seed':'0x12345678 LCG, injected via WKUserScript','click_method':'DOM .click() calls, not physical pointer input','pixel_alignment':'none','background_dominates_full_frame':True,'narrow_viewport_is_ios_device':False},
        'static':static,'dynamic':{'observed_hex':[s['text'] for s in states],'card_click_preserves_color':True,'body_click_changes_color':True},
        'artifact_sha256':{p.name:digest(p) for p in sorted(EVIDENCE.glob('*')) if p.suffix in ['.png','.json']},
    }
    framework=Path('/System/Library/Frameworks/WebKit.framework/Versions/A/Resources/Info.plist')
    if framework.exists():
        with framework.open('rb') as file: info=plistlib.load(file)
        report['webkit_version']={k:info.get(k) for k in ['CFBundleShortVersionString','CFBundleVersion']}
    if args.blitz_bin and args.webview_bin:
        report['binary_sha256']={'blitz_comparison':digest(args.blitz_bin),'wkwebview_comparison':digest(args.webview_bin)}
    (ROOT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'index.html').write_text(page(report))
    print(json.dumps({'static':static,'dynamic':report['dynamic']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
