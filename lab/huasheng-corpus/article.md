# 把周末还给山野 · Field Notes

这是一篇用于检验公众号排版器**实际导出结果**的测试文章。中文与 English 混排，观察换行、标点、字重与留白。它不是已发布公众号文章的抓取。

![单张封面](ASSET_PNG)

## 从一段小路开始

清晨走出城市，让脚步跟上风的节奏。**加粗的重点**、*轻柔的强调*、~~删除的文字~~以及[保留样式的链接](https://example.com/article)，都应该能在文章中读清楚。

> 好的排版，让每一段文字都有呼吸的空间。
>
> 引用中的 **重点** 与第二段文字，检查继承和行间距。

### 两张图片并排

![PNG 插图](ASSET_PNG)
![JPEG 插图](ASSET_JPG)

接下来是三个格式的图集，用于检查导出的表格、图片尺寸与居中。

![GIF 插图](ASSET_GIF)
![WebP 插图](ASSET_WEBP)
![PNG 插图](ASSET_PNG)

### 出发前的小清单

- 第一项包含 **重点** 和[列表链接](https://example.com/list)。
  - 嵌套项目：水、地图和相机。
  - 嵌套项目：慢慢走，不赶路。
- 第二项包含行内代码 `render(article)`。

1. 保存文章。
2. 检查预览和资源。
3. 发布前完整阅读。

#### 数据表格

| 项目 | 格式 | 说明 |
| :--- | :---: | ---: |
| 中文正文 | HTML | 自然换行 |
| 插图 | PNG / JPEG | 比例与留白 |
| 图集 | GIF / WebP | 表格内居中 |

##### 代码与空白

```javascript
const title = "山野来信";
function render(article) {
  return article.title + " · " + title;
}
```

###### 最后的一点留白

正文里的 `inline code` 不应改变整段的行距。数学 x<sup>2</sup> 与化学 H<sub>2</sub>O，以及 <ruby>微信<rt>wēi xìn</rt></ruby> 用于观察行内排版。

---

把生活写下来，也把留白留给生活。THE END · 完整文章结束标记。
