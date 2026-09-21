#!/usr/bin/env python3
"""Publish captures and diagnostic metrics; deliberately no global fidelity score."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import json

ROOT=Path(__file__).resolve().parent
corpus=json.loads((ROOT/'corpus.json').read_text())
runs=json.loads((ROOT/'run-results.json').read_text())
patched_path=ROOT/'run-results-patched.json'
patched_runs={(r['case'],r['width']):r['patched'] for r in json.loads(patched_path.read_text())} if patched_path.exists() else {}
for r in runs:
    if (r['case'],r['width']) in patched_runs:r['patched']=patched_runs[(r['case'],r['width'])]
FONT=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',23)
NOTES={
 '01-typography':'正文可见，但中文两端对齐、换行、斜体、行内圆角及上下标与 WebKit 不同。',
 '02-headings-quotes':'严重：display:table 标题文字消失；圆角引用的左边框缺失，text-shadow 未呈现。',
 '03-lists':'嵌套项目符号、有序编号、section 包装与手工前缀均可见，测量到的块级边界一致；文字像素仍有差异。',
 '04-tables':'rowspan 的单元格仍画出中间横线、文字未正确居中，混合边框丢失；截图不能证明滚动事件已接入。',
 '05-code':'代码文字与高亮可见；旧式 -webkit-box、长行裁剪和行内背景存在差异。',
 '06-images':'扩展构建恢复 WebP；PNG/JPEG/GIF、object-fit、圆角与阴影整体接近，仍有细节差异。GIF 此处为静态图。',
 '07-links-footnotes':'链接边框、sup 和 vertical-align 存在可见差异；flex 脚注基本成形。',
 '08-carousel':'严重：nowrap + inline-block 图集在 Blitz 中变成纵向排列。还需要给 Makepad 接入容器内部的横向滚动事件。',
 '09-svg-attributes':'启用 SVG 后，属性形式的路径、渐变与描边恢复；行盒高度仍有偏差。',
 '10-svg-css':'启用 SVG 后仍错误：继承自 HTML 父级的 currentColor 变成黑色。SVG 内部 CSS 的部分样式能生效。',
 '11-ruby':'严重：rt 注音落在汉字旁边；sup/sub 没有正确的基线位移。',
 '12-effects':'渐变、圆角和裁剪可见；文字阴影缺失。变换后的视觉边界不等同于未变换的布局框，几何指标需人工解释。',
 '13-layout':'未启用 floats 时超时；启用后可渲染环绕布局，但绝对定位标签相对错误的祖先定位，偏移 36px。该边界探针未验证微信发布接受度。',
 '14-lazy-image':'两边都不会把 data-src 当作 src。需要宿主导入层解析并授权加载；这是适配需求，不是 Blitz 独有的渲染缺陷。',
}
PATCH_NOTES={
 '02-headings-quotes':'已修复 display:table 标题丢字；圆角引用边框和文字阴影仍有差异。',
 '08-carousel':'已修复仅含卡片的 nowrap 图集纵排；Makepad 内部横向滚动交互尚未接入。混合文本与卡片的完整换行规则仍待补齐。',
 '10-svg-css':'已修复 HTML 继承的 currentColor；覆盖 SVG 属性、内联样式、内部 CSS 和动态颜色回归测试。生产入口仍拒绝 SVG。',
}
records=[]
for run in runs:
    cid=run['case'];width=run['width'];case=next(c for c in corpus['cases'] if c['id']==cid)
    out=ROOT/'evidence'/cid/str(width)
    wk=json.loads((out/'webview-original.json').read_text())
    ref=Image.open(out/'webview-original-full.png').convert('RGB')
    record={**run,'title':case['title'],'features':case['features'],'sources':case['sources'],'note':NOTES[cid],'patched_note':PATCH_NOTES.get(cid,NOTES[cid]),'variants':{}}
    for variant in ['media','extended'] + (['patched'] if 'patched' in run else []):
        folder=out if variant=='media' else out/variant
        result=run[variant]
        if result['exit_code']!=0:
            placeholder=Image.new('RGB',ref.size,'#f6e7e7');d=ImageDraw.Draw(placeholder)
            d.text((25,80),'BLITZ RENDER TIMED OUT' if 'timeout_seconds' in result else 'BLITZ RENDER FAILED',font=FONT,fill='#9b2632')
            d.text((25,125),'No renderer pixels are substituted.',font=FONT,fill='#9b2632')
            placeholder.save(out/f'diff-{variant}.png')
            img=placeholder;metrics={'render_failed':True,**result}
        else:
            b=json.loads((folder/'blitz-original.json').read_text())
            img=Image.open(folder/'blitz-original-full.png').convert('RGB')
            probes=b['elements']['[data-probe]'];rp=wk['observation']['elements']['[data-probe]']
            deltas=[max(abs(a[k]-z[k]) for k in ['x','y','width','height']) for a,z in zip(probes,rp) if a and z]
            height=max(img.height,ref.height)
            a=Image.new('RGB',(width*2,height),'white');a.paste(img,(0,0))
            z=Image.new('RGB',(width*2,height),'white');z.paste(ref,(0,0))
            aa=np.asarray(a).astype(np.int16);zz=np.asarray(z).astype(np.int16)
            ink=(np.max(255-aa,axis=2)>12)|(np.max(255-zz,axis=2)>12)
            diff=np.max(np.abs(aa-zz),axis=2)>24
            metrics={'render_failed':False,'content_union_pixels':int(ink.sum()),
                     'content_pixels_differing_over_24_rgb_pct':round(float((diff&ink).sum()/max(1,ink.sum())*100),3),
                     'probe_count':[len(probes),len(rp)],'max_probe_delta_css':round(max(deltas,default=0),3),
                     'median_probe_delta_css':round(float(np.median(deltas)),3),
                     'article_height_css':[probes[0]['height'],rp[0]['height']],
                     'production_admission':b['product_admission'],'decode_probes':b.get('image_decode_probes',[])}
            delta=np.clip(np.abs(aa-zz)*3,0,255).astype(np.uint8)
            Image.fromarray(delta).save(out/f'diff-{variant}.png')
        canvas=Image.new('RGB',(width*4+24,max(img.height,ref.height)+50),'#e8edf1')
        d=ImageDraw.Draw(canvas)
        d.text((12,12),f'Blitz / {variant}',font=FONT,fill='#172333')
        d.text((width*2+36,12),'macOS WKWebView',font=FONT,fill='#172333')
        canvas.paste(img,(0,50));canvas.paste(ref,(width*2+24,50))
        canvas.save(out/f'pair-{variant}.png')
        record['variants'][variant]=metrics
    records.append(record)
report={'method':'Raw-engine diagnostic, exact identical fixture bytes and resources. Real macOS WKWebView; page JS disabled. 2x. No registration or alignment. CSS font-family PingFang SC in both.',
 'scope':'Source-derived authored fixtures; not published WeChat captures, not an official exhaustive allowlist, not iOS/Android WeChat certification.',
 'variants':{'patched':'Same extended features + repository vendor/blitz patches wechat-css-1','media':'woff + gif; other product defaults','extended':'woff + gif + blitz-paint/svg + blitz-dom/floats; WebP decoder enabled transitively by SVG'},
 'metric_limits':'Pixel difference is measured only over the union of nonwhite content, threshold 24/255; it is not similarity or a 9/10 score. Font rasterization affects pixels. Probe rectangles can differ for transforms even when pixels agree. Exit 0 only means capture completed.',
 'results':records}
(ROOT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
data=json.dumps(report,ensure_ascii=False).replace('</','<\\/')
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>公众号 HTML/CSS · Blitz / WKWebView</title>
<style>body{margin:24px;font:15px/1.65 system-ui;background:#eff2f6;color:#182638}h1{font-size:24px}select,button{padding:8px;margin:4px}label{margin-right:12px}.card{padding:16px;background:white;border-radius:12px;margin-bottom:16px}img{max-width:100%;background:white}a{color:#16658d}pre{white-space:pre-wrap;font-size:12px}#stats{display:flex;gap:20px}.warning{color:#934522}nav{position:sticky;top:0;background:#eff2f6;padding:8px 0}details{margin:12px 0}</style>
<h1>公众号 HTML/CSS：真实渲染对照与缺口</h1>
<div class="card">14 个样本 × 390 / 600 CSS px。来源：doocs/md、Markdown Nice；少量边界探针另有标注。<br>原始 HTML 和资源一致，字体声明均为 PingFang SC，页面 JS 关闭。右侧是真实 macOS WKWebView；这不是 iOS 或微信客户端验收。<br><a href="README.md">研究结论与修改路线</a> · <a href="corpus.json">样本及来源</a> · <a href="results.json">原始测量</a></div>
<nav><label>样本 <select id="case"></select></label><label>宽度 <select id="width"><option>390</option><option>600</option></select></label><label>Blitz 构建 <select id="variant"><option value="patched">本地修复后</option><option value="extended">图片 + SVG + float</option><option value="media">图片格式启用后</option></select></label><label>视图 <select id="mode"><option value="pair">并排</option><option value="diff">像素差异 ×3</option></select></label></nav>
<div class="card"><strong id="title"></strong><p id="note"></p><div id="stats"></div><details><summary>样本来源、HTML 与测量</summary><div id="links"></div><pre id="details"></pre></details><p class="warning">像素差异百分比不是相似度评分；“完成截图”也不表示兼容通过。</p></div>
<img id="capture" alt="真实引擎截图"><script>const report=DATA;
const $=id=>document.getElementById(id);const cases=[...new Map(report.results.map(r=>[r.case,r])).values()];for(const r of cases){const o=new Option(r.title,r.case);$('case').add(o)}
function update(){const r=report.results.find(r=>r.case===$('case').value&&String(r.width)===$('width').value);const v=$('variant').value;const m=r.variants[v];$('title').textContent=r.title;$('note').textContent=v==='patched'?r.patched_note:r.note;$('stats').textContent=m.render_failed?'渲染超时或失败':`探针最大边界差 ${m.max_probe_delta_css}px · 中位差 ${m.median_probe_delta_css}px · 内容像素差异 ${m.content_pixels_differing_over_24_rgb_pct}%`;$('details').textContent=JSON.stringify(m,null,2);$('links').replaceChildren();for(const [i,url] of r.sources.entries()){const a=document.createElement('a');a.href=url;a.textContent=`来源 ${i+1} `;a.target='_blank';$('links').append(a)}const src=document.createElement('a');src.href=`fixtures/${r.case}.html`;src.textContent='查看 HTML';$('links').append(src);$('capture').src=`evidence/${r.case}/${r.width}/${$('mode').value}-${v}.png`;}
for(const el of document.querySelectorAll('select'))el.onchange=update;update();</script></html>'''.replace('DATA',data)
(ROOT/'index.html').write_text(page)
for r in records:
 e=r['variants'].get('patched',r['variants']['extended']);print(r['case'],r['width'],'FAIL' if e['render_failed'] else f"maxΔ {e['max_probe_delta_css']}px; content pixel diff {e['content_pixels_differing_over_24_rgb_pct']}%")
