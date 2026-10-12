#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""范文 HTML 学习页渲染器（2026 新大纲口径）。

读取范文正文 + 好词好句 + 教师元数据（teacher.json），按 reference/hsk_vocab.json
（2026 版 HSK 分级词表）做最长匹配分词，给每个词标注 HSK 等级与拼音，
生成一份完整、自包含、可直接打印/下载的教学素材 HTML：

  - 学生练习版：题目、四格漫画、构思引导、可用句型、参考关键词、写作要求
  - 教师备课版：教学信息、参考范文（★超纲词+注释表）、范文结构、评分要点、
    教学建议、级控检查、考试说明
  - 顶部工具条：打印 / 存为 PDF、下载 HTML（@media print 打印友好，A4 可用）

用法:
  python3 render_essay_html.py --essay-text "范文正文" --title "标题" --hsk-level 5
  python3 render_essay_html.py --essay-file /path/essay.txt --expressions-json /path/expr.json \
      --teacher-json /path/teacher.json --output /mnt/user-data/outputs/essay_话题_HSKx.html \
      --hsk-level 6 --title "标题"

参数:
  --essay-text     范文正文（与 --essay-file 二选一）
  --essay-file     范文文本文件路径
  --expressions-json  好词好句 JSON 数组（可选）：[{"expression","pinyin","hsk","en_def","explanation","example"}]
  --teacher-json   教师元数据 JSON（可选，提供则渲染完整双视图教学素材）：
      {"exam_name","exam_type","topic","level_label","min_chars","time_limit",
       "question","guiding_questions":[],"patterns":[],"connectors":[],
       "keywords":[],"requirements":[],"teaching_info":[[k,v],...],
       "structure","rubric":[],"teaching_tips":[],"exam_note",
       "glossary":[{"word","pinyin","meaning"}],"out_of_syllabus_note"}
  --output         输出 HTML 路径（默认 /mnt/user-data/outputs/essay_display.html）
  --hsk-level      HSK 等级（仅用于页头显示）
  --title          标题（无 teacher-json 时的页头标题）
  --word-count     字数（留空/为0时自动按正文实算）
  --ref-dir        reference 目录（默认自动推断为脚本上级目录的 reference/）
  --comic-svg      四格漫画 SVG 文件路径（本地保底路径，嵌入学生版）
  --comic-images   四格漫画 PNG 图片路径，逗号分隔（千问 API 生成时传入，base64 嵌入）
"""
import argparse
import base64
import json
import os
import re
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HSK_LABELS = {1: "HSK 1", 2: "HSK 2", 3: "HSK 3", 4: "HSK 4", 5: "HSK 5", 6: "HSK 6", 7: "HSK 7", 8: "HSK 8", 9: "HSK 9"}
HSK_COLORS = {1: "#c0392b", 2: "#d35400", 3: "#e67e22", 4: "#27ae60", 5: "#2980b9", 6: "#8e44ad", 7: "#7f8c8d", 8: "#7f8c8d", 9: "#7f8c8d"}
HSK_BG = {1: "#fdf0ef", 2: "#fdf4ee", 3: "#fdf6ef", 4: "#effaf2", 5: "#eef5fc", 6: "#f7f2fc", 7: "#f4f4f4", 8: "#f4f4f4", 9: "#f4f4f4"}
PUNCT = re.compile(r"[\s\u3000，。！？；：、,.!?;:·—…（）()《》<>“”‘’\"'【\[\]：—]")


def esc(s):
    import html as _html
    if s is None:
        return ""
    return _html.escape(str(s), quote=True)


def _level_of_key(k):
    """从等级键名解析等级数字，兼容 "hsk1"~"hsk6" 与合并键 "hsk7-9"（取主数字 7）"""
    s = k.lower().replace("hsk", "").strip()
    m = re.match(r"^(\d+)", s)
    return int(m.group(1)) if m else 0


def load_vocab(path):
    """{词: 等级(整数)}，兼容 {"hsk1": [...]} 与 {"词": 1} 两种格式"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    word2level = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list):
                lv = _level_of_key(k)
                for w in v:
                    w = w.strip()
                    if w and (w not in word2level or word2level[w] > lv):
                        word2level[w] = lv
            elif isinstance(v, int):
                for part in k.strip().split("|"):
                    part = part.strip()
                    if part and (part not in word2level or word2level[part] > v):
                        word2level[part] = v
    return word2level


def load_char_pinyin(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Trie:
    def __init__(self):
        self.root = {}

    def insert(self, word, level):
        node = self.root
        for ch in word:
            node = node.setdefault(ch, {})
        node["_w"] = word
        node["_l"] = level

    def longest_match(self, text, start):
        node = self.root
        match = None
        for i in range(start, len(text)):
            ch = text[i]
            if ch in node:
                node = node[ch]
                if "_w" in node:
                    match = node
            else:
                break
        return match


def char_pinyin_of(ch, char_pinyin):
    return char_pinyin.get(ch, "")


def segment(text, trie, char_pinyin):
    """返回 [(token, level_or_None, pinyin_or_None)]"""
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        if PUNCT.match(text[i]):
            tokens.append((text[i], None, None))
            i += 1
            continue
        m = trie.longest_match(text, i)
        if m and "_w" in m and len(m["_w"]) > 1:
            w = m["_w"]
            py = " ".join(filter(None, (char_pinyin.get(ch, "") for ch in w)))
            tokens.append((w, m["_l"], py or None))
            i += len(w)
        else:
            tokens.append((text[i], None, None))
            i += 1
    return tokens


def split_essay(text):
    """解析范文文本：第一行（非空）为标题，其余行为正文段落（空行/换行分隔）。

    若第一行过长（>30 字），视为无标题，整体按正文处理。
    """
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return "", []
    title = lines[0]
    paras = lines[1:] if len(lines) > 1 else []
    if len(title) > 30:
        paras = [title] + paras
        title = ""
    return title, paras


def essay_chars(paragraphs):
    """范文正文汉字数（不含标题、不含空白）"""
    return len(re.sub(r"\s", "", "".join(paragraphs)))


def build_essay_html(title, paragraphs, vocab, char_pinyin, expressions):
    """带 HSK 等级着色 + 拼音 + 好词好句高亮的范文正文 HTML。

    标题居中加粗（essay-title），正文每段首行空两格（essay-para），
    使用楷体书写字体，支持普通/横线纸/方格纸三种展示模式。
    """
    trie = Trie()
    for w, lv in vocab.items():
        if len(w) >= 1:
            trie.insert(w, lv)

    expr_words = set()
    for e in expressions or []:
        expr_words.add(e.get("expression", ""))

    def render_para(para):
        parts = []
        for token, level, py in segment(para, trie, char_pinyin):
            w = token
            if level is not None and level > 0:
                color = HSK_COLORS.get(level, "#7f8c8d")
                bg = HSK_BG.get(level, "#f4f4f4")
                tip = "%s（%s级）" % (py or w, HSK_LABELS.get(level, "超纲"))
                if w in expr_words:
                    parts.append('<span class="word expr hsk%d" style="background:%s;color:%s" title="%s">%s</span>' % (level, "#fff3cd", color, tip, w))
                else:
                    parts.append('<span class="word hsk%d" style="background:%s;color:%s" title="%s">%s</span>' % (level, bg, color, tip, w))
            else:
                if w in expr_words:
                    parts.append('<span class="expr" style="background:#fff3cd">%s</span>' % w)
                else:
                    parts.append(w)
        return "".join(parts)

    title_html = '<div class="essay-title">%s</div>' % esc(title) if title else ""
    para_html = "".join('<p class="essay-para">%s</p>' % render_para(p) for p in paragraphs)
    return title_html, para_html


def build_expr_table(expressions, text):
    rows = []
    for e in expressions or []:
        exp = e.get("expression", "")
        example = e.get("example", "").strip()
        if not example and exp:
            for sent in re.split(r"[。！？；!?;]+", text):
                if exp in sent:
                    example = sent.strip()
                    break
        rows.append(
            "<tr><td><strong>%s</strong></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (esc(exp), esc(e.get("pinyin", "")), HSK_LABELS.get(e.get("hsk"), ""), esc(e.get("en_def", "")), esc(example or e.get("explanation", "")))
        )
    return (
        '<h3 class="sec-h">💡 好词好句</h3><table><tr><th>表达</th><th>拼音</th><th>等级</th><th>释义</th><th>例句/说明</th></tr>%s</table>'
        % "".join(rows)
    )


def build_comic_html(comic_svg, comic_images, comic_image=None):
    if comic_images:
        cells = []
        for i, img_path in enumerate(comic_images[:4], 1):
            try:
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                cells.append(
                    '<figure><img src="data:image/png;base64,%s" alt="图%d"><figcaption>图%d</figcaption></figure>'
                    % (b64, i, i)
                )
            except Exception:
                continue
        if cells:
            return '<div class="comic-grid">%s</div>' % "".join(cells)
    if comic_image:
        try:
            with open(comic_image, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return '<div class="comic"><img src="data:image/png;base64,%s" alt="四格漫画"></div>' % b64
        except Exception:
            pass
    if comic_svg:
        return '<div class="comic">%s</div>' % comic_svg
    return ""


def card(title, inner, cls="white", icon=""):
    return (
        '<div class="card %s"><div class="card-title">%s%s</div>%s</div>'
        % (cls, icon, esc(title), inner)
    )


def ul(items, tag="ul"):
    if not items:
        return ""
    return "<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % esc(x) for x in items), tag)


def build_student_section(tj, comic_html):
    blocks = []
    min_chars = tj.get("min_chars") or 0
    question = tj.get("question") or ""
    if question:
        sub = "写作题目" + (" · 不少于%d字" % min_chars if min_chars else "")
        blocks.append(
            '<div class="card white"><div class="card-title">📝 %s</div>'
            '<div class="question">%s</div></div>' % (esc(sub), esc(question))
        )
    if comic_html:
        blocks.append(card("四格漫画（看图作文）", comic_html, icon="🖼️ "))
    if tj.get("guiding_questions"):
        blocks.append(card("构思引导", ul(tj.get("guiding_questions"), "ol"), icon="💡 "))
    patterns = tj.get("patterns") or []
    connectors = tj.get("connectors") or []
    if patterns or connectors:
        inner = ul(patterns)
        if connectors:
            inner += '<div class="conn"><b>连接词：</b>%s</div>' % esc("、".join(connectors))
        blocks.append(card("可用句型", inner, icon="🗣 "))
    if tj.get("keywords"):
        kw_html = "".join(
            '<span class="kw">%s</span>' % esc(w) for w in tj.get("keywords")
        )
        blocks.append(card("参考关键词", '<div>%s</div>' % kw_html, icon="🔑 "))
    if tj.get("requirements"):
        blocks.append(card("写作要求", ul(tj.get("requirements")), cls="amber", icon="📌 "))
    return "".join(blocks)


def build_teacher_section(tj, essay_title_html, paras_html, expr_html, paragraphs, expressions):
    blocks = []
    info = tj.get("teaching_info") or []
    if info:
        trs = "".join(
            '<tr><td class="k">%s</td><td class="v">%s</td></tr>' % (esc(k), esc(v)) for k, v in info
        )
        blocks.append(card("教学信息", '<table class="info">%s</table>' % trs, icon="🏫 "))
    paper_switch = (
        '<div class="paper-switch">'
        '<span class="ps-label">书写纸：</span>'
        '<button class="pbtn active" data-p="" onclick="setPaper(\'\')">普通</button>'
        '<button class="pbtn" data-p="paper-line" onclick="setPaper(\'paper-line\')">横线纸</button>'
        '<button class="pbtn" data-p="paper-grid" onclick="setPaper(\'paper-grid\')">方格纸</button>'
        '</div>'
    )
    blocks.append(card("参考范文", paper_switch + essay_title_html + '<div class="essay" id="essay-block">%s</div>%s' % (paras_html, expr_html), icon="📝 "))
    glossary = tj.get("glossary") or []
    if glossary:
        g_rows = "".join(
            '<tr><td class="star">★%s★</td><td>%s</td><td>%s</td></tr>'
            % (esc(g.get("word", "")), esc(g.get("pinyin", "")), esc(g.get("meaning", "")))
            for g in glossary
        )
        note = tj.get("out_of_syllabus_note") or "超纲词超过本等级词汇，请先解释再使用"
        blocks.append(
            '<div class="card white"><div class="card-title">⭐ 超纲词注释</div>'
            '<div class="note">%s</div><table>%s</table></div>' % (esc(note), g_rows)
        )
    if tj.get("structure"):
        blocks.append(card("范文结构", '<div class="para-text">%s</div>' % esc(tj.get("structure")), icon="🧩 "))
    if tj.get("rubric"):
        blocks.append(card("评分要点", ul(tj.get("rubric")), icon="✅ "))
    if tj.get("teaching_tips"):
        blocks.append(card("教学建议", ul(tj.get("teaching_tips")), cls="green", icon="👩‍🏫 "))
    # 级控检查（自动实算字数，只统计正文段落，不含标题）
    real_wc = essay_chars(paragraphs)
    min_chars = tj.get("min_chars") or 0
    ok = real_wc >= min_chars if min_chars else True
    lines = ["<li>字数：正文%d字%s</li>" % (real_wc, "（≥%d字，达标）" % min_chars if min_chars else "")]
    lines.append("<li>检查结果：<b>%s</b></li>" % ("通过（字数达标）" if ok else "需复核（字数不足）"))
    blocks.append(
        '<div class="card gray"><div class="card-title">🔍 级控自动检查</div>'
        '<ul class="small">%s</ul></div>' % "".join(lines)
    )
    if tj.get("exam_note"):
        blocks.append('<div class="card gray"><div class="card-title">📘 考试说明</div><div class="note">%s</div></div>' % esc(tj.get("exam_note")))
    return "".join(blocks)


PAGE_CSS = """
  *{box-sizing:border-box}
  body{font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;margin:0;background:#eef2f8;color:#2b3a52;line-height:1.7}
  .wrap{max-width:820px;margin:0 auto;padding:24px 16px 60px}
  .hero{background:linear-gradient(135deg,#1f4fd8,#3b6df0);color:#fff;border-radius:16px;padding:26px 28px;margin-bottom:18px;box-shadow:0 4px 14px rgba(31,79,216,.25)}
  .hero h1{margin:0 0 6px;font-size:22px;letter-spacing:1px}
  .hero .sub{font-size:13px;opacity:.92}
  .badges{margin-top:12px}
  .badge{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:20px;padding:3px 12px;margin:0 6px 6px 0;font-size:13px}
  .actions{margin:0 0 18px;text-align:right}
  .btn{display:inline-block;background:#1f4fd8;color:#fff;border:0;border-radius:8px;padding:9px 18px;font-size:14px;cursor:pointer;margin-left:8px;box-shadow:0 2px 6px rgba(31,79,216,.3)}
  .btn:hover{background:#1740b0}
  .btn.green{background:#2e8b57;box-shadow:0 2px 6px rgba(46,139,87,.3)}
  .btn.green:hover{background:#237044}
  .sec{margin-bottom:20px}
  .sec-title{display:flex;align-items:center;gap:10px;margin-bottom:12px;font-size:18px;font-weight:700;color:#1c2b45}
  .sec-title::before{content:"";display:inline-block;width:8px;height:22px;border-radius:4px;background:#1f4fd8}
  .sec-title.green::before{background:#2e8b57}
  .divider{text-align:center;color:#8a93a6;font-size:13px;margin:26px 0 18px;border-top:1px dashed #c9d3e3;padding-top:14px}
  .card{background:#fff;border:1px solid #e3e8f0;border-radius:12px;padding:18px 22px;margin:0 0 14px;box-shadow:0 1px 3px rgba(15,41,93,.05)}
  .card.amber{background:#fff8ec;border-color:#f5e1b8}
  .card.green{background:#f0f7f0;border-color:#cfe3cf}
  .card.gray{background:#f6f8fb;border-color:#dde4ee}
  .card-title{font-size:16px;font-weight:700;color:#1c2b45;margin-bottom:10px}
  .question{font-size:17px;font-weight:600;color:#1c2b45;line-height:1.8;white-space:pre-wrap}
  .kw{display:inline-block;background:#eef3ff;color:#1f4fd8;border:1px solid #d6e1ff;border-radius:20px;padding:3px 12px;margin:0 6px 8px 0;font-size:13px}
  .conn{font-size:14px;color:#33415c;margin-top:8px}
  .para-text{font-size:14px;color:#33415c;line-height:1.8}
  .note{font-size:13px;color:#8a93a6;margin-bottom:8px}
  .essay{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:22px 26px;font-family:"KaiTi","楷体","STKaiti","KaiTi_GB2312",serif;font-size:17px;line-height:2.0;color:#2b3a52}
  .essay-title{text-align:center;font-weight:700;font-size:20px;letter-spacing:2px;margin-bottom:12px;font-family:"KaiTi","楷体","STKaiti","KaiTi_GB2312",serif}
  .essay-para{text-indent:2em;margin:0 0 4px;text-align:justify}
  .paper-switch{margin-bottom:10px;font-size:13px;color:#5a6b85}
  .ps-label{margin-right:6px}
  .pbtn{display:inline-block;background:#fff;color:#1f4fd8;border:1px solid #d6e1ff;border-radius:14px;padding:2px 12px;margin:0 6px 0 0;font-size:13px;cursor:pointer}
  .pbtn.active{background:#1f4fd8;color:#fff;border-color:#1f4fd8}
  /* 横线纸：linify() 按实际渲染行拆分为 .hline（border-bottom 贯穿整行），线跟随每行字、行距即线距，完全自适应 */
  .paper-line{line-height:30px}
  .paper-line .hline{display:block;border-bottom:1px solid #b9c6d8;line-height:30px;white-space:nowrap}
  /* 方格纸：字帖米字格——每个格子含十字+两条对角线虚线（8部分），SVG data URI 纯前端实现 */
  .cell{display:inline-block;width:26px;height:26px;margin:0 -1px 2px 0;border:1px solid #a9bcd4;text-align:center;text-indent:0;line-height:26px;font-size:20px;vertical-align:top;background-color:#fff;background-image:url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='26'%20height='26'%3E%3Cline%20x1='13'%20y1='0'%20x2='13'%20y2='26'%20stroke='%23d9e2f0'%20stroke-width='1'%20stroke-dasharray='2%202'/%3E%3Cline%20x1='0'%20y1='13'%20x2='26'%20y2='13'%20stroke='%23d9e2f0'%20stroke-width='1'%20stroke-dasharray='2%202'/%3E%3Cline%20x1='0'%20y1='0'%20x2='26'%20y2='26'%20stroke='%23d9e2f0'%20stroke-width='1'%20stroke-dasharray='2%202'/%3E%3Cline%20x1='26'%20y1='0'%20x2='0'%20y2='26'%20stroke='%23d9e2f0'%20stroke-width='1'%20stroke-dasharray='2%202'/%3E%3C/svg%3E");background-size:100% 100%;background-repeat:no-repeat;border-radius:0;overflow:hidden}
  .cell.blank{background:#f4f8fd;border-style:dashed}
  .comic{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-align:center}
  .comic img{max-width:100%;border-radius:6px;border:1px solid #eee}
  .comic svg{max-width:100%;height:auto}
  .comic-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
  .comic-grid figure{margin:0;text-align:center}
  .comic-grid img{width:100%;border-radius:6px;border:1px solid #eee}
  .comic-grid figcaption{font-size:13px;color:#7f8c8d;margin-top:4px}
  .word{border-radius:3px;padding:0 1px;cursor:help}
  .expr{outline:2px solid #f1c40f}
  .legend{display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin:12px 0 8px;font-size:12px}
  .lg{display:inline-block;padding:2px 10px;border-radius:10px;border:1px solid rgba(0,0,0,.06)}
  table{width:100%;border-collapse:collapse;margin:10px 0 16px;background:#fff;font-size:13px}
  th,td{border:1px solid #ddd;padding:6px 9px;text-align:left}
  th{background:#3498db;color:#fff}
  table.info td.k{width:110px;font-weight:600;color:#1c2b45;white-space:nowrap;background:#f7f9fc}
  table.info td.v{color:#33415c;line-height:1.7}
  td.star{font-weight:600;color:#7a4a00}
  ul.small{font-size:13px;color:#5a6b85;margin:8px 0 0;padding-left:20px}
  .footer{color:#8a93a6;font-size:12px;text-align:center;margin-top:24px;line-height:1.8}
  @media print{
    body{background:#fff}
    .wrap{max-width:100%;padding:0}
    .hero{box-shadow:none;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .actions{display:none}
    .card,.sec,.divider{box-shadow:none;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    a{color:inherit;text-decoration:none}
  }
"""


def render(text, title, hsk_level, expressions, vocab, char_pinyin, comic_svg=None, comic_images=None, teacher_json=None, comic_image=None):
    essay_title, paragraphs = split_essay(text)
    essay_title_html, paras_html = build_essay_html(essay_title, paragraphs, vocab, char_pinyin, expressions)
    expr_html = build_expr_table(expressions, text) if expressions else ""
    comic_html = build_comic_html(comic_svg, comic_images, comic_image)
    real_wc = essay_chars(paragraphs)

    legend = "".join(
        '<span class="lg" style="background:%s;color:%s">%s</span>' % (HSK_BG[l], HSK_COLORS[l], HSK_LABELS[l])
        for l in range(1, 7)
    )
    legend_html = '<div class="legend">按 HSK 等级着色（悬停查看拼音）：%s</div>' % legend

    badges = '<div class="badges"><span class="badge">%s</span></div>' % esc(HSK_LABELS.get(hsk_level, "HSK %s" % hsk_level))

    if teacher_json:
        tj = teacher_json
        topic = tj.get("topic") or ""
        exam_name = tj.get("exam_name") or ""
        title = ("%s — %s（%s）" % (topic, exam_name, HSK_LABELS.get(hsk_level, hsk_level))) if topic else title
        meta_bits = ["等级：%s" % esc(tj.get("level_label") or HSK_LABELS.get(hsk_level, hsk_level))]
        if exam_name:
            meta_bits.append("题型：%s" % esc(exam_name))
        if tj.get("min_chars"):
            meta_bits.append("字数：≥%d字" % tj["min_chars"])
        if tj.get("time_limit"):
            meta_bits.append("时间：%s" % esc(tj.get("time_limit")))
        meta_html = '<div class="hero"><h1>%s</h1><div class="sub">%s</div>%s</div>' % (
            esc(title), " ｜ ".join(meta_bits), badges
        )

        student_html = build_student_section(tj, comic_html)
        teacher_html = build_teacher_section(tj, essay_title_html, paras_html, expr_html, paragraphs, expressions)

        body = '<div class="sec"><div class="sec-title">学生练习版</div>%s</div>' % student_html
        if teacher_html:
            body += '<div class="divider">┄　以下为教师版（学生练习时可不查看）　┄</div>'
            body += '<div class="sec"><div class="sec-title green">教师备课版</div>%s</div>' % teacher_html
        body += legend_html
        return _page(meta_html, body, title)
    else:
        meta_html = '<div class="hero"><h1>%s</h1><div class="sub">等级：%s｜字数：%s</div>%s</div>' % (
            esc(title), HSK_LABELS.get(hsk_level, hsk_level), real_wc, badges
        )
        body = legend_html + '<div class="card white"><div class="card-title">📝 参考范文</div>%s<div class="essay">%s</div>%s</div>' % (essay_title_html, paras_html, expr_html)
        if comic_html:
            body = '<div class="card white"><div class="card-title">🖼️ 四格漫画</div>%s</div>' % comic_html + body
        return _page(meta_html, body, title)


def _page(meta_html, body, title):
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>%s</style>
</head>
<body>
<div class="wrap">
%s
<div class="actions">
  <button class="btn" onclick="window.print()">🖨 打印 / 存为 PDF</button>
  <button class="btn green" onclick="downloadHtml()">⬇ 下载 HTML</button>
</div>
%s
<div class="footer">本材料由 HSK 写作题目生成器自动生成（基于 2026 版 HSK 大纲，范文经官方词表级控校验）。<br>
供学生练习与教师备课使用，可直接打印或保存为 PDF。</div>
</div>
<script>
function downloadHtml(){
  var html='<!DOCTYPE html>'+document.documentElement.outerHTML;
  var blob=new Blob([html],{type:'text/html;charset=utf-8'});
  var a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=(document.title.replace(/[\\\\/:*?"<>|\\s]+/g,'_')||'essay')+'.html';
  document.body.appendChild(a);a.click();document.body.removeChild(a);
}
function setPaper(cls){
  var el=document.getElementById('essay-block');
  if(!el)return;
  if(essayOrigHTML===null){essayOrigHTML=el.innerHTML;}
  if(cls==='paper-grid'){
    var t=document.createElement('div');
    t.innerHTML=essayOrigHTML;
    gridify(t);
    el.innerHTML=t.innerHTML;
    el.className='essay';
  }else if(cls==='paper-line'){
    el.innerHTML=essayOrigHTML;
    el.className='essay paper-line';
    linify(el);
  }else{
    el.innerHTML=essayOrigHTML;
    el.className='essay'+(cls?' '+cls:'');
  }
  var btns=document.querySelectorAll('.pbtn');
  for(var i=0;i<btns.length;i++){
    if(btns[i].getAttribute('data-p')===cls){btns[i].classList.add('active');}
    else{btns[i].classList.remove('active');}
  }
}
function gridify(root){
  var paras=root.querySelectorAll('.essay-para');
  for(var pi=0;pi<paras.length;pi++){
    var p=paras[pi];
    p.style.textAlign='left'; /* justify 与 inline-block 混用在部分内核导致字溢出格子，方格模式强制左对齐 */
    var b1=document.createElement('span');b1.className='cell blank';b1.innerHTML='&nbsp;';
    var b2=b1.cloneNode(true);
    p.insertBefore(b2,p.firstChild);
    p.insertBefore(b1,p.firstChild);
    var targets=[];
    (function rec(n){
      for(var i=0;i<n.childNodes.length;i++){
        var c=n.childNodes[i];
        if(c.nodeType===3){targets.push(c);}
        else if(c.nodeType===1&&c.tagName==='SPAN'){targets.push(c);}
        else{rec(c);}
      }
    })(p);
    for(var ti=0;ti<targets.length;ti++){
      var t=targets[ti],frag=document.createDocumentFragment();
      if(t.nodeType===3){
        splitIntoCells(t.nodeValue,null,frag);
      }else{
        var title=t.getAttribute('title')||'';
        var color='',st=t.getAttribute('style')||'',m=st.match(/color:([^;]+)/);
        if(m){color=m[1];}
        splitIntoCells(t.textContent,{title:title,color:color},frag);
      }
      t.parentNode.replaceChild(frag,t);
    }
  }
}
function splitIntoCells(txt,meta,frag){
  var i=0;
  while(i<txt.length){
    var ch=txt[i];
    if(ch===' '||ch==='\t'||ch==='\\n'||ch==='\\r'){i++;continue;}
    var cell=document.createElement('span');
    cell.className='cell';
    if(meta){
      if(meta.title){cell.setAttribute('title',meta.title);}
      if(meta.color){cell.style.color=meta.color;}
    }
    var end=i;
    if(/[A-Za-z0-9]/.test(ch)){
      while(end<txt.length&&/[A-Za-z0-9]/.test(txt[end])){end++;}
    }else{end=i+1;}
    cell.textContent=txt.substring(i,end);
    frag.appendChild(cell);
    i=end;
  }
}
function escHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function linify(root){
  /* 横线纸：把段落文本按实际渲染行拆成 <div class="hline">，border-bottom 贯穿整行，
     线跟随每行字（行距即线距），不依赖固定坐标背景 */
  var paras=root.querySelectorAll('.essay-para');
  for(var pi=0;pi<paras.length;pi++){
    var p=paras[pi];
    p.style.textAlign='left';
    var chars=[];
    var walker=document.createTreeWalker(p,NodeFilter.SHOW_TEXT,{acceptNode:function(n){return n.nodeValue&&n.nodeValue.length?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT;}});
    var nodes=[];var w;
    while(w=walker.nextNode()){nodes.push(w);}
    for(var ni=0;ni<nodes.length;ni++){
      var node=nodes[ni];
      var sp=node.parentNode,title='',color='';
      while(sp&&sp.nodeType===1&&sp.tagName!=='SPAN'){sp=sp.parentNode;}
      if(sp&&sp.nodeType===1){
        title=sp.getAttribute('title')||'';
        var st=sp.getAttribute('style')||'',m=st.match(/color:([^;]+)/);
        if(m){color=m[1];}
      }
      var v=node.nodeValue;
      for(var ci=0;ci<v.length;ci++){
        var ch=v[ci];
        if(ch===' '||ch==='\t'||ch==='\\n'||ch==='\\r'){continue;}
        var r=document.createRange();r.setStart(node,ci);r.setEnd(node,ci+1);
        var rc=r.getBoundingClientRect();
        if(rc.width===0&&rc.height===0){continue;}
        chars.push({ch:ch,title:title,color:color,top:Math.round(rc.top)});
      }
    }
    if(!chars.length){continue;}
    var lines=[[chars[0]]];
    for(var i2=1;i2<chars.length;i2++){
      var lastTop=lines[lines.length-1][0].top;
      if(chars[i2].top>lastTop+2){lines.push([]);}
      lines[lines.length-1].push(chars[i2]);
    }
    p.style.textIndent='0';
    var html='';
    for(var li=0;li<lines.length;li++){
      var line=lines[li],sb='';
      for(var cj=0;cj<line.length;cj++){
        var c=line[cj],st2='';
        if(c.color){st2+=';color:'+c.color;}
        sb+='<span class="ch"'+(c.title?' title="'+escHtml(c.title)+'"':'')+' style="'+st2.slice(1)+'">'+escHtml(c.ch)+'</span>';
      }
      html+='<div class="hline"'+(li===0?' style="text-indent:2em"':'')+'>'+sb+'</div>';
    }
    p.innerHTML=html;
  }
}
var essayOrigHTML=null;
</script>
</body>
</html>""" % (esc(title), PAGE_CSS, meta_html, body)


def main():
    ap = argparse.ArgumentParser(description="范文 HTML 学习页渲染器")
    ap.add_argument("--essay-text", default=None)
    ap.add_argument("--essay-file", default=None)
    ap.add_argument("--expressions-json", default=None)
    ap.add_argument("--teacher-json", default=None)
    ap.add_argument("--output", default="/mnt/user-data/outputs/essay_display.html")
    ap.add_argument("--hsk-level", type=int, default=6)
    ap.add_argument("--title", default="范文")
    ap.add_argument("--word-count", default="0")
    ap.add_argument("--ref-dir", default=None, help="reference 目录（默认自动推断为脚本上级目录的 reference/）")
    ap.add_argument("--comic-svg", default=None, help="四格漫画 SVG 文件路径（本地保底路径，嵌入学生版）")
    ap.add_argument("--comic-images", default=None, help="四格漫画 PNG 图片路径，逗号分隔（千问 panels 模式生成时传入，以 base64 嵌入 2×2 网格）")
    ap.add_argument("--comic-image", default=None, help="四格漫画单张 PNG 路径（千问 single 模式生成的 2×2 图，以 base64 嵌入）")
    args = ap.parse_args()

    if args.essay_text:
        text = args.essay_text
    elif args.essay_file:
        with open(args.essay_file, encoding="utf-8") as f:
            text = f.read()
    else:
        print(json.dumps({"error": "缺少输入：用 --essay-text 或 --essay-file"}, ensure_ascii=False))
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    ref_dir = args.ref_dir or os.path.join(script_dir, "..", "reference")
    if not os.path.exists(ref_dir):
        ref_dir = os.path.join(script_dir, "..", "..", "reference")
    vocab_path = os.path.join(ref_dir, "hsk_vocab.json")
    char_path = os.path.join(ref_dir, "char_pinyin.json")
    if not os.path.exists(vocab_path):
        print(json.dumps({"error": "词表缺失：reference/hsk_vocab.json（可用 --ref-dir 指定）"}, ensure_ascii=False))
        sys.exit(1)

    vocab = load_vocab(vocab_path)
    char_pinyin = load_char_pinyin(char_path) if os.path.exists(char_path) else {}

    expressions = []
    if args.expressions_json and os.path.exists(args.expressions_json):
        with open(args.expressions_json, encoding="utf-8") as f:
            expressions = json.load(f)

    teacher_json = None
    if args.teacher_json and os.path.exists(args.teacher_json):
        with open(args.teacher_json, encoding="utf-8") as f:
            teacher_json = json.load(f)

    real_wc = len(re.sub(r"\s", "", text))
    comic_svg = None
    if args.comic_svg and os.path.exists(args.comic_svg):
        with open(args.comic_svg, encoding="utf-8") as f:
            comic_svg = f.read()
    comic_images = [p.strip() for p in (args.comic_images or "").split(",") if p.strip()] or None
    comic_image = args.comic_image if args.comic_image and os.path.exists(args.comic_image) else None
    html = render(text, args.title, args.hsk_level, expressions, vocab, char_pinyin, comic_svg, comic_images, teacher_json, comic_image)

    out = args.output
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(json.dumps({"success": True, "path": out, "word_count": real_wc}, ensure_ascii=False))


if __name__ == "__main__":
    main()
