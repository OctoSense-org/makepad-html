#!/usr/bin/env python3
"""Authored regression probes for patterns found in public WeChat editors.

These are not an official WeChat allowlist or captured, published articles.
Exact upstream revisions and per-case evidence are recorded in corpus.json.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import hashlib
import json

ROOT=Path(__file__).resolve().parent
FIX=ROOT/'fixtures'; ASSETS=ROOT/'assets'
FIX.mkdir(exist_ok=True); ASSETS.mkdir(exist_ok=True)
MD='https://github.com/doocs/md/blob/cbcd3756e55d4982a37ff451753a69ce822e7a58/'
NICE='https://github.com/mdnice/markdown-nice/blob/6525a5aba371209c2840593e8f537b4a69137a4b/'
SOURCES={
 'theme':MD+'packages/shared/src/configs/theme-css/default.css',
 'grace':MD+'packages/shared/src/configs/theme-css/grace.css',
 'renderer':MD+'packages/core/src/renderer/renderer-impl.ts',
 'nice':NICE+'src/template/basic.js',
 'syntax':NICE+'src/template/content.md',
 'blitz':'https://blitz.is/status/css',
 'tables':'https://www.w3.org/TR/CSS22/tables.html#border-conflict-resolution',
}
pattern=Image.new('RGB',(400,240),'#ebf4fa'); d=ImageDraw.Draw(pattern)
for i,c in enumerate(['#d45849','#e8b54b','#56a688','#5079bd']):
 d.rectangle((i*100,0,(i+1)*100-1,180),fill=c)
 d.text((i*100+10,190),str(i+1),fill='black')
d.ellipse((140,55,260,175),fill='#ffffff',outline='#202a40',width=5)
for ext in ['png','jpg','webp','gif']:pattern.save(ASSETS/f'chart.{ext}')
frames=[Image.new('RGB',(120,60),c) for c in ['#dd4455','#3388cc']]
frames[0].save(ASSETS/'animated.gif',save_all=True,append_images=frames[1:],duration=500,loop=0)

def p(text,style=''):
 return f'<p data-probe style="margin:12px 0;{style}">{text}</p>'

cases=[]
def add(name,title,body,features,sources,kind='source-derived pattern'):
 document=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;background:white;color:#333;font:16px/1.75 'PingFang SC',sans-serif;word-wrap:break-word;">
<section id="article" data-probe style="padding:20px;box-sizing:border-box;max-width:100%;">
<h2 data-probe style="font-size:20px;line-height:1.5;margin:0 0 18px;color:#16836a">{title}</h2>{body}</section></body></html>'''
 path=FIX/f'{name}.html';path.write_text(document)
 cases.append({'id':name,'title':title,'file':str(path.relative_to(ROOT)),
               'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
               'features':features,'sources':[SOURCES[s] for s in sources],'provenance':kind})

add('01-typography','中文正文与混合排版',
 p('微信公众号文章需要稳定的中文换行。这里包含 English words、2026 年、标点“引号”和链接。'*2,'text-align:justify;text-indent:2em;letter-spacing:1px;')+
 p('这是<strong>加粗文字</strong>、<em>斜体 English</em>、<u>下划线</u>、<del>删除内容</del>。')+
 p('行内标记 <span style="background:#fff0ba;color:#bc5033;padding:2px 5px;border-radius:4px">重点内容</span> 与 H<sub>2</sub>O、E=mc<sup>2</sup>。')+
 p('LongWord_abcdefghijklmnopqrstuvwxyz_0123456789_abcdefghijklmnopqrstuvwxyz','word-break:break-all;'),
 ['PingFang SC','CJK line breaking','justify','text-indent','letter-spacing','inline decorations','sub/sup'],['theme','nice'])

add('02-headings-quotes','标题、引用与阴影',
 '<h3 data-probe style="display:table;margin:20px auto;padding:6px 18px;color:white;background:#16836a;border-radius:8px;box-shadow:0 4px 6px #0002">居中的主题标题</h3>'+
 '<h3 data-probe style="border-left:4px solid #16836a;border-bottom:1px dashed #16836a;padding-left:12px;text-shadow:2px 2px 4px #777">带装饰线的标题</h3>'+
 '<blockquote data-probe style="margin:20px 0;padding:14px;border-left:4px solid #16836a;background:#eff6f4;border-radius:6px">'+p('引用块保留内联样式、颜色和行距。')+
 '<blockquote data-probe style="margin:10px;padding:12px;box-shadow:1px 1px 10px #0003">嵌套引用，检查阴影与边距。</blockquote></blockquote>'+
 '<hr data-probe style="border:0;height:2px;background:linear-gradient(to right,transparent,#16836a,transparent)">',
 ['display:table heading','auto margins','border styles','border-radius','box-shadow','text-shadow','gradient'],['theme','grace','nice'])

add('03-lists','嵌套列表与手工编号',
 '<ul data-probe style="padding-left:25px;list-style:disc"><li><section style="margin:5px 0">第一个项目：列表内部使用 section。</section></li><li><section>第二个项目</section><ul style="list-style:square"><li>二级列表 A</li><li>二级列表 B</li></ul></li></ul>'+
 '<ol data-probe start="3" style="padding-left:25px"><li>从三开始的有序列表</li><li>包含较长内容的列表项，需要换行后仍保持正确的缩进与行距。</li></ol>'+
 '<ul data-probe style="list-style:none;padding-left:12px"><li>• doocs 风格的文字项目符号</li><li>• 直接写入内容的项目符号</li></ul>',
 ['ul/ol/li/section','nested list markers','start attribute','manual list prefixes'],['renderer','nice'])

add('04-tables','表格、合并单元格与滚动',
 '<section data-probe style="max-width:100%;overflow:auto;-webkit-overflow-scrolling:touch"><table data-probe style="border-collapse:collapse;min-width:500px;font-size:15px"><thead><tr><th style="border:1px solid #999;padding:8px;background:#edf5f2">项目</th><th colspan="2" style="border:1px solid #999;padding:8px;background:#edf5f2">渲染检查</th></tr></thead><tbody><tr><td rowspan="2" style="border:1px solid #999;padding:8px">微信公众号</td><td style="border:1px solid #999;padding:8px">中文</td><td style="border:1px solid #999;padding:8px">HTML / CSS</td></tr><tr><td style="border:1px solid #999;padding:8px">图片</td><td style="border:3px dashed #cf543a;padding:8px">混合边框</td></tr></tbody></table></section>'+p('上方表格比手机视口更宽，应在容器内部滚动。'),
 ['table','colspan/rowspan','border-collapse','nonuniform borders','overflow:auto'],['renderer','nice'])

add('05-code','代码高亮与旧式 WebKit 布局',
 p('正文中的 <code style="font:14px Menlo,monospace;background:#edf3f7;color:#286ca0;padding:2px 4px;border-radius:4px">render(article)</code> 行内代码。')+
 '<pre data-probe style="padding:14px;background:#f4f5f7;overflow:auto;border-radius:6px"><code data-probe style="display:-webkit-box;font:13px/24px Menlo,monospace;white-space:pre"><span style="color:#a626a4">const</span> title = <span style="color:#508040">"公众号文章"</span>;\n<span style="color:#a626a4">function</span> render(article) {\n  return article.content.map(block => block.renderWithTheme());\n}</code></pre>',
 ['pre/code/span','syntax colors','monospace','white-space:pre','display:-webkit-box','horizontal overflow'],['renderer','nice'])

add('06-images','插图、图注与图片格式',
 '<figure data-probe style="margin:0"><img data-probe src="/assets/chart.png" style="display:block;width:100%;height:140px;object-fit:cover;border-radius:12px"><figcaption style="font-size:13px;color:#888;text-align:center">PNG 封面：裁剪填充、圆角</figcaption></figure>'+
 '<section data-probe style="display:flex;gap:10px;margin-top:16px">'+''.join(f'<figure style="margin:0;flex:1;min-width:0"><img data-probe src="/assets/chart.{ext}" style="display:block;width:100%;height:80px;object-fit:contain"><figcaption style="text-align:center;font-size:12px">{ext.upper()}</figcaption></figure>' for ext in ['jpg','gif','webp'])+'</section>'+
 '<img data-probe src="/assets/chart.png" style="display:block;margin:18px auto;width:90px;height:90px;object-fit:cover;border-radius:50%;box-shadow:0 4px 8px #0003">',
 ['PNG','JPEG','static GIF','WebP','object-fit','percentage width','border-radius','figure/figcaption'],['grace','syntax'])

add('07-links-footnotes','链接、脚注与上下标',
 p('公众号内的<a data-probe href="https://mp.weixin.qq.com/" style="color:#27709a;border-bottom:1px solid #27709a;text-decoration:none">文章链接</a>，以及参考文献<sup style="color:#27709a;font-size:11px">[1]</sup>。')+
 '<section data-probe style="display:flex;margin-top:20px"><span data-probe style="width:10%;font-size:80%;opacity:0.6">[1]</span><p data-probe style="width:90%;margin:0;font-size:14px;word-break:break-all">参考资料：https://example.test/articles/very-long-reference-path-that-must-wrap-correctly</p></section>'+
 p('基线测试：正文 <span data-probe style="display:inline-block;background:#dcf1e9;width:48px;height:42px;vertical-align:middle">卡片</span> 对齐。'),
 ['inline border','link styling','superscript','flex footnote','word-break','vertical-align'],['renderer','nice'])

add('08-carousel','横向滑动图片',
 '<section data-probe style="overflow:hidden;margin:16px 0"><section data-probe style="width:100%;white-space:nowrap;overflow-x:scroll">'+''.join(f'<section data-probe style="display:inline-block;width:100%;white-space:normal;vertical-align:middle"><img src="/assets/chart.png" style="display:block;width:100%;height:180px;object-fit:cover"><p style="text-align:center">第 {i} 张插图</p></section>' for i in range(1,4))+'</section></section>'+p('初始截图只应显示第一张；拖动或滚轮需要宿主传递滚动事件。'),
 ['inline-block','nowrap','overflow-x:scroll','nested scroll container','imageflow'],['syntax','nice'])

add('09-svg-attributes','SVG 图标与公式图形',
 '<svg data-probe xmlns="http://www.w3.org/2000/svg" width="280" height="140" viewBox="0 0 280 140"><defs><linearGradient id="g"><stop stop-color="#28ac86"/><stop offset="1" stop-color="#547ac8"/></linearGradient></defs><rect x="5" y="5" width="270" height="130" rx="18" fill="url(#g)"/><path d="M30 96L85 38L138 96L198 34L252 94" fill="none" stroke="white" stroke-width="8"/><circle cx="138" cy="96" r="8" fill="#ffce59"/></svg>'+
 p('静态 SVG 是公式和流程图常用的输出形式。此处用确定性的路径测试渐变、描边和 viewBox，不依赖字体。'),
 ['inline SVG','path','viewBox','presentation attributes','SVG gradient'],['renderer','syntax'])

add('10-svg-css','SVG 的 CSS 样式',
 '<section data-probe style="color:#16836a"><svg data-probe xmlns="http://www.w3.org/2000/svg" width="280" height="140" viewBox="0 0 280 140"><style>.mark{fill:currentColor;stroke:#e7a533;stroke-width:6}</style><rect class="mark" x="8" y="8" width="264" height="124" rx="18"/><path d="M55 72L105 110L220 35" style="fill:none;stroke:white;stroke-width:9"/></svg></section>'+p('与属性版 SVG 分开测试：父级 currentColor、class 选择器及内联 style。'),
 ['SVG CSS','currentColor inheritance','SVG internal stylesheet','inline style'],['theme','renderer'])

add('11-ruby','中文注音与行内对齐',
 p('中文注音：<ruby data-probe>微信<rt>wēi xìn</rt></ruby>，<ruby data-probe>公众号<rt>gōng zhòng hào</rt></ruby>。')+
 p('注音应该排列在汉字上方，而不是混在正文里。')+
 p('上标 x<sup>2</sup> 和下标 H<sub>2</sub>O，字号与基线应该协调。'),
 ['ruby/rt','ruby line metrics','sup/sub baseline'],['syntax'])

add('12-effects','背景、圆角、裁剪与变换',
 '<section data-probe style="padding:20px;background:linear-gradient(120deg,#d9f1e7,#dbe6fa);border-radius:18px;box-shadow:0 8px 18px #17394233"><p style="margin:0;font-weight:bold;text-shadow:2px 2px 3px #889">渐变主题卡片</p><p style="margin:10px 0 0">保留背景、阴影与圆角的组合。</p></section>'+
 '<section data-probe style="margin:30px 0;display:flex;gap:20px"><img data-probe src="/assets/chart.png" style="width:120px;height:120px;object-fit:cover;clip-path:polygon(50% 0,100% 40%,80% 100%,20% 100%,0 40%)"><img data-probe src="/assets/chart.png" style="width:120px;height:120px;object-fit:cover;border-radius:16px;transform:rotate(8deg)"></section>',
 ['gradient','box-shadow','text-shadow','clip-path','transform','border-radius'],['grace','blitz'],'source-derived theme plus exploratory CSS probes; publish acceptance not verified')

add('13-layout','浮动与定位边界',
 '<section data-probe style="display:flow-root"><img data-probe src="/assets/chart.png" style="float:left;width:100px;height:100px;object-fit:cover;margin:0 12px 8px 0">'+('图片与正文环绕排版，检查 float 和 clear。公众号长文需要稳定的行盒位置。'*4)+'</section>'+
 '<section data-probe style="position:relative;height:120px;background:#eff6f3;margin-top:16px;padding:16px"><section style="margin:20px;padding:10px;background:#d7ece3">静态中间容器<span data-probe style="position:absolute;right:0;top:0;background:#da684d;color:white;padding:4px">右上角标签</span></section></section>',
 ['float/clear','flow-root','absolute containing block'],['blitz'],'exploratory CSS layout probe; publish acceptance not verified')

add('14-lazy-image','微信图片属性的宿主处理',
 '<img data-probe data-src="/assets/chart.png" data-type="png" data-ratio="0.6" data-w="400" style="display:block;width:100%;height:160px" alt="只有 data-src 的待加载图片">'+
 p('data-src 只是数据属性。两个普通 HTML 引擎都不会自动把它当作 src；需要导入层在资源授权后转换。'),
 ['data-src','data-ratio','data-w','host import normalization'],['syntax'],'host-integration probe; not a claim of browser-native lazy loading')

add('15-table-edges','表格边界与对齐回归',
 '<style>.edge{border-collapse:collapse;margin:12px 0;table-layout:fixed;width:300px}.edge td{border:2px solid #16836a;padding:4px;height:48px}.edge i{display:block;width:16px;height:12px;background:#3476c8}</style>'+
 '<table class="edge" data-probe><tr><td data-probe rowspan="2"><i data-probe></i></td><td data-probe style="vertical-align:top"><i data-probe></i></td></tr><tr><td data-probe style="border:6px dashed #cf543a;vertical-align:bottom"><i data-probe></i></td></tr><tr><td data-probe colspan="2" style="border-bottom:6px double #3476c8"><i data-probe></i></td></tr></table>'+
 '<table class="edge" data-probe style="direction:rtl"><tr><td data-probe style="border-left:6px solid #3476c8"><i data-probe></i></td><td data-probe style="border-right:4px solid #cf543a"><i data-probe></i></td></tr></table>'+
 '<table class="edge" data-probe style="border:4px solid #3476c8"><colgroup style="border:4px solid #cf543a"><col><col></colgroup><tbody style="border:4px solid #16836a"><tr><td data-probe style="border:none"><i data-probe></i></td><td data-probe style="border-left:hidden;border-right:6px dotted #cf543a"><i data-probe></i></td></tr></tbody></table>'+
 p('验证合并单元格、冲突边框、逻辑方向和单元格内对齐。'),
 ['collapsed border conflicts','rowspan/colspan','top/middle/bottom cell alignment','RTL','row/column group borders','hidden/dashed/dotted/double'],['tables'],
 'authored CSS table regression; not a published WeChat acceptance claim')

(ROOT/'corpus.json').write_text(json.dumps({'description':'Authored representative probes, not an exhaustive or official WeChat subset.',
 'sources':SOURCES,'cases':cases,'viewports':[[390,700],[600,700]],'scale':2},ensure_ascii=False,indent=2))
print(f'Created {len(cases)} fixtures and deterministic media in {ROOT}')
