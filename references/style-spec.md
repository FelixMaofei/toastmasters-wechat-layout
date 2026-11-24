# 样式说明

脚本 `scripts/build_wechat_html.py` 生成的就是下面这些样式。没有 Python、需要手写 HTML 时照抄。所有样式都写在标签的 `style` 里，不用 `class` 和 `<style>`，因为公众号编辑器粘贴时会丢掉它们。

数值来自 `assets/theme.json`：正文 14px，行间距 1.8，字间距 2px，段后 8px，左右缩进 8px。

## 颜色

| 用途 | 色值 |
|---|---|
| 正文 | `#3F3F3F` |
| 引用、导语、署名文字 | `#555555` |
| 图注、链接网址 | `#7A7F80` |
| 头马蓝 Loyal Blue | `#004165` |
| 头马酒红 True Maroon | `#772432` |
| 头马灰 Cool Gray | `#A9B2B1` |
| 头马黄 Happy Yellow（只做线条点缀） | `#F2DF74` |
| 浅灰底 Fair Gray | `#F5F5F5` |
| 高亮底 | `#FBF3C4` |

## 正文段落

```html
<p style="margin:0 8px 8px;font-size:14px;line-height:1.8;letter-spacing:2px;color:#3F3F3F;text-align:justify;">正文</p>
```

## 空一行（图片前后）

```html
<p style="margin:0 8px;font-size:14px;line-height:1.8;"><br></p>
```

只加在图片和文字之间。两张图片相邻时不加，只靠段后 8px 分开。图注算图片的一部分，紧贴图片。

## 标题

按稿件里出现过的级别重新排：最高一级 20px，往下 18、16、14px。稿件从 `##` 开始也一样从 20px 起。

```html
<!-- 第 1 级 20px：酒红左竖线 + 头马蓝字 + 灰色下划线 -->
<h2 style="margin:28px 8px 14px;padding:0 0 8px 10px;border-left:5px solid #772432;border-bottom:1px solid #A9B2B1;color:#004165;font-size:20px;line-height:1.5;letter-spacing:2px;font-weight:bold;">一、标题</h2>

<!-- 第 2 级 18px：酒红字 + 黄色下划线 -->
<h3 style="margin:24px 8px 12px;color:#772432;font-size:18px;line-height:1.5;letter-spacing:2px;font-weight:bold;"><span style="border-bottom:3px solid #F2DF74;padding-bottom:2px;">标题</span></h3>

<!-- 第 3 级 16px：酒红竖块 + 头马蓝字 -->
<h4 style="margin:20px 8px 10px;color:#004165;font-size:16px;line-height:1.5;letter-spacing:2px;font-weight:bold;"><span style="color:#772432;">▍</span>标题</h4>

<!-- 第 4 级 14px：酒红字 -->
<h5 style="margin:16px 8px 8px;color:#772432;font-size:14px;line-height:1.5;letter-spacing:2px;font-weight:bold;">标题</h5>
```

## 行内

| 写法 | 效果 |
|---|---|
| `**文字**` | `<strong style="color:#772432;">` |
| `*文字*` | `<span style="color:#004165;">` |
| `==文字==` | `<span style="background-color:#FBF3C4;">` |
| `` `文字` `` | 浅灰底酒红字 |
| `[文字](公众号文章链接)` | 保留为链接 |
| `[文字](其他网址)` | 蓝字，后面用灰色小字写出网址（公众号不允许外链） |

## 图片和图注

```html
<p style="margin:0 8px 8px;text-align:center;"><img src="图片" alt="图注" style="max-width:100%;height:auto;vertical-align:top;margin:0 auto;"></p>
<p style="margin:0 8px 8px;font-size:12px;line-height:1.6;letter-spacing:1px;color:#7A7F80;text-align:center;">图注</p>
```

本地图片的 `src` 默认写成 data URI（`data:image/png;base64,...`）。这样复制正文时图片跟着进剪贴板，粘贴进公众号编辑器后由公众号自动上传。

## 引用

```html
<section style="margin:0 8px 8px;padding:10px 12px;background-color:#F5F5F5;border-left:3px solid #772432;">
<p style="margin:0;font-size:14px;line-height:1.8;letter-spacing:2px;color:#555555;text-align:justify;">引用内容</p>
</section>
```

## 列表

每一项是一个正文段落，前面加符号：无序用头马蓝 `•`，有序用酒红 `1.`。不用 `<ul>`、`<ol>`，因为公众号编辑器里列表样式不稳定。

## 分隔

```html
<p style="margin:20px 8px;text-align:center;font-size:12px;line-height:1.5;letter-spacing:8px;"><span style="color:#004165;">●</span><span style="color:#772432;">●</span><span style="color:#A9B2B1;">●</span></p>
```

## 开头（可选）

- **栏目条**：头马蓝底、白字、酒红下边线，14px 居中加粗。
- **导语**：浅灰底，头马蓝左竖线，14px 灰色字。

## 片尾

1. 三色圆点分隔；
2. 署名框：浅灰底，头马蓝上边线；每行「**标签｜**名字」，标签酒红加粗，默认顺序作者、编辑；
3. 空一行；
4. 尾图，和正文图片同样处理。
