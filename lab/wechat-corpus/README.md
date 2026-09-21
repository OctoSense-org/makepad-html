# 公众号 HTML/CSS：Blitz 与 WKWebView 实测

2026-09-21。打开 [交互对照页](index.html)，可切换 14 个样本、390/600 CSS px、三种 Blitz 构建，以及并排/差异图。原文、来源和 SHA-256 在 [corpus.json](corpus.json)，所有测量在 [results.json](results.json)。

结论：Blitz 可以作为原生公众号文章渲染的基础，但当前不能称为完整兼容。本轮已修复 CSS 表格标题丢字、仅含卡片的 nowrap 图集纵排、SVG 的 HTML 颜色继承。表格跨度/边框、注音、行内装饰和更完整的 SVG 样式仍有缺口。当前 Robrix 接入还只是静态位图预览。

**已实现的第一批引擎修复**

源码在 `vendor/blitz`，由独立 `makepad-html` 工作区拥有；Robrix 通过固定 git revision 使用此库。
保留上游的六个最小依赖包、许可证和固定版本；没有修改共享 Cargo 缓存。
`media`/`extended` 是修复前基线，`patched` 为相同 extended 特性加本地补丁。
HTML 文件 SHA-256、资源、视口和 WKWebView 参考截图保持不变。

| 问题 | 修复 | 实测结果（390 / 600 CSS px） |
|---|---|---|
| `display:table` 普通文本丢失 | 生成匿名行/单元格，不改原 DOM；纳入重建和释放流程 | 标题出现；该样本最大探针差 133.531 → 2.031px |
| 纯卡片 `nowrap` 图集纵排 | 在没有文本簇传递换行规则时，读取每个原子行内盒的父级规则 | 最大探针差 700/1120 → 0px；内部文字仍可正常换行 |
| SVG 内 CSS 的 `currentColor` 变黑 | 传递 HTML 计算颜色；保留 SVG 自身颜色级联，移除序列化时错误替换；样式更新后重建 SVG | 绿色与参考一致；动态颜色、属性/内联/CSS 覆盖测试通过 |

补丁版 28/28 个组合完成截图。其余 11 个样本 × 2 种宽度的 PNG 与 extended 基线逐字节一致。
这不是 28 项兼容通过：标题的边框/阴影、SVG 后方 8px 行盒偏差等仍存在。
图集修复只覆盖无文本簇、全部原子盒且父级禁止换行的行内上下文；混合文本/盒的完整规则需要继续修 Parley。
未添加 Makepad 内部横向滚动事件，也未开放生产 SVG 入口；SVG 测试走明确标注的 raw-engine 诊断路径。

验证：makepad-html 默认测试集通过；扩展集通过；新增回归涵盖匿名表格、编辑/样式更新、节点释放、普通换行对照及 SVG 颜色。
提取前 Robrix 集成检查已通过；提取后的验证记录见仓库根目录 `docs/extraction-validation.json`。
未进行 iOS/Android 真机或登录账号端到端验收。

**样本来源与范围**

- [doocs/md 默认主题](https://github.com/doocs/md/blob/cbcd3756e55d4982a37ff451753a69ce822e7a58/packages/shared/src/configs/theme-css/default.css)、[grace 主题](https://github.com/doocs/md/blob/cbcd3756e55d4982a37ff451753a69ce822e7a58/packages/shared/src/configs/theme-css/grace.css)、[渲染器](https://github.com/doocs/md/blob/cbcd3756e55d4982a37ff451753a69ce822e7a58/packages/core/src/renderer/renderer-impl.ts)：主题标题、代码、手工列表前缀、表格包装、脚注、内联 SVG。
- [Markdown Nice 基础样式](https://github.com/mdnice/markdown-nice/blob/6525a5aba371209c2840593e8f537b4a69137a4b/src/template/basic.js)、[语法示例](https://github.com/mdnice/markdown-nice/blob/6525a5aba371209c2840593e8f537b4a69137a4b/src/template/content.md)：列表内 section、注音、公式 SVG、横向图集及其 inline-block/nowrap 样式。
- [微信官方新增草稿 API](https://developers.weixin.qq.com/doc/service/api/draftbox/draftmanage/api_draft_add)说明正文接受 HTML、移除 JS，图片 URL 有平台来源限制。该页面没有提供可直接当作完整实现规格的逐标签、逐 CSS 属性清单。本次通过 HTTP 获取官方文档；浏览工具自身未能解析该地址。
- 一个公开公众号示例链接跳转到验证码，未取得正文。没有绕过验证，也没有把验证码页计入样本。

这 14 个文件是依据上述模式编写的回归探针，中文测试文案和图片校准图由本实验编写，不是从真实公众号完整导出的文章。12 号的部分 CSS 效果和 13 号定位/浮动是明确标注的探索性边界探针，未验证微信发布接受度。14 号测试宿主导入行为。它们不是“微信官方 HTML/CSS 全集”。

**如何测试**

- Blitz 固定版本 `e99fbdbd1d03b9f0aa1622c3f810d95daac92042`，Vello CPU，直接从相同 HTML 字节解析；不修改原文以迁就引擎。
- macOS 26.6.2 原生 WKWebView，非持久化数据存储，页面 JS 关闭；宿主测量代码读取 DOM 几何与字体/图片状态，并滚动分片截图。
- 两边宽度为 390 或 600、高度为 700 CSS px，DPR 2；声明相同的 PingFang SC 字体。仅提供测试清单中的本地资源快照，真实图片均校验可读取，不以资源下载失败代替渲染结果。
- `media` 构建启用 `blitz-dom/woff,image/gif`；`extended` 进一步启用 `blitz-paint/svg,blitz-dom/floats`。后者的依赖也启用了 WebP 解码。生产集成应显式声明所需格式，避免依赖传递特性的偶然开启。
- 共 28 个样本/尺寸组合：WKWebView 28 个、extended Blitz 28 个完成截图；media Blitz 26 个完成，浮动边界样本两个尺寸均超时。完成截图不代表兼容通过。
- 超时阶段已加日志确认：发生在调用现有 `makepad_html::render_html` 的产品入口检查阶段，尚未进入后面的 raw-document 对照。它不是 WKWebView 卡住，也不是图片 404；启用 floats 后同样的入口和原始引擎渲染均能完成。
- 提供节点边界差、原始截图和内容区域像素差；不做位移对齐，也不把白色背景计入所谓“高相似度”。字体光栅化、字形位置也会影响像素差，因此没有把它转换成 9/10 分数。
- 实际解码探针用于判断图片格式；`image::ImageFormat::can_read()` 只报告库是否认识该格式，不代表本次构建启用了对应解码器。

**实测结果**

以下“扩展构建”均指实验构建，并非已经改变 Robrix 的生产准入策略。

| 样本 | 结果 | 应修改的位置 |
|---|---|---|
| 中文正文、混排 | 段落可见；两端对齐与换行有差异，行内背景圆角和上下标不一致 | Blitz inline layout、Parley 字体/行盒、文字绘制 |
| display:table 标题 | 严重：文字消失，只剩很小的背景；手机宽度最大探针边界差约 133.5px | Blitz 匿名表格盒生成、表格内文本布局 |
| 嵌套列表 | 本组块级边界一致，项目符号与编号基本正确；文字像素仍不同 | 保留为回归基线，继续做字体/排版校准 |
| 表格 | rowspan 区域出现不该有的横线、文字未正确居中；混合边框未保留 | 表格网格/跨度、折叠边框冲突解析与绘制 |
| 代码块 | 文字和高亮可见，旧式 `-webkit-box` 的行盒/尺寸与 WebKit 不同 | 导入兼容转换或 legacy display 适配，inline/pre 布局 |
| PNG/JPEG/GIF/WebP | 扩展构建均显示；图片组最大边界差 0.75px，裁剪、圆角与阴影接近 | 产品资源授权与显式解码特性；继续测动画和异常资源 |
| 链接、脚注 | flex 脚注基本成形；链接边框、sup 和 vertical-align 有差异 | 行内盒边框、基线定位 |
| 横向图集 | 严重：三张横排图片被排成纵向，390px 组最大探针差 700px | inline-block 的 nowrap/换行/溢出处理；随后接横向滚动事件 |
| 属性式静态 SVG | 启用 SVG 后路径、渐变和描边恢复；后续文字位置仍相差约 8px | SVG replaced element 的基线/行盒 |
| SVG CSS | 内部样式能部分生效，但 HTML 父级的 currentColor 变成黑色 | Stylo 计算样式到 SVG 树的继承桥接 |
| ruby/rt、sup/sub | 严重：注音排在汉字旁，上下标没有正确基线位移 | Ruby 布局及行内 vertical-align/基线 |
| 渐变、裁剪、变换 | 大部分形状可见；text-shadow 缺失，圆角边框组合需补测 | blitz-paint 文字阴影、行内/圆角边框 |
| float/absolute 边界 | 无 floats 构建超时；启用后浮动可渲染，但 absolute 相对错误祖先，偏移 36px | 特性配置、布局终止条件、containing block 选择 |
| data-src 图片 | 两边都不自动加载；单纯传原始 DOM 不足以展示微信懒加载图片 | 共享导入层解析/授权资源后转换，不应靠任意脚本 |

点击对照页可以看到每个结论对应的原始图。SVG CSS 和图集尤其说明：元素存在、尺寸接近或进程正常退出，都不能证明视觉兼容。

[coverage.json](coverage.json)枚举了探针实际出现的 43 种标签（含 HTML 文档包装及 SVG 标签）和 48 种内联 CSS 属性；这只是本轮覆盖库存，不表示每种属性的全部取值和组合已测完。

**建议修改路线**

1. **先定义可验收的文章格式与导入层。** 在共享的 article 层新增导入模块，提取正文、保留嵌套元素与受支持的内联样式，把资源 URL 转为宿主授予的资源句柄；处理 data-src、相对路径、尺寸/比例及缺图状态。保留原始 HTML 和导入诊断。微信的发布清洗规则与本地渲染能力分别记录，不能拿 WebKit 能显示当作微信接受该内容的证据。
2. **扩展文档模型。** 现有 `crates/article-core/src/document.rs` 的 BlockKind/Mark 只能表达少量段落、标题、列表和图片，不能无损承载嵌套 section、CSS、table、SVG 和 ruby。加入带样式的结构节点、表格跨度、资源引用、不可编辑但可保留的富内容块与版本迁移。将编辑友好的语义模型与保留样式的导入树关联，避免一次保存就丢掉格式。
3. **落实已验证的配置能力。** 在 `Cargo.toml` 中建立明确的文章功能配置，显式启用经过验证的解码器、SVG、floats。扩展 `ResourceMap` 的受控资源类型与错误报告，而不是开放任意 HTTP、文件或账号能力。SVG 需专门校验/资源限制；当前产品 preflight 仍拒绝 svg，不能只删拒绝列表就称为支持。
4. **修复引擎核心缺口。** 优先顺序是丢失内容、布局错误、装饰精度：display:table 匿名盒 → nowrap 图集 → table rowspan/border-collapse → ruby/sup/sub → SVG 样式继承 → 行内边框、text-shadow、文字度量。对应上游位置见下表。每个修复把当前 fixture 作为回归，并补对应 WPT/最小案例。
5. **接入持久 DOM 和原生事件。** `src/makepad.rs` 目前只把整页位图放进 ScrollYView。需要保留文档状态，接 hit-test、滚轮/触摸、嵌套滚动、链接动作、选择、可访问性与动画时钟；长文采用可见区域分块绘制。仅重画一张图无法实现滑动图集、动态 GIF 或交互 SVG。
6. **单独适配微信专有能力。** 音视频、公众号资料卡、小程序/商品卡不是普通标签渲染问题。定义宿主组件与受控动作；在 Robrix 与 OctoSense 各自实现账号/资源操作，文章和 Octoscript 只持有能力句柄。不要把 Matrix 凭据交给 HTML 或 mini-app。
7. **最后做实际微信验收。** 收集明确可使用的发布后 HTML/资源快照与 iOS、Android 微信截图，覆盖多个主题、字号、暗色、长文和动画/交互状态。当前 macOS WKWebView 是有用的渲染参考，不等于所有微信客户端。未通过这个阶段，不宣称“完全支持”或“9/10”。

| 上游模块（固定版本中的路径） | 具体工作 |
|---|---|
| `packages/blitz-dom/src/layout/construct.rs`、`layout/table.rs` | 匿名表格结构、标题文本、跨度和表格尺寸 |
| `packages/blitz-dom/src/layout/inline.rs`、`font_metrics.rs` | nowrap、inline-block、ruby、上下标、中文行盒与基线 |
| `packages/stylo_taffy/src/convert.rs` 与布局上下文 | display 兼容、absolute containing block、浮动相关行为 |
| `packages/blitz-dom/src/layout/construct.rs`、`node/svg.rs`、`util.rs` | 当前将 SVG outerHTML 单独解析，需接入继承的计算样式和更新失效逻辑 |
| `packages/blitz-paint/src/text.rs`、`render/border.rs` | text-shadow、行内装饰、圆角非均匀边框、表格边框绘制 |
| `packages/blitz-dom/src/net.rs` 与宿主资源层 | GIF/图片动画解码、资源报告；现有 ImageReader 路径只转为一张 RGBA 图 |
| `packages/blitz-dom/src/events/*` 与 Makepad adapter | 事件转发、滚动链、选择、焦点与增量重绘 |

上游 [CSS 状态表](https://blitz.is/status/css)与[元素状态表](https://blitz.is/status/elements)可用于选题，但不能替代固定版本实测。例如状态页称字体族别名尚不支持，而当前固定源码已经有 `FontFaceOverrides`；不应据此重复实现或把文字差异直接归咎于该项。

**验收建议**

将兼容等级定义为可测试条件：资源全部可解释地加载或回退；没有丢字、丢图、错误排列或超时；主要块边界达到约定误差；文字换行与基线正确；关键控件/滑动状态与参考一致。背景比例很大的全图像素匹配不能用于掩盖局部缺陷。可以把当前样本继续扩成版本化集合，但需要持续保留未知和未测项目。

建议首先交付“静态文章阅读兼容集”，再加入“图集、GIF、音视频与卡片交互集”；两者各自报告通过率，保留每个失败案例。编辑器的导入—编辑—保存—再次渲染也要作为独立往返测试，防止阅读正确但保存后丢样式。

**复现**

从仓库根目录运行，需 Rust 1.98、Swift、Python 3、Pillow 和 NumPy：

```sh
# 重建原始基线时使用隔离的上游构建；它们不会加载 vendor 补丁。
python3 lab/wechat-corpus/build.py media
python3 lab/wechat-corpus/build.py extended
swiftc lab/comparison/html5_webview.swift -o target/html5-capture
python3 lab/wechat-corpus/run.py

# 保留基线，单独捕获修复版。
python3 lab/wechat-corpus/build.py patched
python3 lab/wechat-corpus/run.py --patched
python3 lab/wechat-corpus/analyze.py
open lab/wechat-corpus/index.html

cargo +1.98.0 test --locked --manifest-path Cargo.toml
cargo +1.98.0 test --locked --manifest-path Cargo.toml --features blitz-dom/woff,image/gif,test-svg,blitz-dom/floats
```

`build.py` 支持 CARGO_TARGET_DIR；原始基线的临时独立清单固定相同 git revision，但移除本地 Cargo patch。`run.py` 会复用 SHA-256、宽高相同的 WKWebView 参考截图；更换系统/WebKit 后应先移走 evidence 目录再重新采集。每个 Blitz 子进程限制 15 秒；超时作为失败保留，不能仅设置线程等待超时后继续留下失控渲染线程。

本轮变更包含引擎补丁、Cargo 接入、回归测试及对照报告。没有修改 Makepad 本体，没有放宽 Robrix 生产入口，也没有将静态截图冒充可交互的公众号页面。
