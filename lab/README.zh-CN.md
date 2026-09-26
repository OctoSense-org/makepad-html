# 原生 HTML 集成验证

[English](README.md) | 简体中文

本集成为独立宿主提供原生 HTML/CSS 文章预览。它不是把 Robrix 迁移到 Dioxus，不是 OctoSense 的运行时依赖，也不是对任意 HTML 富文本编辑的实现。

来源：本仓库（`src/`）。引擎提交：`e99fbdbd1d03b9f0aa1622c3f810d95daac92042`。Makepad 提交：`47837267faf6970a6cc36acedf9f83846b277307`。独立的 lockfile 记录了所有已解析的依赖。运行时测试：Rust 1.98.0，aarch64 macOS。Rust 1.94.0 下的 `--no-default-features` 构建检查也已通过。

测试样例是原创的合成文章，不是抓取的微信页面。它们覆盖中英文（使用 PingFang SC 的 CSS 字体偏好）、行内强调、嵌套章节、图片资源授权、边框、背景、间距、CSS 变量、class/行内样式层叠、响应式媒体规则、深色模式以及一个基础表格。它们是有用的集成证据，但不是微信兼容性基准。

生成的证据：

- `evidence/mobile-light.png`：390 CSS px，2× 渲染。
- `evidence/desktop-light.png`：760 CSS px，1× 渲染。
- `evidence/mobile-dark.png`：390 CSS px，2× 渲染，使用样例自带的深色主题 CSS。
- `evidence/native-top.png` 和 `native-bottom.png`：隔离 Makepad 窗口的真实截图，包括 Blitz 纹理的原生滚动。
- `evidence/render-results.json`：引擎版本、尺寸、资源决策和耗时。
- `evidence/native-validation.json`：原生可执行文件/图片哈希、窗口尺寸、OCR 断言和进程隔离检查。
- `validation.json`：最终的测试/检查结果和证据哈希。

渲染器测试套件通过像素检查 CSS 层叠/媒体查询变量、精确的内存内授权、被拒绝的远程/文件/data 资源、被阻止的嵌套导入、图片解码/显示、畸形资源、主动元素、输入/视口/深度限制、请求次数上限、长文章裁剪，以及中文响应式/深色样例。原生验证还会通过截图 OCR 检查真实的 Makepad 纹理路径和滚动行为。

已知边界：

- 该位图控件不支持 HTML 到可编辑文档的转换、导入样式的持久化 schema、文字选择或无障碍文本。
- CSS 深色模式基于样例自带的规则，并不声称能复现微信的自动深色配色转换。
- 没有 iOS 真机验证，也没有 Android/Windows/Linux 运行时验证。
- 不支持任意 SVG、动画组件或微信私有标签；不执行 JavaScript。
- 明确启用了系统字体发现；不捆绑分发 PingFang。
- 没有与真实微信截图的相似度测量，也不声称达到 9/10。
- 输出/资源预算并不构成 CPU 或进程沙箱。在接收任意公开文档之前，上游的中间分配和病态 CSS 仍需要更强的隔离。
- 超出位图预算的长文档会被明确报告为已裁剪；宿主必须显示这一状态。分块渲染是后续工作。

复现命令和宿主 API 见[仓库 README](../README.zh-CN.md)。未使用任何个人 Matrix 凭据、资料或账号。

Robrix 的可选 `article_blitz` 特性现在使用本渲染器来预览经过验证的
本地草稿。其集成检查、Palpo 生命周期检查以及真实的 Robrix
截图单独记录在 [Robrix 集成实验室](https://github.com/OctoSense-org/robrix2/tree/wechat-ui/lab/article-components)。

行内/交互轮次通过 `DocumentSession` 增加了原生链接、展开/收起、页内片段跳转
以及水平嵌套滚动。额外的检查是
`python3 lab/verify_interactions.py target/debug/examples/viewer`（需要 Pillow）。
它检查真实的指针输入、拖动抑制、展开/收起往返后的像素、
片段跳转 OCR、滚动后的链接，以及切换/点击水平幻灯片。
结果：[交互证据](evidence/interactions/native-validation.json) 和
[行内对照报告](../docs/inline-parity.md)。
