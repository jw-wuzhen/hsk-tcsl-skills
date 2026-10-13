#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对话素材 HTML 学习页渲染器（HSK 对话材料生成器配套）。

读取对话素材 JSON（标题、场景、人物、多轮对话、关键词、生词、学后任务、
教师信息），生成一份自包含、可直接打印/下载的对话学习页 HTML：

  - 学生视图：气泡双栏对话（角色左右分列、颜色区分）+ 遮句自练模式
    （遮住任一角色，学生扮演另一方，点击占位卡查看原文）+ 关键词 +
    重点句型 + 生词悬停标注（拼音+HSK等级+释义）+ 学后任务
  - 教师视图：教学信息、组织流程、评分要点
  - 生词自动在台词中标注（.oc，悬停显示 title）

用法:
  python3 render_dialogue_html.py --dialogue-json /path/dialogue.json \
      --output /mnt/user-data/outputs/dialogue_话题_HSKx.html

dialogue.json 格式:
{
  "title": "周末的一天",
  "hsk_level": 4,
  "tags": ["生活日常", "居家生活", "8轮 · 2人"],
  "scene": "周末上午，家里",
  "characters": ["小李", "小王"],
  "topic_tree": "日常生活 > 家庭生活 > 居家生活",
  "functions": "商量安排、表达感受、提出建议",
  "grammar_points": ["先……再……", "把字句", "动词重叠", "……吧"],
  "dialogue": [
    {"speaker": "小李", "line": "你起床啦？今天天气真好。"},
    {"speaker": "小王", "line": "是啊，阳光很暖和，我想先去买点菜。"}
  ],
  "keywords": ["天气", "阳光", "买菜", "做饭", "打扫", "擦", "散步"],
  "new_words": [
    {"word": "西红柿", "pinyin": "xī hóng shì", "hsk": 5,
     "meaning": "tomato", "example": "那中午我做西红柿鸡蛋面，你觉得怎么样？"}
  ],
  "after_tasks": ["用中文说说：周末你一般在家做什么？"],
  "teaching": {
    "level_desc": "HSK4（CEFR B1+，词汇量 2000 词，书写字 400 字）",
    "speaking_ability": "能比较流利地讲述家庭生活等话题；能与人交流看法",
    "org_flow": "热身（5分钟）→ 核心活动（15分钟）→ 拓展/表演（10分钟）→ 总结",
    "rubric": ["语音清晰、句子自然", "词汇以本级词为主", "交际达成"]
  }
}
"""
import argparse
import html as _html
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def esc(s):
    if s is None:
        return ""
    return _html.escape(str(s), quote=True)


# 角色气泡配色（a=左，b=右，c/d/e 循环左侧换色）
ROLE_STYLES = [
    {"side": "a", "who": "#5a84c9", "bubble": "#e8f1fd", "border": "#bcd4f7", "color": "#1c3a63"},
    {"side": "b", "who": "#4a9a6a", "bubble": "#eaf7ef", "border": "#bfe3cd", "color": "#24543a"},
    {"side": "a", "who": "#9a6a4a", "bubble": "#fdf1e7", "border": "#f0d3b8", "color": "#5c3d24"},
    {"side": "a", "who": "#6a5a9a", "bubble": "#efeafb", "border": "#d3c8f0", "color": "#3c2d5c"},
    {"side": "a", "who": "#4a8a9a", "bubble": "#e6f4f7", "border": "#bfe0e8", "color": "#24505c"},
]


def mark_new_words(line, over_list):
    """把台词中的生词替换为悬停标注 span（按词长降序，避免子串误伤）。"""
    if not over_list:
        return esc(line)
    words = sorted(over_list, key=lambda o: len(o.get("word", "")), reverse=True)
    # 用占位符分两次替换，防止已插入的 span 被后续词匹配
    out = esc(line)
    ph = []
    for i, o in enumerate(words):
        w = o.get("word", "")
        if not w or w not in out:
            continue
        title = "%s %s（HSK%s）%s" % (
            w, o.get("pinyin", ""), o.get("hsk", "大纲外"), o.get("meaning", "")
        )
        ph_id = "\x01%d\x02" % i
        ph.append((ph_id, '<span class="oc" title="%s">%s</span>' % (esc(title), esc(w))))
        out = out.replace(w, ph_id, 1)
    for pid, tag in ph:
        out = out.replace(pid, tag)
    return out


def build_dialog_html(dlg, new_by_speaker):
    """生成气泡对话 HTML。new_by_speaker: speaker -> 生词列表"""
    characters = dlg.get("characters") or []
    role_of = {name: i for i, name in enumerate(characters)}
    n_roles = len(characters) or 2
    msgs = []
    for turn in dlg.get("dialogue") or []:
        sp = turn.get("speaker", "")
        line = turn.get("line", "")
        if not line:
            continue
        idx = role_of.get(sp, 0)
        st = ROLE_STYLES[idx % len(ROLE_STYLES)]
        line_html = mark_new_words(line, new_by_speaker.get(sp, []))
        radius = "border-top-left-radius:4px" if st["side"] == "a" else "border-top-right-radius:4px"
        msgs.append(
            '<div class="msg %s"><span class="who" style="color:%s">%s</span>'
            '<div class="bubble" style="background:%s;border:1px solid %s;color:%s;%s">%s</div>'
            '<div class="cover">点击查看原文</div></div>'
            % (st["side"], st["who"], esc(sp), st["bubble"], st["border"], st["color"], radius, line_html)
        )
    return "".join(msgs)


def build_switch_buttons(characters):
    """生成遮句按钮：全部显示 + 每个角色一个遮住按钮。"""
    btns = ['<button class="btn active" data-m="all" onclick="setMode(\'all\')">全部显示</button>']
    for c in characters:
        btns.append(
            '<button class="btn" data-m="%s" onclick="setMode(\'%s\')">遮住%s（扮演%s）</button>'
            % (esc(c), esc(c), esc(c), esc(c))
        )
    return "".join(btns)


def build_oc_card(new_words):
    """生词表卡（含原文例句）。"""
    if not new_words:
        return ""
    rows = []
    for o in new_words:
        rows.append(
            '<div class="oc-row">· <b>%s</b> %s（HSK%s）%s<br><span class="oc-ex">原文：%s</span></div>'
            % (esc(o.get("word", "")), esc(o.get("pinyin", "")),
               esc(str(o.get("hsk", "大纲外"))), esc(o.get("meaning", "")),
               esc(o.get("example", "")))
        )
    return (
        '<div class="card"><div class="card-title">📖 生词表</div>'
        '<div class="gram">%s</div></div>' % "".join(rows)
    )


def build_keyword_card(dlg):
    kws = dlg.get("keywords") or []
    if not kws:
        return ""
    chips = "".join('<span class="kw">%s</span>' % esc(w) for w in kws)
    return '<div class="card"><div class="card-title">🔑 关键词</div>%s</div>' % chips


def build_grammar_card(dlg):
    gps = dlg.get("grammar_points") or []
    if not gps:
        return ""
    rows = "".join("<div>· %s</div>" % esc(g) for g in gps)
    return '<div class="card"><div class="card-title">🧩 重点句型</div><div class="gram">%s</div></div>' % rows


def build_task_card(dlg):
    tasks = dlg.get("after_tasks") or []
    if not tasks:
        return ""
    rows = "".join("<div>%d. %s</div>" % (i + 1, esc(t)) for i, t in enumerate(tasks))
    return '<div class="card"><div class="card-title">📌 学后任务</div><div class="task">%s</div></div>' % rows


def build_teacher_card(dlg):
    t = dlg.get("teaching") or {}
    bits = []
    if t.get("level_desc"):
        bits.append(('<tr><td class="k">等级</td><td class="v">%s</td></tr>') % esc(t["level_desc"]))
    if dlg.get("topic_tree"):
        bits.append(('<tr><td class="k">话题树位置</td><td class="v">%s</td></tr>') % esc(dlg["topic_tree"]))
    if dlg.get("functions"):
        bits.append(('<tr><td class="k">交际功能</td><td class="v">%s</td></tr>') % esc(dlg["functions"]))
    if t.get("speaking_ability"):
        bits.append(('<tr><td class="k">大纲"说"能力</td><td class="v">%s</td></tr>') % esc(t["speaking_ability"]))
    if t.get("org_flow"):
        bits.append(('<tr><td class="k">组织流程</td><td class="v">%s</td></tr>') % esc(t["org_flow"]))
    rubric = t.get("rubric") or []
    if rubric:
        lis = "".join("<li>%s</li>" % esc(r) for r in rubric)
        bits.append(('<tr><td class="k">评分要点</td><td class="v"><ul class="rb">%s</ul></td></tr>') % lis)
    if not bits:
        return ""
    return (
        '<div class="card gray"><div class="card-title">👨‍🏫 教师视图</div>'
        '<table class="info">%s</table></div>' % "".join(bits)
    )


PAGE_CSS = """
  *{box-sizing:border-box}
  body{font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;margin:0;background:#f2f5fa;color:#2b3a52;line-height:1.7}
  .wrap{max-width:760px;margin:0 auto;padding:28px 18px 60px}
  .hero{background:linear-gradient(135deg,#1f4fd8,#3b6df0);color:#fff;border-radius:16px;padding:24px 26px;margin-bottom:16px}
  .hero h1{margin:0 0 8px;font-size:22px;letter-spacing:1px}
  .hero .tags{font-size:13px;opacity:.92}
  .tag{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:20px;padding:2px 10px;margin-right:6px}
  .card{background:#fff;border:1px solid #e3e8f0;border-radius:14px;padding:18px 20px;margin-bottom:14px;box-shadow:0 1px 3px rgba(15,41,93,.05)}
  .card.gray{background:#f6f8fb;border-color:#dde4ee}
  .card-title{font-size:15px;font-weight:700;color:#1c2b45;margin-bottom:10px}
  .ctrl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
  .btn{display:inline-block;background:#fff;color:#1f4fd8;border:1.5px solid #d6e1ff;border-radius:20px;padding:5px 14px;font-size:13px;cursor:pointer}
  .btn.active{background:#1f4fd8;color:#fff;border-color:#1f4fd8}
  .ctrl .hint{font-size:12px;color:#8a93a6;margin-left:4px}
  .dialog{display:flex;flex-direction:column;gap:14px}
  .msg{display:flex;flex-direction:column}
  .msg .who{font-size:12px;color:#8a93a6;margin-bottom:3px}
  .msg .bubble{max-width:74%;padding:10px 14px;border-radius:14px;font-size:17px;line-height:1.7;position:relative}
  .msg.a{align-items:flex-start}
  .msg.b{align-items:flex-end}
  .msg.a .who{color:#5a84c9}
  .msg.b .who{color:#4a9a6a}
  .msg .cover{display:none;max-width:74%;padding:10px 14px;border-radius:14px;border:1.5px dashed #b9c6d8;background:#f8fafd;color:#8a93a6;font-size:13px;cursor:pointer;text-align:center}
  .msg .cover:hover{background:#eef3ff;color:#1f4fd8;border-color:#9db6e8}
  .msg.hidden .bubble{display:none}
  .msg.hidden .cover{display:block}
  .revealed .bubble{outline:2px solid #f1c40f}
  .oc{border-bottom:1.5px dashed #e67e22;background:#fef5ec;color:#a35a00;padding:0 2px;border-radius:3px;cursor:help}
  .oc::after{content:"⚠";font-size:10px;vertical-align:super;margin-left:1px;color:#e67e22}
  .oc-tip{font-size:12px;color:#a35a00;background:#fef5ec;border:1px solid #f5d9b8;border-radius:8px;padding:6px 10px;margin-top:12px}
  .oc-row{margin-bottom:10px}
  .oc-ex{font-size:12px;color:#8a93a6}
  .kw{display:inline-block;background:#eef3ff;color:#1f4fd8;border:1px solid #d6e1ff;border-radius:16px;padding:2px 12px;margin:0 6px 8px 0;font-size:13px}
  .gram{font-size:13px;color:#33415c;line-height:1.9}
  .gram b{color:#1f4fd8}
  .task{font-size:14px;color:#33415c;line-height:1.9}
  table.info{width:100%;border-collapse:collapse;margin:4px 0;font-size:13px}
  table.info td{border:1px solid #e3e8f0;padding:7px 10px;vertical-align:top}
  table.info td.k{width:110px;font-weight:600;color:#1c2b45;white-space:nowrap;background:#f7f9fc}
  table.info ul.rb{margin:0;padding-left:18px}
  .foot{color:#8a93a6;font-size:12px;text-align:center;margin-top:18px}
  @media print{
    body{background:#fff}
    .wrap{max-width:100%;padding:0}
    .hero,.card{box-shadow:none;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .ctrl .btn{display:none}
  }
"""


def render(dlg):
    characters = dlg.get("characters") or []
    new_all = dlg.get("new_words") or []
    new_by_speaker = {}
    for o in new_all:
        w = o.get("word", "")
        for turn in dlg.get("dialogue") or []:
            if w and w in turn.get("line", ""):
                new_by_speaker.setdefault(turn.get("speaker", ""), []).append(o)

    dialog_html = build_dialog_html(dlg, new_by_speaker)
    btns = build_switch_buttons(characters)
    tags = "".join('<span class="tag">%s</span>' % esc(t) for t in (dlg.get("tags") or []))
    oc_tip = (
        '<div class="oc-tip">台词中带 <span class="oc" title="示例：生词">⚠</span>'
        ' 的词为生词（%s 及以上），鼠标悬停查看拼音与释义。</div>'
        % esc(dlg.get("level_label", "本级"))
    )
    body = (
        '<div class="card"><div class="card-title">🎭 对话自练</div>'
        '<div class="ctrl">%s<span class="hint">被遮住的台词点击即可查看原文</span></div>'
        '<div class="dialog" id="dlg">%s</div>%s</div>'
        % (btns, dialog_html, oc_tip)
    )
    body += build_keyword_card(dlg)
    body += build_grammar_card(dlg)
    body += build_oc_card(new_all)
    body += build_task_card(dlg)
    body += build_teacher_card(dlg)

    title = esc(dlg.get("title", "对话素材"))
    meta = (
        '<div class="hero"><h1>《%s》</h1><div class="tags">%s</div></div>'
        % (title, tags)
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n"
        "<div class=\"wrap\">\n%s\n%s\n<div class=\"foot\">对话素材 · %s · "
        "由 HSK 对话材料生成器自动生成，可打印或保存为 PDF。</div>\n"
        "</div>\n<script>\nvar dlg=document.getElementById('dlg');\n"
        "function setMode(mode){\n"
        "  var btns=document.querySelectorAll('.btn');\n"
        "  for(var i=0;i<btns.length;i++) btns[i].classList.remove('active');\n"
        "  var idx=[].slice.call(btns).findIndex(function(b){return b.getAttribute('data-m')===mode;});\n"
        "  if(idx>=0) btns[idx].classList.add('active');\n"
        "  var msgs=dlg.querySelectorAll('.msg');\n"
        "  for(var i=0;i<msgs.length;i++){\n"
        "    var sp=msgs[i].querySelector('.who').textContent;\n"
        "    if(mode==='all') msgs[i].classList.remove('hidden');\n"
        "    else if(sp===mode) msgs[i].classList.add('hidden');\n"
        "    else msgs[i].classList.remove('hidden');\n"
        "  }\n"
        "}\n"
        "dlg.addEventListener('click', function(e){\n"
        "  var t=e.target;\n"
        "  if(t&&t.classList.contains('cover')){\n"
        "    var msg=t.parentNode;\n"
        "    msg.classList.remove('hidden');\n"
        "    msg.classList.add('revealed');\n"
        "  }\n"
        "});\n"
        "</script>\n</body>\n</html>" % (
            title, PAGE_CSS, meta, body,
            esc(dlg.get("level_label", "HSK 对话学习页"))
        )
    )


def main():
    ap = argparse.ArgumentParser(description="对话素材 HTML 学习页渲染器")
    ap.add_argument("--dialogue-json", required=True, help="对话素材 JSON 路径")
    ap.add_argument("--output", default="/mnt/user-data/outputs/dialogue_display.html", help="输出 HTML 路径")
    args = ap.parse_args()

    if not os.path.exists(args.dialogue_json):
        print(json.dumps({"error": "缺少输入：--dialogue-json 文件不存在"}, ensure_ascii=False))
        sys.exit(1)
    with open(args.dialogue_json, encoding="utf-8") as f:
        dlg = json.load(f)

    html = render(dlg)
    out = args.output
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    n_turns = len(dlg.get("dialogue") or [])
    print(json.dumps({"success": True, "path": out, "turns": n_turns,
                      "new_words": len(dlg.get("new_words") or [])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
