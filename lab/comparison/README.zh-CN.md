# DigitalOcean HTML：Blitz 与 macOS WKWebView 对照

[English](README.md) | 简体中文

打开[交互对照页](index.html)。其中有并排截图、桌面/窄屏视口切换、
同坐标擦除滑块、文字局部放大图和差异图。原始截图和 DOM 测量数据在 `evidence/` 中。
对照页、`evidence/` 和 `results.json` 由下文的复现步骤在本地生成；
它们被 git 忽略，不纳入版本库。

来源：[digitalocean/sample-html index.html](https://github.com/digitalocean/sample-html/blob/b658ada1c68912e9ac4026db63d687e8e2aa808a/index.html)，
提交 `b658ada1c68912e9ac4026db63d687e8e2aa808a`。
SHA-256：`96448c90c3ed0ede400f5f68d904201428bc730aa4355b3a4141f4c4c11071bc`。
两个引擎接收的是完全相同的 4,394 个原始字节。下载的源文件保存在被忽略的
`inputs/` 中；复现时会重新获取并校验固定版本。

## 方法

- 真实的 macOS 26.6.2 `WKWebView.takeSnapshot`，使用非持久数据存储，
  对比 Blitz `e99fbdbd` / Vello CPU 的像素输出，所用渲染器依赖与 Robrix
  相同。不改写 HTML/CSS，也不做图像配准/对齐。
- 视口：800×600 和 390×844 CSS 像素，均为 DPR 2、浅色外观。
  窄视口是 macOS WebKit，**不是** iOS 设备测试。
- 静态对照：关闭 WKWebView 页面 JavaScript。宿主诊断 JS
  等待 `document.fonts.ready`，读取计算样式和几何信息；
  它不修改文档。Blitz 没有 JS 引擎。
- 动态对照：原始 HTML 不做修改，开启 WKWebView 页面 JS。
  一个 document-start `WKUserScript` 把 `Math.random` 替换为带固定种子的 LCG，
  使颜色可复现。这是对测试环境的改动，不是对源码的改写。
  卡片/正文点击使用 DOM `.click()`，而不是原生指针事件。
- 生产入口 `makepad_html::render_html` 会以
  `unsupported active/document element: script` 拒绝这一原始页面。`compare_html.rs`
  是一条单独的诊断用原始引擎路径，没有可以加载资源的网络 provider。
  它让 script 元素保持惰性，并不放宽应用的准入策略。这些原始引擎截图的成功
  **并不**意味着 Robrix 能兼容原始源码。

## 结果

| 测量项 | Blitz | WKWebView |
| --- | ---: | ---: |
| 桌面卡片 x / y，CSS px | 268 / 240.5 | 266.8125 / 240.5 |
| 窄屏卡片 x / y，CSS px | 63 / 362.5 | 61.8125 / 362.5 |
| 卡片宽 × 高，CSS px | 264 × 119 | 266.359375 × 119 |
| 静态内容 | `#000000` | `#000000` |
| 加载时的页面 JS | 未执行 | `#20bc92` |
| JS 卡片点击 | 无 JS 运行时 | 保持 `#20bc92` |
| JS 正文点击 | 无 JS 运行时 | 变为 `#71da4e` |

两个视口出现了相同的静态几何差异。Flex 居中、100% 页面高度、CSS 变量、
内边距、rem 尺寸和静态颜色都能正确渲染。
两张卡片矩形的交并比为 99.114%。Blitz 的卡片窄 2.359375
CSS 像素；左边缘向右偏 1.1875 像素。虽然两个引擎报告的 y 坐标相同，
但观察到的 Blitz 卡片光栅起点低一个设备像素（DPR 2 下为 0.5 CSS 像素）。

任一 RGB 通道误差 >16/255 的像素占比：

- 卡片并集区域：两个视口均为 **4.762%**。
- 文字并集裁剪区域（含六个设备像素的边距）：**16.332%**。
- 整帧：桌面 0.315%，窄屏 0.460%。相同的黑色背景
  主导了这些整帧数字；它们不是有意义的整体保真度评分。
  文字裁剪区域显示出笔画/抗锯齿和字距差异。
  尚未把字体选择、字形整形和光栅化分别确认为原因。

`results.json` 包含矩形数值、绝对通道误差、裁剪边界、
来源与产物哈希，以及明确的测试限定条件。差异 PNG
把绝对 RGB 误差放大四倍以便观察。文字放大图对相同裁剪坐标使用 3× 最近邻
放大；原始截图均予保留。

结论：该样本的静态布局很接近，但存在可测量的字体排印和
像素对齐差异。其 JS 驱动的行为 Blitz 无法复现。
这一个简单的变色页面不涵盖文章图片、表格、复杂的微信
CSS、长文档或编辑，也不能据此得出 9/10 的兼容性评分。

## 复现

需要 macOS、Swift、Rust 1.98、Python 3、Pillow 和 NumPy。在仓库根目录运行：

```sh
cargo +1.98.0 build --locked --manifest-path Cargo.toml --example compare_html
swiftc lab/comparison/webview.swift -o target/html-comparison-webview
python3 lab/comparison/compare.py --render \
  --blitz-bin target/debug/examples/compare_html \
  --webview-bin target/html-comparison-webview
open lab/comparison/index.html
```

不带 `--render` 运行 `compare.py` 时，只会根据已有的原生截图
重新计算指标/合成图。页面的随机变色行为经过了测试，但任意页面
JS、外部资源、导航和 iOS 都不在本实验范围内。

本地文件输入、下载的第三方资源及其截图均被忽略（不纳入版本库）。
可复现的原创样例和已发布的截图位于 `../wechat-corpus/`。
