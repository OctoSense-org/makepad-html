#!/usr/bin/env python3
"""Generate an offline, inspectable report without turning pixel error into a score."""
from pathlib import Path
import html
import json

ROOT=Path(__file__).resolve().parent
report=json.loads((ROOT/'results.json').read_text())
corpus=json.loads((ROOT/'corpus.json').read_text())
rows=report['results']
assert len(rows)==40 and len({(r['case'],r['width']) for r in rows})==40
completed=sum(r['blitz']['exit_code']==0 and r['webview']['exit_code']==0 for r in rows)
decoded=sum(r.get('webview_images',{}).get('decoded',0) for r in rows)
summary={'themes':len(corpus['cases']),'comparisons':len(rows),'completed':completed,
    'failed': [{'case':r['case'],'width':r['width'],'blitz':r['blitz'],'webview':r['webview']} for r in rows if r['blitz']['exit_code']!=0 or r['webview']['exit_code']!=0],
    'webview_images_decoded':decoded,'webview_images_expected':6*len(rows),
    'blitz_denied_resource_count':sum(len(r.get('denied_resources',[])) for r in rows),
    'successful_render_snapshot_image_formats_decode':all(p['decoded'] for r in rows for p in r.get('image_decode_probes',[])),
    'largest_absolute_height_delta_css':max(abs(r['metrics']['height_css'][0]-r['metrics']['height_css'][1]) for r in rows if 'metrics' in r),
    'source_html_bytes_unchanged':True}
for case in corpus['cases']:
    import hashlib
    assert hashlib.sha256((ROOT/case['file']).read_bytes()).hexdigest()==case['sha256']
(ROOT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
compact=[{k:r[k] for k in ['case','name','width','blitz','webview','metrics','production_admission','webview_images'] if k in r} for r in rows]
data=json.dumps(compact,ensure_ascii=False).replace('</','<\\/')
table=[]
for c in corpus['cases']:
    cells=[]
    for w in [390,600]:
        r=next(r for r in rows if r['case']==c['id'] and r['width']==w)
        if 'metrics' in r:
            b,k=r['metrics']['height_css'];delta=b-k
            text=f'{b:g} / {k:g}（{delta:+g}）'
        else:text='捕获失败'
        cells.append(f'<td><a href="#" data-case="{c["id"]}" data-width="{w}">{text}</a></td>')
    table.append('<tr><td>'+html.escape(c['name'])+'</td>'+''.join(cells)+'</tr>')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>花生编辑器 · Blitz / WKWebView 实测</title>
<style>body{margin:24px;font:15px/1.65 -apple-system,"PingFang SC",sans-serif;color:#23342f;background:#f3f6f5}h1{font-size:26px}nav,.card{padding:16px;background:white;border-radius:10px;margin:16px 0}nav{position:sticky;top:0;z-index:1;display:flex;gap:20px;flex-wrap:wrap;box-shadow:0 2px 10px #0001}select{font:inherit;padding:6px}a{color:#087c5a}#capture{display:block;width:100%;max-width:1224px;height:auto;background:white}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}.muted{color:#62706b}pre{white-space:pre-wrap}#note{font-weight:600}</style>
<h1>花生编辑器：实际导出 HTML 渲染对照</h1>
<div class="card">20 个主题 × 390 / 600 CSS px × 2× DPI。SUMMARY<br>
直接运行固定版本花生编辑器的 Markdown 渲染与“复制到公众号”导出函数；两边使用完全相同的导出 HTML 和嵌入图片，保留主题原字体。<br>
<strong>内容是统一测试文章，不是已发布公众号文章。下方为实际引擎截图，捕获完成不等于兼容通过；像素差不是相似度评分。</strong><br>
<a href="README.md">测试方法与发现</a> · <a href="article.md">输入文章</a> · <a href="corpus.json">来源与导出记录</a> · <a href="results.json">全部测量</a></div>
<details class="card"><summary>20 个主题结果总览：全文高度 Blitz / WebKit（差值 CSS px）</summary><table><thead><tr><th>主题</th><th>390 px</th><th>600 px</th></tr></thead><tbody>ROWS</tbody></table></details>
<nav><label>主题 <select id="case"></select></label><label>宽度 <select id="width"><option>390</option><option>600</option></select></label><label>视图 <select id="mode"><option value="pair">并排截图</option><option value="diff">像素差 ×3</option></select></label></nav>
<div class="card"><strong id="title"></strong><p id="note"></p><div id="stats"></div><div id="links"></div><details><summary>原始测量</summary><pre id="details"></pre></details></div><img id="capture" alt="左 Blitz，右 macOS WKWebView 的真实渲染截图">
<script>const rows=DATA;const $=id=>document.getElementById(id);
for(const r of rows.filter(r=>r.width===390)){const opt=document.createElement('option');opt.value=r.case;opt.textContent=r.name;$('case').append(opt)}
function update(){const r=rows.find(r=>r.case===$('case').value&&r.width===Number($('width').value));$('title').textContent=r.name;
$('note').textContent='布局和字体仍有可见差异；请滚动查看全文，尤其是图片表格、行内装饰与文章尾部。';
const m=r.metrics;$('mode').querySelector('[value="diff"]').disabled=!m;if(!m){$('mode').value='pair';$('note').textContent='Blitz 渲染崩溃：当前 Vello CPU 后端不支持此主题所用的灰度/棕褐色滤镜。左侧为失败提示，右侧为实际 WKWebView 截图。'}
else if(r.case==='gaudi-organic')$('note').textContent='已目视确认：background-clip:text 画成整块渐变背景；引用的渐变边框缺失；中文字体与换行不同。';
else if(r.case==='wechat-ft')$('note').textContent='已目视确认：中文字体、斜体、链接下边框及图片尺寸不同，造成下文累计位移。';
$('stats').textContent=m?`全文高度 ${m.height_css[0]} / ${m.height_css[1]} CSS px · 内容像素差 ${m.content_pixels_differing_over_24_rgb_pct}%（不是相似度）`:'捕获失败，详见日志';
$('details').textContent=JSON.stringify(r,null,2);$('capture').src=`evidence/${r.case}/${r.width}/${$('mode').value}.png`;
$('links').replaceChildren();for(const [name,path] of [['同源渲染 HTML',`fixtures/${r.case}.html`],['原始导出片段',`exports/${r.case}.html`],['编辑器预览片段',`previews/${r.case}.html`],['Blitz 日志',`evidence/${r.case}/${r.width}/blitz.log`]]){const a=document.createElement('a');a.href=path;a.textContent=name+' · ';a.target='_blank';$('links').append(a)}}
for(const s of document.querySelectorAll('select'))s.onchange=update;
for(const a of document.querySelectorAll('a[data-case]'))a.onclick=e=>{e.preventDefault();$('case').value=a.dataset.case;$('width').value=a.dataset.width;update();document.querySelector('nav').scrollIntoView()};
update();</script></html>'''
page=page.replace('SUMMARY',f'{completed}/40 组双引擎捕获完成，WKWebView 图片解码 {decoded}/240。').replace('ROWS',''.join(table)).replace('DATA',data)
(ROOT/'index.html').write_text(page)
print(json.dumps(summary,ensure_ascii=False))
