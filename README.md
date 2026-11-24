# 头马公众号推文排版

把一篇头马推文排成能直接贴进公众号编辑器的版式：正文 14px，标题 20 / 18 / 16 / 14px，行间距 1.8，字间距 2，段落间距 8，页边距 8，图片和文字之间空一行，文末带作者、编辑和尾图，英文人名统一成 Anita LUO 的格式，用头马官方的蓝、酒红、灰、黄。

它只排版，不改你的文字，也不会登录或发布你的公众号。

## 安装

把这句话发给支持 Skill 的 AI 助手（WorkBuddy、Claude Code、Codex 等）：

> 请从 https://github.com/FelixMaofei/toastmasters-wechat-layout 安装仓库根目录的 `toastmasters-wechat-layout` Skill 到当前工具支持的 Skills 目录。若已装同名且来自这个仓库的版本，请更新。

手动安装：在 GitHub 点 **Code → Download ZIP**，解压后把含有 `SKILL.md` 的那一层文件夹命名为 `toastmasters-wechat-layout`，放进你用的工具的 Skills 目录，重新打开对话。

需要电脑上有 Python 3（Mac 一般自带）。没有也能用，助手会照着说明手写排版，只是慢一些。

## 使用

把稿子和图片放在同一个文件夹，对助手说：

> 请用 toastmasters-wechat-layout 把这篇推文排成公众号版式。作者是 Anita LUO，编辑是 xxx，尾图用 images/尾图.png。

助手会：

1. 把稿子整理成带标题分级的源稿；
2. 统一英文人名格式，拿不准的会问你；
3. 生成一个 HTML 文件，打开就是手机预览。

## 贴进公众号

1. 打开生成的 HTML，点「复制标题」，贴到公众号标题栏。
2. 点「复制正文（含图片）」，贴进正文。图片会自动上传到公众号，等几秒，图片都显示出来再保存。
3. 万一有图片没传上去，删掉那张，在原位置重新上传。
4. 公众号里点「预览」，用手机看一遍再保存。

页面上还有一个「复制正文（图片留位）」：每张图的位置换成一行黄色提示，方便你自己逐张上传，作为备用。

## 先试一下

`examples/示例推文.md` 是一篇虚构的示例。对助手说「用这个 Skill 排一下示例推文」，或者自己运行：

```bash
python3 scripts/build_wechat_html.py examples/示例推文.md
```

然后打开 `examples/示例推文-公众号排版.html`。

## 想改样式

字号、颜色、间距都在 `assets/theme.json`。直接告诉助手想改什么，比如“标题换成深一点的红”，它会另存一份设置，不动默认值。
