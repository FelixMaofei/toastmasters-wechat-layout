#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头马公众号推文排版：把 Markdown 推文稿排成可粘贴到微信公众号编辑器的 HTML。

只用 Python 标准库（3.8+）。

用法：
    python3 build_wechat_html.py 稿件.md
    python3 build_wechat_html.py 稿件.md --out 输出.html --theme 我的主题.json
    python3 build_wechat_html.py 稿件.md --link-images    # 本地图片不嵌入（默认嵌入，粘贴进公众号时图片自动上传）
    python3 build_wechat_html.py 稿件.md --join-lines     # 按 Markdown 原生规则：空行才分段

运行后在标准输出打印一段 JSON 汇总（输出路径、标题、图片数、需要处理的提醒）。
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_THEME_PATH = SKILL_DIR / "assets" / "theme.json"

# 信息区（文件开头 --- 之间）支持的字段。左边是可以写的键，右边是统一后的名字。
META_ALIASES = {
    "title": "title", "标题": "title",
    "summary": "summary", "摘要": "summary",
    "lead": "lead", "导语": "lead",
    "column": "column", "栏目": "column",
    "end_image": "end_image", "尾图": "end_image",
    "end_image_caption": "end_image_caption", "尾图说明": "end_image_caption",
}
# 片尾署名。按信息区里出现的顺序排列。
CREDIT_ALIASES = {
    "author": "作者", "作者": "作者", "文字": "文字", "文": "文字",
    "editor": "编辑", "编辑": "编辑", "责编": "责编", "责任编辑": "责任编辑",
    "reviewer": "审核", "审核": "审核", "校对": "校对",
    "photo": "摄影", "photographer": "摄影", "摄影": "摄影", "图片": "图片",
    "layout": "排版", "排版": "排版", "翻译": "翻译", "策划": "策划",
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
IMAGE_RE = re.compile(r'^!\[([^\]]*)\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+["“](.*?)["”])?\s*\)\s*$')
HR_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
UL_RE = re.compile(r"^\s*[-*+•·]\s+(.*)$")
OL_RE = re.compile(r"^\s*(\d{1,2})(?:[.)）]\s+|、\s*)(.*)$")
QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
CJK = "\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f"

# 人名检查时跳过的常见头马、日常英文词。命中的只是“请确认”，不会自动改。
NAME_STOPWORDS = set("""
Toastmasters Toastmaster International Pathways Path Paths Level Levels Project Projects District Districts Division
Area Club Clubs Speech Speeches Contest Contests Table Topics Topic Evaluation Evaluations Evaluator Evaluators General
Master Masters Ceremonies Timer Grammarian Ah Counter Officer Officers President Vice Education Membership Public
Relations Secretary Treasurer Sergeant Arms Enhancement Program Programme Programs Leadership Excellence Award Awards
Distinguished Meeting Meetings Chapter Part Week Day Hall Fame Online Hybrid Super Lab Morning Night Evening The This
That These Those And With For From Our Your Their Welcome Dear Happy New Year Chinese English China Shenzhen Guangzhou
Beijing Shanghai Hong Kong Macau January February March April May June July August September October November
December Monday Tuesday Wednesday Thursday Friday Saturday Sunday Dynamic Innovative Planning Presentation Mastery
Persuasive Influence Engaging Humor Humorous Motivational Strategies Visionary Communication Communications Effective
Coaching Team Teams Collaboration Strategic Relationships Ice Breaker Feedback Research Present Introduction Vocal
Variety Body Language Connect Storytelling Understanding Style Styles Mentoring Mentor Mentors Ask Questions Question
Know Audience Gestures Zoom Tencent WeChat Book Books Reading Workshop Workshops Session Sessions Training Leaders
Leader Made Where Are Learning Learn Base Camp Basecamp Speaker Speakers Best Table Role Roles Theme Word Words
Conference Conferences Annual Spring Autumn Fall Winter Summer Chair Director Directors Manager Managers Ambassador
Ambassadors Coach Coaches Sponsor Mentorship Spotlight Champion Champions Final Finals Semi Round Elite Club's
Officer's Speaker's Level's Of In On At To As By Is It We You They He She His Her Our My Me Us A An Or But So Not
Thank Thanks Hello Hi Good Great Love Life Story Stories Live Show News Daily Weekly Monthly Special Guest Guests
""".split())
NAME_ACRONYMS = set("DTM PQC VPE VPM VPPR SAA TME GE TT TTM IE AI PR PPT PDF QR CEO HR DIY TM TI BBK BBKING OK".split())


def load_theme(path: Path | None) -> dict:
    theme = json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8"))
    if path:
        user = json.loads(Path(path).read_text(encoding="utf-8"))
        colors = dict(theme.get("colors", {}))
        colors.update(user.get("colors", {}))
        theme.update(user)
        theme["colors"] = colors
    return theme


def parse_front_matter(text: str):
    """读文件开头 --- 之间的信息区，返回 (meta, credits, 正文, 提醒)。"""
    meta, credits, warnings = {}, [], []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta, credits, text, warnings
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        warnings.append("信息区只有开头的 ---，没有结尾的 ---，已全部按正文处理。")
        return meta, credits, text, warnings
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"\s*([^:：]+?)\s*[:：]\s*(.*)$", raw)
        if not m:
            warnings.append(f"信息区这一行看不懂，已忽略：{raw.strip()}")
            continue
        key, value = m.group(1).strip(), m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].strip()
        meta_key = META_ALIASES.get(key.lower(), META_ALIASES.get(key))
        credit_label = CREDIT_ALIASES.get(key.lower(), CREDIT_ALIASES.get(key))
        if meta_key:
            if value:
                meta[meta_key] = value
        elif credit_label:
            if value:
                credits.append((credit_label, value))
        else:
            warnings.append(f"信息区的「{key}」不是支持的字段，已忽略。")
    return meta, credits, "\n".join(lines[end + 1:]), warnings


def join_text(parts):
    out = ""
    for part in parts:
        part = part.strip()
        if not out:
            out = part
        elif re.search(f"[{CJK}]$", out) or re.match(f"^[{CJK}]", part):
            out += part
        else:
            out += " " + part
    return out


def parse_blocks(body: str, join_lines: bool):
    blocks = []
    lines = body.splitlines()
    buf = []

    def flush():
        if buf:
            blocks.append(("para", join_text(buf)))
            buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        s = line.strip()
        if not s:
            flush()
            i += 1
            continue
        if HR_RE.match(s):
            flush()
            blocks.append(("hr",))
            i += 1
            continue
        m = HEADING_RE.match(s)
        if m:
            flush()
            blocks.append(("heading", len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        m = IMAGE_RE.match(s)
        if m:
            flush()
            src = m.group(2).strip().strip("<>")
            caption = (m.group(3) or m.group(1) or "").strip()
            blocks.append(("image", src, caption))
            i += 1
            continue
        if QUOTE_RE.match(line):
            flush()
            qlines = []
            while i < len(lines) and QUOTE_RE.match(lines[i]):
                qlines.append(QUOTE_RE.match(lines[i]).group(1).rstrip())
                i += 1
            paras, cur = [], []
            for ql in qlines:
                if not ql.strip():
                    if cur:
                        paras.append(join_text(cur))
                        cur = []
                elif join_lines:
                    cur.append(ql)
                else:
                    paras.append(ql.strip())
            if cur:
                paras.append(join_text(cur))
            if paras:
                blocks.append(("quote", paras))
            continue
        if UL_RE.match(line) or OL_RE.match(line):
            flush()
            kind = "ul" if UL_RE.match(line) else "ol"
            items = []
            while i < len(lines):
                cur_line = lines[i]
                mu, mo = UL_RE.match(cur_line), OL_RE.match(cur_line)
                if kind == "ul" and mu and not HR_RE.match(cur_line.strip()):
                    items.append([None, mu.group(1).strip()])
                elif kind == "ol" and mo:
                    items.append([mo.group(1), mo.group(2).strip()])
                elif items and cur_line.strip() and cur_line[:1] in (" ", "\t") and not (mu or mo):
                    items[-1][1] = join_text([items[-1][1], cur_line.strip()])
                else:
                    break
                i += 1
            blocks.append((kind, items))
            continue
        if join_lines:
            buf.append(s)
        else:
            blocks.append(("para", s))
        i += 1
    flush()
    return blocks


class Renderer:
    def __init__(self, theme: dict):
        self.t = theme
        self.c = theme["colors"]

    # ---------- 基础样式 ----------
    def text_style(self, size=None, color=None, align=None):
        t = self.t
        return (f"font-size:{size or t['body_size']}px;line-height:{t['line_height']};"
                f"letter-spacing:{t['letter_spacing']}px;color:{color or self.c['text']};"
                f"text-align:{align or t['text_align']};")

    def p_style(self, **kw):
        t = self.t
        return f"margin:0 {t['page_margin']}px {t['paragraph_spacing']}px;" + self.text_style(**kw)

    def blank_line(self):
        t = self.t
        return (f'<p style="margin:0 {t["page_margin"]}px;font-size:{t["body_size"]}px;'
                f'line-height:{t["line_height"]};"><br></p>')

    # ---------- 行内 ----------
    def inline(self, text: str) -> str:
        stash = []

        def keep(snippet):
            stash.append(snippet)
            return f"\x00{len(stash) - 1}\x00"

        blue, muted = self.c["loyal_blue"], self.c["muted"]
        text = re.sub(
            r"`([^`]+)`",
            lambda m: keep(f'<span style="background-color:{self.c["fair_gray"]};color:{self.c["true_maroon"]};'
                           f'padding:0 4px;border-radius:3px;">{html.escape(m.group(1))}</span>'),
            text)

        def link(m):
            label = self.basic(html.escape(m.group(1), quote=False))
            url = m.group(2)
            if re.match(r"https?://mp\.weixin\.qq\.com/", url):
                return keep(f'<a href="{html.escape(url, quote=True)}" style="color:{blue};'
                            f'text-decoration:underline;">{label}</a>')
            return keep(f'<span style="color:{blue};">{label}</span><span style="color:{muted};font-size:12px;'
                        f'letter-spacing:0;">（{html.escape(url, quote=False)}）</span>')

        text = re.sub(r"(?<!!)\[([^\]]+)\]\((\S+?)\)", link, text)
        text = self.basic(html.escape(text, quote=False))
        return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)

    def basic(self, s: str) -> str:
        maroon, blue = self.c["true_maroon"], self.c["loyal_blue"]
        s = re.sub(r"\*\*(.+?)\*\*", rf'<strong style="color:{maroon};">\1</strong>', s)
        s = re.sub(r"__(.+?)__", rf'<strong style="color:{maroon};">\1</strong>', s)
        s = re.sub(r"==(.+?)==", rf'<span style="background-color:{self.c["highlight"]};">\1</span>', s)
        s = re.sub(r"(?<![\*\w])\*(?![\s*])(.+?)(?<![\s*])\*(?!\*)",
                   rf'<span style="color:{blue};">\1</span>', s)
        return s

    # ---------- 块 ----------
    def heading(self, rank: int, text: str) -> str:
        t, c = self.t, self.c
        size = t["heading_sizes"][min(rank, len(t["heading_sizes"]) - 1)]
        pm = t["page_margin"]
        common = f"font-size:{size}px;line-height:1.5;letter-spacing:{t['letter_spacing']}px;font-weight:bold;"
        body = self.inline(text)
        if rank == 0:
            return (f'<h2 style="margin:28px {pm}px 14px;padding:0 0 8px 10px;border-left:5px solid {c["true_maroon"]};'
                    f'border-bottom:1px solid {c["cool_gray"]};color:{c["loyal_blue"]};{common}">{body}</h2>')
        if rank == 1:
            return (f'<h3 style="margin:24px {pm}px 12px;color:{c["true_maroon"]};{common}">'
                    f'<span style="border-bottom:3px solid {c["happy_yellow"]};padding-bottom:2px;">{body}</span></h3>')
        if rank == 2:
            return (f'<h4 style="margin:20px {pm}px 10px;color:{c["loyal_blue"]};{common}">'
                    f'<span style="color:{c["true_maroon"]};">▍</span>{body}</h4>')
        return f'<h5 style="margin:16px {pm}px 8px;color:{c["true_maroon"]};{common}">{body}</h5>'

    def para(self, text: str) -> str:
        return f'<p style="{self.p_style()}">{self.inline(text)}</p>'

    def quote(self, paras) -> str:
        t, c = self.t, self.c
        inner = []
        for k, p in enumerate(paras):
            mb = 0 if k == len(paras) - 1 else t["paragraph_spacing"]
            inner.append(f'<p style="margin:0 0 {mb}px;{self.text_style(color="#555555")}">{self.inline(p)}</p>')
        return (f'<section style="margin:0 {t["page_margin"]}px {t["paragraph_spacing"]}px;padding:10px 12px;'
                f'background-color:{c["fair_gray"]};border-left:3px solid {c["true_maroon"]};">'
                + "".join(inner) + "</section>")

    def list_block(self, kind, items) -> str:
        c = self.c
        out = []
        for n, (num, text) in enumerate(items, 1):
            if kind == "ul":
                mark = f'<span style="color:{c["loyal_blue"]};font-weight:bold;">•</span> '
            else:
                mark = f'<span style="color:{c["true_maroon"]};font-weight:bold;">{html.escape(num or str(n))}.</span> '
            out.append(f'<p style="{self.p_style()}">{mark}{self.inline(text)}</p>')
        return "".join(out)

    def divider(self) -> str:
        t, c = self.t, self.c
        return (f'<p style="margin:20px {t["page_margin"]}px;text-align:center;font-size:12px;line-height:1.5;'
                f'letter-spacing:8px;"><span style="color:{c["loyal_blue"]};">●</span>'
                f'<span style="color:{c["true_maroon"]};">●</span><span style="color:{c["cool_gray"]};">●</span></p>')

    def image(self, idx: int, src: str, caption: str, name: str) -> str:
        t, c = self.t, self.c
        pm, ps = t["page_margin"], t["paragraph_spacing"]
        alt = html.escape(caption or name, quote=True)
        out = (f'<p data-tm-img="{idx}" data-tm-name="{html.escape(name, quote=True)}" '
               f'style="margin:0 {pm}px {ps}px;text-align:center;">'
               f'<img src="{html.escape(src, quote=True)}" alt="{alt}" '
               f'style="max-width:100%;height:auto;vertical-align:top;margin:0 auto;"></p>')
        if caption:
            out += (f'<p data-tm-cap="{idx}" style="margin:0 {pm}px {ps}px;font-size:{t["caption_size"]}px;line-height:1.6;'
                    f'letter-spacing:1px;color:{c["muted"]};text-align:center;">{self.inline(caption)}</p>')
        return out

    def column_band(self, text: str) -> str:
        t, c = self.t, self.c
        return (f'<p style="margin:0 {t["page_margin"]}px 16px;padding:8px 12px;background-color:{c["loyal_blue"]};'
                f'border-bottom:3px solid {c["true_maroon"]};color:#FFFFFF;font-size:{t["body_size"]}px;'
                f'line-height:1.6;letter-spacing:{t["letter_spacing"]}px;font-weight:bold;text-align:center;">'
                f'{self.inline(text)}</p>')

    def lead(self, text: str) -> str:
        t, c = self.t, self.c
        paras = [p.strip() for p in re.split(r"\\n|\n", text) if p.strip()]
        inner = []
        for k, p in enumerate(paras):
            mb = 0 if k == len(paras) - 1 else t["paragraph_spacing"]
            inner.append(f'<p style="margin:0 0 {mb}px;{self.text_style(color="#555555")}">{self.inline(p)}</p>')
        return (f'<section style="margin:0 {t["page_margin"]}px 16px;padding:12px 14px;background-color:{c["fair_gray"]};'
                f'border-left:4px solid {c["loyal_blue"]};">' + "".join(inner) + "</section>")

    def credits(self, credits) -> str:
        t, c = self.t, self.c
        sep = t.get("credit_separator", "｜")
        rows = []
        for k, (label, value) in enumerate(credits):
            mb = 0 if k == len(credits) - 1 else 4
            rows.append(f'<p style="margin:0 0 {mb}px;{self.text_style(color="#555555", align="left")}">'
                        f'<strong style="color:{c["true_maroon"]};">{html.escape(label)}{sep}</strong>'
                        f'{self.inline(value)}</p>')
        return (f'<section style="margin:0 {t["page_margin"]}px {t["paragraph_spacing"]}px;padding:10px 14px;'
                f'background-color:{c["fair_gray"]};border-top:2px solid {c["loyal_blue"]};">' + "".join(rows) + "</section>")


def is_remote(src: str) -> bool:
    return bool(re.match(r"^(https?:)?//", src)) or src.startswith("data:")


def resolve_image(src: str, md_dir: Path, out_dir: Path, embed: bool, warnings: list):
    """返回 (用于 HTML 的 src, 显示名, 是否本地, 本地绝对路径或 None, 下载链接)。

    本地图片默认以 data URI 嵌进 HTML：复制正文时图片随正文进剪贴板，
    贴进公众号编辑器后由公众号自动上传（2026-11-24 在公众号后台实测）。
    """
    if is_remote(src):
        name = src.split("?")[0].rstrip("/").split("/")[-1] or src
        return src, name, False, None, src
    path = Path(os.path.expanduser(src))
    if not path.is_absolute():
        path = (md_dir / path).resolve()
    name = path.name
    if not path.exists():
        warnings.append(f"找不到图片：{src}（按稿件所在文件夹查找）")
        return src, name, True, None, src
    rel = Path(os.path.relpath(path, out_dir)).as_posix()
    size_mb = path.stat().st_size / 1024 / 1024
    if size_mb > 5:
        warnings.append(f"图片较大（{size_mb:.1f} MB）：{name}，建议先压缩到 2 MB 左右，公众号上传更稳。")
    if embed:
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}", name, True, path, rel
    return rel, name, True, path, rel


def find_name_suspects(texts):
    """找可能没按「Anita LUO」格式写的英文人名。只提醒，不自动改。"""
    found = []
    seen = set()
    for text in texts:
        clean = re.sub(r"\(\S+?\)|https?://\S+", " ", text)
        for m in re.finditer(r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\s+([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\b", clean):
            a, b = m.group(1), m.group(2)
            if a in NAME_STOPWORDS or b in NAME_STOPWORDS:
                continue
            key = f"{a} {b}"
            if key not in seen:
                seen.add(key)
                found.append({"原文": key, "建议": f"{a} {b.upper()}", "说明": "像是「名 姓」，姓应全大写；不是人名可忽略"})
        for m in re.finditer(r"\b([A-Z]{2,})\s+([A-Z][a-z]+)\b", clean):
            a, b = m.group(1), m.group(2)
            if a in NAME_ACRONYMS or b in NAME_STOPWORDS:
                continue
            key = f"{a} {b}"
            if key not in seen:
                seen.add(key)
                found.append({"原文": key, "建议": f"{b} {a}", "说明": "像是把全大写的姓放在了前面；头马习惯「名 姓」，请确认"})
    return found


PAGE_CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#E9ECEC;color:#2B2B2B;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:20px 16px 48px}
.tools{background:#fff;border:1px solid #D5DADA;border-top:4px solid #004165;border-radius:10px;padding:14px 16px;margin:0 0 18px}
.eyebrow{margin:0 0 6px;font-size:12px;font-weight:700;color:#772432;letter-spacing:1px}
.ttl{margin:0 0 4px;font-size:17px;line-height:1.5;font-weight:700;color:#004165}
.sum{margin:0 0 10px;font-size:13px;line-height:1.6;color:#5C6566}
.actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
button{border:1px solid #004165;border-radius:6px;padding:7px 12px;font:inherit;font-size:13px;line-height:1.5;cursor:pointer;background:#fff;color:#004165}
button.primary{background:#004165;color:#fff}
button:focus-visible{outline:3px solid #F2DF74;outline-offset:2px}
#status{font-size:12px;color:#772432;min-height:18px}
.steps{margin:10px 0 0;padding-left:20px;font-size:12.5px;line-height:1.7;color:#4A5354}
.imgs{margin:10px 0 0;font-size:12.5px;line-height:1.7;color:#4A5354}
.imgs a{color:#004165}
.imgs .miss{color:#B42318;font-weight:700}
.warn{margin:10px 0 0;padding:8px 10px;background:#FFF8D6;border-left:3px solid #772432;font-size:12.5px;line-height:1.7;color:#4A3A00}
.phone{width:375px;max-width:100%;margin:0 auto;background:#fff;border-radius:14px;box-shadow:0 8px 30px rgba(0,40,60,.12);padding:20px 16px 28px;overflow:hidden}
.phone .label{margin:0 0 14px;font-size:11px;color:#9AA3A4;text-align:center;letter-spacing:1px}
.article-title{margin:0 0 6px;font-size:22px;line-height:1.4;font-weight:700;color:#1F1F1F}
.meta{margin:0 0 20px;font-size:13px;color:#8A9393}
@media(max-width:420px){.wrap{padding:10px 8px 32px}.phone{border-radius:10px;padding:16px 8px 24px}}
"""

PAGE_JS = r"""
const statusEl = document.getElementById('status');
function say(msg){ statusEl.textContent = msg; }
function cleanClone(mode){
  const clone = document.getElementById('wechat-body').cloneNode(true);
  clone.querySelectorAll('img').forEach(function(img, k){
    const live = document.querySelectorAll('#wechat-body img')[k];
    if (live) img.setAttribute('src', live.src);
  });
  if (mode === 'placeholder') {
    clone.querySelectorAll('[data-tm-img]').forEach(function(p){
      const ph = document.createElement('p');
      ph.setAttribute('style', PLACEHOLDER_STYLE);
      ph.textContent = '【在这里插入图 ' + p.getAttribute('data-tm-img') + '：' + (p.getAttribute('data-tm-name') || '') + '】';
      p.replaceWith(ph);
    });
  }
  clone.querySelectorAll('*').forEach(function(el){
    Array.from(el.attributes).forEach(function(a){ if (a.name.indexOf('data-tm') === 0) el.removeAttribute(a.name); });
  });
  return clone;
}
function copyViaEvent(htmlText, plain){
  // 在用户点击里同步触发 copy 事件，直接写入干净的 HTML，不带页面的计算样式。
  let ok = false;
  const onCopy = function(e){
    if (!e.clipboardData) return;
    if (htmlText !== null) e.clipboardData.setData('text/html', htmlText);
    e.clipboardData.setData('text/plain', plain);
    e.preventDefault();
    ok = true;
  };
  document.addEventListener('copy', onCopy);
  try { document.execCommand('copy'); } catch (e) {}
  document.removeEventListener('copy', onCopy);
  return ok;
}
function fallbackCopy(htmlText, plain){
  const holder = document.createElement('div');
  holder.setAttribute('contenteditable', 'true');
  holder.style.cssText = 'position:fixed;left:-10000px;top:0;width:375px;';
  if (htmlText !== null) holder.innerHTML = htmlText; else holder.textContent = plain;
  document.body.appendChild(holder);
  const sel = window.getSelection(); const range = document.createRange();
  range.selectNodeContents(holder); sel.removeAllRanges(); sel.addRange(range);
  let ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
  sel.removeAllRanges(); holder.remove();
  return ok;
}
async function copyRich(node, msg){
  const htmlText = node.innerHTML; const plain = node.innerText || node.textContent;
  if (copyViaEvent(htmlText, plain)) { say(msg); return; }
  if (navigator.clipboard && window.ClipboardItem) {
    try {
      await navigator.clipboard.write([new ClipboardItem({
        'text/html': new Blob([htmlText], {type: 'text/html'}),
        'text/plain': new Blob([plain], {type: 'text/plain'})
      })]);
      say(msg); return;
    } catch (e) {}
  }
  say(fallbackCopy(htmlText, plain) ? msg : '复制没成功：请在下面的预览里全选正文，按 ⌘C / Ctrl+C 复制');
}
async function copyPlain(text, msg){
  if (copyViaEvent(null, text)) { say(msg); return; }
  if (navigator.clipboard) { try { await navigator.clipboard.writeText(text); say(msg); return; } catch (e) {} }
  say(fallbackCopy(null, text) ? msg : '复制没成功，请手动选中复制');
}
document.getElementById('copy-placeholder').addEventListener('click', function(){
  copyRich(cleanClone('placeholder'), '已复制正文（图片位置留了黄色提示行）。贴到公众号后，在提示行处上传对应图片，再删掉提示行。');
});
document.getElementById('copy-full').addEventListener('click', function(){
  copyRich(cleanClone('full'), IMAGES_READY ? '已复制正文（含图片）。贴进公众号后图片会自动上传，等图片都显示出来再保存。' : '已复制正文（含图片）。本地图片没有嵌入，可能贴不过去，看到裂图就改用「图片留位」。');
});
document.getElementById('copy-title').addEventListener('click', function(){ copyPlain(ARTICLE_TITLE, '已复制标题'); });
const sumBtn = document.getElementById('copy-summary');
if (sumBtn) sumBtn.addEventListener('click', function(){ copyPlain(ARTICLE_SUMMARY, '已复制摘要'); });
"""


def build(md_path: Path, out_path: Path, theme: dict, embed: bool, join_lines: bool):
    raw = md_path.read_text(encoding="utf-8-sig")
    meta, credits, body, warnings = parse_front_matter(raw)
    blocks = parse_blocks(body, join_lines)

    # 标题：信息区优先；没有就把正文最前面的标题当文章标题（不放进正文）。
    title = meta.get("title", "").strip()
    if blocks and blocks[0][0] == "heading":
        if not title:
            title = blocks[0][2]
            blocks = blocks[1:]
        elif blocks[0][2].strip() == title:
            blocks = blocks[1:]
    if not title:
        warnings.append("没有文章标题：在信息区写 title: 或 标题:。")

    # 标题层级按出现过的级别重新排：最高一级 20px，往下 18/16/14。
    levels = sorted({b[1] for b in blocks if b[0] == "heading"})
    n_sizes = len(theme["heading_sizes"])
    if len(levels) > n_sizes:
        warnings.append(f"正文用了 {len(levels)} 级标题，超过 {n_sizes} 级；更深的都按 {theme['heading_sizes'][-1]}px 处理。")
    rank_of = {lv: min(k, n_sizes - 1) for k, lv in enumerate(levels)}

    r = Renderer(theme)
    md_dir, out_dir = md_path.parent.resolve(), out_path.parent.resolve()
    images, parts, kinds = [], [], []
    text_kinds = {"para", "heading", "quote", "ul", "ol", "lead", "column", "credits"}

    def add(kind, snippet):
        kinds.append(kind)
        parts.append(snippet)

    if meta.get("column"):
        add("column", r.column_band(meta["column"]))
    if meta.get("lead"):
        add("lead", r.lead(meta["lead"]))

    headings_count = {}
    for b in blocks:
        kind = b[0]
        if kind == "heading":
            rank = rank_of[b[1]]
            size = theme["heading_sizes"][rank]
            headings_count[f"{size}px"] = headings_count.get(f"{size}px", 0) + 1
            add("heading", r.heading(rank, b[2]))
        elif kind == "para":
            add("para", r.para(b[1]))
        elif kind == "quote":
            add("quote", r.quote(b[1]))
        elif kind in ("ul", "ol"):
            add(kind, r.list_block(kind, b[1]))
        elif kind == "hr":
            add("hr", r.divider())
        elif kind == "image":
            src, name, local, path, href = resolve_image(b[1], md_dir, out_dir, embed, warnings)
            idx = len(images) + 1
            images.append({"序号": idx, "文件": name, "href": href, "嵌入": src.startswith("data:"),
                           "本地": local, "存在": (path is not None) if local else True,
                           "路径": str(path) if path else b[1], "图注": b[2]})
            add("image", r.image(idx, src, b[2], name))

    # 片尾：分隔 + 署名 + 尾图
    if credits or meta.get("end_image"):
        add("hr", r.divider())
    if credits:
        add("credits", r.credits(credits))
    else:
        warnings.append("片尾没有作者、编辑：在信息区写 作者: 和 编辑:。")
    labels = [c[0] for c in credits]
    for need in ("作者", "编辑"):
        if credits and need not in labels and not (need == "作者" and "文字" in labels):
            warnings.append(f"片尾没有「{need}」。")
    if meta.get("end_image"):
        src, name, local, path, href = resolve_image(meta["end_image"], md_dir, out_dir, embed, warnings)
        idx = len(images) + 1
        images.append({"序号": idx, "文件": name, "href": href, "嵌入": src.startswith("data:"),
                       "本地": local, "存在": (path is not None) if local else True,
                       "路径": str(path) if path else meta["end_image"], "图注": "尾图"})
        add("image", r.image(idx, src, meta.get("end_image_caption", ""), name))
    else:
        warnings.append("没有尾图：在信息区写 尾图: 图片路径。")

    # 图片与文字之间空一行
    html_parts = []
    for k, (kind, snippet) in enumerate(zip(kinds, parts)):
        if k > 0 and theme.get("blank_line_around_images", True):
            prev = kinds[k - 1]
            if (kind == "image" and prev in text_kinds) or (prev == "image" and kind in text_kinds):
                html_parts.append(r.blank_line())
        html_parts.append(snippet)
    body_html = "\n".join(html_parts)

    # 残留的 Markdown 符号
    visible = re.sub(r"<[^>]+>", "", body_html)
    for token, tip in (("**", "加粗符号 ** 没配对"), ("![", "有图片写法没识别（图片要单独占一行）"),
                       ("](", "有链接或图片写法没识别"), ("==", "高亮符号 == 没配对")):
        if token in visible:
            warnings.append(f"正文里还留着「{token}」：{tip}。")
    for line in body.splitlines():
        if re.match(r"^\s*#{1,6}[^#\s]", line):
            warnings.append(f"这一行像标题但 # 后面没空格，按正文处理了：{line.strip()[:30]}")

    name_texts = [b[2] if b[0] == "heading" else "" for b in blocks]
    for b in blocks:
        if b[0] == "para":
            name_texts.append(b[1])
        elif b[0] == "quote":
            name_texts.extend(b[1])
        elif b[0] in ("ul", "ol"):
            name_texts.extend(item[1] for item in b[1])
        elif b[0] == "image":
            name_texts.append(b[2])
    name_texts += [v for _, v in credits] + [meta.get("lead", ""), meta.get("column", ""), title]
    suspects = find_name_suspects(name_texts)

    has_local = any(img["本地"] for img in images)
    # 本地图片都已嵌入（或没有本地图片）时，「含图片」可以一键带图进公众号
    images_ready = all(img["嵌入"] or not img["本地"] for img in images)
    embedded_mb = sum(img["路径"] and Path(img["路径"]).stat().st_size for img in images
                      if img["嵌入"]) / 1024 / 1024 if images else 0
    if embedded_mb > 20:
        warnings.append(f"本篇图片合计 {embedded_mb:.0f} MB，复制和上传可能变慢甚至失败；建议先压缩图片。")
    c = theme["colors"]
    placeholder_style = (f"margin:0 {theme['page_margin']}px {theme['paragraph_spacing']}px;padding:8px 10px;"
                         f"background-color:{c['placeholder_bg']};border:1px dashed {c['true_maroon']};"
                         f"color:{c['true_maroon']};font-size:{theme['body_size']}px;line-height:1.6;text-align:center;")

    img_rows = []
    for img in images:
        cls = "" if img["存在"] else ' class="miss"'
        state = "" if img["存在"] else "（找不到文件）"
        href = html.escape(img["href"], quote=True)
        img_rows.append(f'<li{cls}>图 {img["序号"]}：<a href="{href}" target="_blank" download>{html.escape(img["文件"])}</a>'
                        f'{"　" + html.escape(img["图注"]) if img["图注"] else ""}{state}</li>')
    img_list = (f'<div class="imgs"><strong>本篇图片（{len(images)} 张）</strong><ol style="margin:4px 0 0;padding-left:20px">'
                + "".join(img_rows) + "</ol></div>") if images else ""
    warn_html = ""
    if warnings or suspects:
        items = [html.escape(w) for w in warnings]
        items += [html.escape(f"人名请确认：{s['原文']} → {s['建议']}（{s['说明']}）") for s in suspects]
        warn_html = '<div class="warn"><strong>排版前请看：</strong><br>' + "<br>".join(items) + "</div>"

    summary = meta.get("summary", "")
    primary_full = images_ready
    buttons = (
        f'<button id="copy-full" type="button" class="{"primary" if primary_full else ""}">复制正文（含图片）</button>'
        f'<button id="copy-placeholder" type="button" class="{"" if primary_full else "primary"}">复制正文（图片留位）</button>'
        '<button id="copy-title" type="button">复制标题</button>'
        + ('<button id="copy-summary" type="button">复制摘要</button>' if summary else "")
    )
    if images_ready:
        steps = [
            "点「复制标题」，贴到公众号的标题栏。",
            "点「复制正文（含图片）」，在公众号正文里粘贴。图片会自动上传到公众号，等几秒，看到图片都显示出来再保存。",
            "个别图片没传上去时，删掉那张，在原位置用编辑器的图片按钮上传；或者改用「复制正文（图片留位）」，在黄色提示行处逐张上传。",
            "在公众号里点「预览」用手机看一遍，再保存。",
        ]
    else:
        steps = [
            "点「复制标题」，贴到公众号的标题栏。",
            "点「复制正文（图片留位）」，贴进正文；在每一行黄色提示处用编辑器的图片按钮上传对应图片，再删掉提示行。",
            "在公众号里点「预览」用手机看一遍，再保存。",
        ]
    steps_html = "\n".join(f"<li>{html.escape(s)}</li>" for s in steps)
    credit_line = "　".join(f"{lab}{theme.get('credit_separator', '｜')}{val}" for lab, val in credits)
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title or md_path.stem)} · 公众号排版</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<main class="wrap">
<section class="tools" aria-label="复制工具">
<p class="eyebrow">头马公众号推文排版 · 本地预览</p>
<p class="ttl">{html.escape(title or "（还没有标题）")}</p>
{f'<p class="sum">摘要：{html.escape(summary)}</p>' if summary else ''}
<div class="actions">{buttons}</div>
<p id="status" role="status" aria-live="polite"></p>
<ol class="steps">
{steps_html}
</ol>
{img_list}
{warn_html}
</section>
<div class="phone">
<p class="label">手机预览（约 375px 宽）</p>
<p class="article-title">{html.escape(title)}</p>
<p class="meta">{html.escape(credit_line)}</p>
<article id="wechat-body">
{body_html}
</article>
</div>
</main>
<script>
const ARTICLE_TITLE = {json.dumps(title, ensure_ascii=False)};
const ARTICLE_SUMMARY = {json.dumps(summary, ensure_ascii=False)};
const IMAGES_READY = {json.dumps(images_ready)};
const PLACEHOLDER_STYLE = {json.dumps(placeholder_style, ensure_ascii=False)};
{PAGE_JS}
</script>
</body>
</html>
"""
    out_path.write_text(page, encoding="utf-8")
    return {
        "output": str(out_path.resolve()),
        "title": title,
        "summary": summary,
        "paragraphs": sum(1 for b in blocks if b[0] == "para"),
        "headings": headings_count,
        "images": [{k: v for k, v in img.items() if k != "src"} for img in images],
        "credits": [f"{a}{theme.get('credit_separator', '｜')}{b}" for a, b in credits],
        "end_image": bool(meta.get("end_image")),
        "name_suspects": suspects,
        "warnings": warnings,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="头马公众号推文排版：Markdown → 公众号可粘贴 HTML")
    ap.add_argument("markdown", help="推文源稿（.md）")
    ap.add_argument("--out", help="输出 HTML 路径；默认放在源稿旁边，文件名加「-公众号排版」")
    ap.add_argument("--theme", help="自定义主题 JSON（只写要改的项）")
    ap.add_argument("--link-images", action="store_true",
                    help="本地图片不嵌入，只用相对路径（HTML 小，但贴进公众号时本地图片带不过去）")
    ap.add_argument("--embed-images", action="store_true", help=argparse.SUPPRESS)  # 旧参数，现在默认就嵌入
    ap.add_argument("--join-lines", action="store_true", help="按 Markdown 原生规则：连续几行合成一段，空行才分段")
    args = ap.parse_args(argv)

    md_path = Path(os.path.expanduser(args.markdown))
    if not md_path.exists():
        print(json.dumps({"error": f"找不到源稿：{md_path}"}, ensure_ascii=False), file=sys.stderr)
        return 1
    out_path = Path(os.path.expanduser(args.out)) if args.out else md_path.with_name(md_path.stem + "-公众号排版.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    theme = load_theme(Path(os.path.expanduser(args.theme)) if args.theme else None)
    result = build(md_path, out_path, theme, not args.link_images, args.join_lines)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
