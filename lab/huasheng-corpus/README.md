# 花生编辑器实际导出：Blitz / WKWebView

2026-09-21。打开 [交互报告](index.html) 查看 20 个主题、390/600 CSS px、2× DPR 的全文并排截图及像素差图。

本轮完成全部 40 组测试。WKWebView 40/40 完成，Blitz 36/40 完成；**这不是兼容通过率**。`ando-concrete` 和 `lemonde` 在两个宽度均触发 CPU 滤镜后端 panic。未绕过滤镜、修改输入 HTML 或用其他引擎替换失败截图。

## 实际运行的内容

- 固定 [alchaincyf/huasheng_editor](https://github.com/alchaincyf/huasheng_editor/tree/3c69a5a106737f439fe30430b12e6f4b50de66b2)，使用未经修改的 `styles.js`、`app.js`，保留上游 MIT 许可证。
- 在独立非持久 WKWebView 中加载真实 Vue 3.4.15、markdown-it 14.0.0，执行原有 `mounted()`、`renderMarkdown()` 和 `copyToClipboard()`。拦截剪贴板降级函数的输出，**不读写用户系统剪贴板**。不加载官网页面的统计或广告资源。
- 输入为 [统一测试文章](article.md) 和既有校准图片，覆盖六级标题、正文、强调、链接、引用、嵌套列表、代码、数据表、单图、两列/三列图集、PNG/JPEG/GIF/WebP、上下标和注音。**这是编辑器真实生成的输出，不是已发布微信公众号文章的抓取。**
- 代码高亮使用上游允许的 `escapeHtml` 回退；原页面声明的 `https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/es/highlight.min.js` 本次检查返回 HTTP 404。本轮不声称验证代码语法着色。
- 保存 `previews/`（预览片段）、`exports/`（原始导出片段）、`fixtures/`（只添加文档外壳及 body margin:0）。导出片段本身逐字节保留，两引擎读取同一份 fixture。主题字体声明保持原样，没有强制替换为 PingFang 来掩盖回退字体差异。
- 两个渲染器均不执行文章脚本。WKWebView 从仅服务固定样本的 loopback 服务加载。Blitz 使用固定资源快照；data URL 图片和 CSS 背景资源也映射到相同原始字节。未调用公开网络加载文章资源。
- Blitz 是仓库当前补丁的原始引擎诊断构建，启用 GIF、SVG、float 等实验特性，使用 Vello CPU。它不等于 Robrix 产品入口；产品仍要求宿主授权资源，且资源格式准入不同。`production_admission` 仅是空资源表下调用现有产品入口所得结果，不能证明产品图片导入完成。
- GIF 本轮只验证静态帧/解码，没有验证动画、触摸交互或 iOS/Android 微信客户端。

## 发现

| 类别 | 证据 | 影响 |
|---|---|---|
| 引擎崩溃 | `ando-concrete` 的 `filter:grayscale(20%)`、`lemonde` 的 `filter:sepia(10%)`，两种宽度均在 `PHASE paint` 以 101 退出；panic: `Other filter primitives not yet implemented` | 当前 Vello CPU 路径不能承接这些滤镜，必须修复后再谈主题支持 |
| 文字背景裁剪 | `gaudi-organic` 标题在 Blitz 中出现整块渐变背景，WebKit 中没有该矩形背景 | `background-clip:text` 缺口 |
| 渐变边框 | `gaudi-organic` 的引用框在 WebKit 中有渐变边框，Blitz 中缺失 | `border-image` 绘制缺口 |
| 中文与行内排版 | `wechat-ft` / `gaudi-organic` 的中文字体、换行，以及默认主题的中文斜体、链接下边框存在明显差异 | 需要校准字体回退、合成斜体、行内边框与排版 |
| 图片与表格 | 默认主题封面在 WebKit 中保持更大的固有尺寸并横向溢出，Blitz 中收缩；图集和后续块也有位移 | 要检查替换元素尺寸和表格布局，不能把收缩当成更兼容 |
| 上游导出改变内容 | 20 个主题均从 1 个嵌套列表变成 0 个，列表内链接从 1 个变成 0 个；见 `corpus.json` | 这是编辑器导出行为，不能归因于 Blitz |
| 上游导出删样式 | 默认、晚点、金融时报等导出片段中的封面 `max-width:100%` 被删除；原预览中仍有该属性 | 应保留导出原文比较，同时另行修复编辑器转换逻辑 |

成功捕获的主题中，全文高度差最大 84 CSS px；已测元素边界最大差 119.703 CSS px（`warm-dossier`、390px、pre）。这些只是几何测量，不代表全部视觉误差。

WKWebView 240/240 张图片完成解码。Blitz 成功的 36 组中没有资源拒绝，PNG/JPEG/GIF/WebP 实际字节解码探针成功。另对两个引擎全部成功截图里的 **456 个图片区域**检查校准颜色像素，确认图片实际绘制，避免仅凭下载成功判断。

## 结果和复现

- [来源、HTML SHA-256 和导出前后清单](corpus.json)
- [全部测量](results.json) / [汇总](summary.json)
- [资源、原文和实际图片绘制核验](validation.json)
- [报告界面加载核验](report-validation.json)：20 主题、两宽度、并排及可用差异图；崩溃样本禁用差异图，保留失败提示与 WebKit 截图。

在仓库根目录运行：

```sh
python3 lab/huasheng-corpus/prepare.py
python3 lab/wechat-corpus/build.py patched
swiftc lab/comparison/html5_webview.swift -o target/html5-capture
python3 lab/huasheng-corpus/run.py
python3 lab/huasheng-corpus/verify.py
python3 lab/huasheng-corpus/report.py
swiftc lab/huasheng-corpus/viewer.swift -o target/huasheng-report-viewer
target/huasheng-report-viewer "$PWD/lab/huasheng-corpus"
```

需要 macOS、Xcode command line tools、Rust 1.98、Python Pillow/numpy。首次准备会下载固定上游源码和版本化 JS 依赖；后续文章渲染使用离线资源。可用 `run.py --only wechat-default` 重测单主题。

为容纳 38–43KB 的完整编辑器导出，诊断工具的输入上限从 16KB 调整到库现有的 256KB 上限；像素、全文高度和资源预算保持原值。本轮没有修改渲染引擎，也没有将这些缺口标记为已修复。
