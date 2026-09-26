# makepad-html

[English](README.md) | 简体中文

为 Makepad 应用提供可复用的原生 HTML/CSS 渲染。独立的 Rust 核心负责文档的布局与绘制；可选的 `HtmlView` 控件以原生滚动方式显示渲染结果。应用负责提供 HTML、资源字节、视口尺寸以及生命周期决策。

本仓库负责渲染 API、Makepad 适配层、独立查看器、Blitz 补丁和兼容性实验室。Robrix 的文章编辑器是其中一个使用方。参见[架构与职责](docs/architecture.md)。

经过测试的引擎是 [Blitz e99fbdbd](https://github.com/DioxusLabs/blitz/tree/e99fbdbd1d03b9f0aa1622c3f810d95daac92042)，而不是 WebView：html5ever → Stylo → Taffy/Parley → AnyRender/Vello CPU → RGBA。这次初步集成在渲染时保留输入的 HTML/CSS；HTML 编辑以及无损保留样式的导入仍是单独的后续工作。

```rust
use ::makepad_html::{render_html, RenderOptions, ResourceMap};

let mut resources = ResourceMap::default();
// Bytes have already been selected/authorized/downloaded by the host.
let stylesheet_url = resources.insert_css("theme.css", "p { color: #337b60 }")?;
let html = format!("<link rel='stylesheet' href='{stylesheet_url}'><p>你好，世界</p>");
let bitmap = render_html(&html, RenderOptions::default(), &resources)?;
assert_eq!(bitmap.rgba.len(), bitmap.width as usize * bitmap.height as usize * 4);
# Ok::<(), makepad_html::RenderError>(())
```

请在工作线程上运行 `render_html`。宿主在展示结果之前，需要确认文档以及相关的资源授权仍然有效。`ResourceMap` 是一份不可变的授权快照，而不是持久的权限令牌。`DocumentSession` 会一直持有这份快照，直到宿主释放该会话。权限或账号发生变化后，请重新构建资源表。切勿把访问令牌、cookie 或带签名的远程 URL 放进文档的 HTML/CSS 或资源标识符中。

## 资源边界

只有宿主插入的、位于 `https://makepad-html.invalid/assets/<id>` 之下的精确 URL 才能被解析。PNG/JPEG 图片在准入之前会在限定范围内解码；CSS 必须是 UTF-8 且有大小限制。相对引用会解析到这一命名空间内。未映射的 URL，包括 HTTP(S)、`file:`、`data:`、CSS `@import`、图片/背景 URL 以及 `@font-face` URL，都会得到空响应，不发生任何 I/O。必须把被拒绝的请求也以响应完成，否则被拒绝的样式表可能让上游无限期等待。

没有 `blitz-net`、请求客户端、导航集成、剪贴板集成，也没有 JavaScript 包。主动元素和子文档元素（`script`、`iframe`、表单、object/embed）以及 SVG 和 MathML 都会被拒绝。文档按标准模式 HTML 解析。事件属性在本渲染器中不起作用；**它不是可用于后续浏览器场景的 HTML 净化器**。

默认的 `system-fonts` 特性会有意启用操作系统字体的发现与加载，从而在 Apple 平台上支持 `font-family: "PingFang SC", system-ui, sans-serif`；这与经文档授权的文件加载是两回事。`--no-default-features` 会关闭系统字体发现，但目前这一初版 API 不提供自定义字体注册接口，文字覆盖范围因此受限。

预算：HTML 256 KiB；保守的 token/深度预检（16,384 个 token，64 个显式开始标签）；最多 48 个已授权资源，每个 8 MiB，合计 24 MiB；每个 CSS 资源 64 KiB；图片最大 4096 × 4096，解码分配上限 64 MiB；128 次资源请求；8 轮解析；输出最多 16,777,216 像素。输出尺寸上限为 16,384 像素，低于 Vello CPU 的 16 位尺寸限制。过长的内容会报告 `clipped`；宿主必须展示这一状态，或改用未来的分页/分块实现，而不能把裁剪后的结果悄悄当作完整文档。

这些限制约束的是输入、已授权资源和输出分配。它们**不**约束 Stylo/Taffy/Vello 的全部中间分配，也不提供可取消的 CPU 时限。工作线程能让 UI 保持响应，但不等于进程隔离。不要声称这个 beta 引擎已针对任意恶意 HTML/CSS 做过加固；在大范围部署之前，导入不可信的公开内容需要单独受监管的进程和资源控制。

## Makepad 适配层

启用 `features = ["makepad"]`，在注册 Makepad 基础控件之后注册 `makepad_html::makepad::script_mod(vm)`，然后实例化 `mod.widgets.HtmlView`。在 Rust 作用域中引入 `makepad_html::makepad::HtmlViewWidgetRefExt`：

```rust,ignore
ui.html_view(cx, ids!(html_preview)).set_rendered(cx, &bitmap);
// On logout, grant revocation, or document replacement:
ui.html_view(cx, ids!(html_preview)).clear(cx);
```

Makepad 也把它内置的解析器重新导出为 `makepad_html`。使用
`use makepad_widgets::*` 时，请用 `::makepad_html` 引入这个外部 crate，
或者给它设置一个 Cargo 依赖别名（Robrix 使用 `makepad-html-renderer`）。

如果接收者是 `Widget`/`RefMut<Widget>` 而不是 `WidgetRef`，请改为引入
`HtmlViewWidgetExt`。

适配层把 RGBA 转换为 Makepad 的 `VecBGRAu8_32`，在带裁剪的原生滚动视图中显示结果，不使用 WebView。本 crate 的 lockfile 将 Makepad 固定在 `47837267faf6970a6cc36acedf9f83846b277307`，与 Robrix 使用相同的来源/分支，以避免出现重复的控件类型。宿主应按测得的视图宽度和当前 DPI 渲染；视图宽度变化时，在宿主重新渲染之前只会缩放现有位图。

适配层会发出文档坐标系下的点击事件，以及水平方向的滚轮/触控板事件。
在工作线程上保留一个 `DocumentSession`，调用 `activate` / `scroll_horizontal`，
状态变化后再调用 `render`。`HtmlAction::OpenLink` 只是发给宿主的请求；
不会自动打开浏览器、发起 HTTP 请求或进行导航。请把 `ScrollTo` 转发给
`HtmlViewRef::scroll_to`。独立查看器演示了这一生命周期，包括滚动后的链接、
页内片段跳转、details 展开/收起以及嵌套的水平滚动容器。宿主替换文档或撤销授权时，
请释放会话并清空控件；丢弃过期的工作线程结果。

目前尚未提供文字选择/复制、键盘链接焦点、无障碍文本和富文本编辑。
渲染和纹理上传仍然整张替换位图；这不是分块渲染器。

## 复现

本 crate 有自己的 workspace/lockfile，因此可以独立于 Robrix 构建。运行时测试使用 aarch64 macOS 上的 Rust 1.98.0。在关闭默认特性的情况下，锁定依赖的构建检查也在 Rust 1.94.0 上通过。

```sh
cargo +1.98.0 test --locked
cargo +1.98.0 test --locked --features test-svg,blitz-dom/floats
cargo +1.98.0 run --locked --example render_fixture -- target/render-evidence
cargo +1.98.0 run --locked --features makepad --example viewer

# View a host-selected document. Resources are explicit ID=PATH grants.
cargo +1.98.0 run --locked --features makepad --example viewer -- \
  page.html theme.css=./theme.css logo.png=./logo.png

# macOS: verify the native widget, screenshot OCR and scrolling.
python3 lab/verify_native.py target/debug/examples/viewer
```

原生验证脚本只启动隔离的 fixture 可执行文件，使用自有的 loopback 桥接，截图并用 OCR 检查中文文字和表格，滚动原生视图，然后退出该进程。它不会连接 Matrix 账号。`MAKEPAD_HIDE_WINDOWS=1` 可让验证过程不出现在用户屏幕上。

证据与局限见 `lab/README.zh-CN.md`。测试证明的是本地行为，而不是微信 9/10 的视觉评分。上游仍处于 beta 阶段，CSS 支持并不完整：[上游状态](https://blitz.is/status/css)。

## 兼容性实验室

[源自微信的 CSS 用例](lab/wechat-corpus/README.md)是其中一套兼容性测试，
包含原始来源哈希、固定版本的上游与打过补丁的 Blitz 截图，以及真实
WKWebView 参考截图。[HTML5 对照](lab/comparison/README.zh-CN.md)
覆盖通用 HTML。两套测试都不依赖文章编辑器。

引擎补丁由本仓库维护，位于 [vendor/blitz](vendor/blitz/README.makepad-html.md)。
使用方直接依赖本 crate；不需要 Cargo patch 覆盖，也不需要 Robrix 的检出。
该控件显示的是一张位图，可选地由持久的离线文档支撑。
选择、键盘/无障碍集成、动画以及更完整的手势路由仍在路线图中。

## 来源

提取自 `OctoSense-org/robrix2` 的 `wechat-ui` 渲染器工作，基于 Robrix
提交 `7f24f14ac5c59f65b84f078944443e3977c9f6f0` 以及经过评审的 CSS 修复。
保留了原有的许可证声明。Blitz 源码来源和确切的本地差异记录在
`vendor/blitz/UPSTREAM.json`、`wechat-css-1.patch`
以及后续的 `table-2.patch`、`text-shadow-3.patch` 和 `inline-4.patch` 中。

表格对齐轮次修复了合并单元格边框、边框冲突和单元格对齐。
默认 27 项 / 扩展 29 项测试通过，并保持相同的生产资源策略。参见[实测结果与剩余差距](docs/table-parity.md)。

文字阴影轮次增加了偏移、模糊、多重阴影、继承颜色以及文字装饰阴影。
它启用了 Vello CPU 的 `filters` 特性；测试所用的后端采用单线程渲染（当上游的
`multithreading` 特性被统一启用时，上游会禁用 filters）。这并不代表已支持通用的 CSS
filter 链。参见[对照结果与限制](docs/text-shadow-parity.md)。

行内/交互轮次增加了水平 HTML ruby 注音、sup/sub 以及嵌套的长度/百分比偏移，
修正了原子行内盒的基线，保留了 span 之间的空格，并加入由工作线程持有的文档交互。
Parley 0.11.1 与 Blitz 一同 vendored，使下游应用获得相同的布局补丁。
参见[测量、原生证据与剩余限制](docs/inline-parity.md)。
