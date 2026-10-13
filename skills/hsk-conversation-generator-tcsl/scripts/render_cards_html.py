#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""问题卡 / 角色扮演卡 HTML 渲染器（HSK 对话材料生成器配套）。

读取卡片素材 JSON（话题、分级问题/角色任务、教师信息），生成一份
自包含、可直接打印/下载的卡片学习页 HTML：

  - discussion（话题问题卡）：热身/核心/拓展三级递进徽章 + 每张卡问题
    大字显示 + 教师提示（答题框架）默认收起、点击展开 + 全部展开/收起
  - roleplay（角色扮演卡）：每张卡《名称》+ 情景横条 + A/B 角色双栏 +
    任务目标高亮 + 语言要求列表 + 参考表达胶囊 + 表演时间徽章
  - 教师视图：教学信息、组织流程、评分要点

用法:
  python3 render_cards_html.py --cards-json /path/cards.json \
      --mode discussion --output /mnt/user-data/outputs/cards_话题_HSKx.html
  python3 render_cards_html.py --cards-json /path/cards.json \
      --mode roleplay --output /mnt/user-data/outputs/roleplay_话题_HSKx.html
  （--mode 省略时自动按 JSON 的 "type" 字段判断）

discussion JSON 格式:
{
  "title": "HSK4 话题问题卡：网上购物",
  "hsk_level": 4,
  "level_label": "HSK4",
  "tags": ["HSK4", "课堂讨论", "6题"],
  "topic": "网上购物",
  "topic_tree": "科学技术 > 科技发展",
  "cards": [
    {"stage": "warmup", "question": "你经常在网上买东西吗？",
     "teacher_tip": "用“经常/有时候/很少”"},
    {"stage": "core", "question": "网上购物有什么好处？",
     "teacher_tip": "用“方便/便宜/选择多”"},
    {"stage": "extended", "question": "你觉得实体店会消失吗？为什么？",
     "teacher_tip": "说出你的看法和两个理由"}
  ],
  "teaching": {
    "level_desc": "HSK4（CEFR B1+，词汇量 2000 词，书写字 400 字）",
    "speaking_ability": "能比较流利地讲述家庭生活等话题；能与人交流看法",
    "org_flow": "热身（5分钟）→ 核心活动（15分钟）→ 拓展/表演（10分钟）→ 总结",
    "rubric": ["语音清晰、句子自然", "词汇以本级词为主", "交际达成"]
  }
}

roleplay JSON 格式:
{
  "title": "HSK4 角色扮演任务卡",
  "hsk_level": 4,
  "level_label": "HSK4",
  "tags": ["HSK4", "情景表演", "4个任务"],
  "cards": [
    {
      "name": "去银行办卡",
      "topic_tree": "职场生活 > 日常办公",
      "scenario": "你去银行办银行卡",
      "role_a": {"name": "你：顾客", "focus": "说明办卡需求、配合填表"},
      "role_b": {"name": "银行职员", "focus": "引导办卡流程、告知取卡时间"},
      "goal": "办成银行卡，知道取卡时间",
      "lang_reqs": ["说明要办什么", "配合填写和签字", "问清流程和时间"],
      "expressions": ["我想办一张银行卡。", "请填一下这张表。",
                      "请在这里签字。", "三个工作日后来取。"],
      "duration": "6-8分钟"
    }
  ],
  "teaching": { ...同上... }
}
"""
import argparse
import html as _html
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def esc(s):
    if s is None:
        return ""
    return _html.escape(str(s), quote=True)


# 分级递进配色（warmup 绿 / core 蓝 / extended 橙）
STAGE_STYLE = {
    "warmup": {"label": "热身", "color": "#2e9e5b", "bg": "#eaf7ef", "border": "#bfe3cd"},
    "core": {"label": "核心", "color": "#1f4fd8", "bg": "#eef3ff", "border": "#d6e1ff"},
    "extended": {"label": "拓展", "color": "#d97a1f", "bg": "#fdf1e7", "border": "#f0d3b8"},
}
STAGE_ORDER = ["warmup", "core", "extended"]


def build_teacher_card(cfg):
    t = cfg.get("teaching") or {}
    bits = []
    if t.get("level_desc"):
        bits.append(('<tr><td class="k">等级</td><td class="v">%s</td></tr>') % esc(t["level_desc"]))
    if cfg.get("topic_tree"):
        bits.append(('<tr><td class="k">话题树位置</td><td class="v">%s</td></tr>') % esc(cfg["topic_tree"]))
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


def build_discussion(cfg):
    cards = cfg.get("cards") or []
    rows = []
    for i, c in enumerate(cards):
        stage = c.get("stage", "core")
        st = STAGE_STYLE.get(stage, STAGE_STYLE["core"])
        tip = c.get("teacher_tip") or ""
        tip_html = (
            '<div class="tip-body">%s</div>' % esc(tip)
        ) if tip else '<div class="tip-body tip-empty">（无教师提示）</div>'
        rows.append(
            '<div class="qcard" data-stage="%s">'
            '<div class="qhead"><span class="qnum">%d</span>'
            '<span class="stage" style="color:%s;background:%s;border-color:%s">%s</span>'
            '<button class="tip-toggle" onclick="toggleTip(this)">💡 教师提示</button></div>'
            '<div class="qtext">%s</div>%s</div>'
            % (esc(stage), i + 1, st["color"], st["bg"], st["border"], esc(st["label"]),
               esc(c.get("question", "")), tip_html)
        )
    meta = ""
    if cfg.get("topic"):
        meta += '<div class="meta"><span class="mk">话题</span>%s</div>' % esc(cfg["topic"])
    body = (
        '<div class="ctrl">'
        '<button class="btn" onclick="toggleAll(true)">全部展开</button>'
        '<button class="btn" onclick="toggleAll(false)">全部收起</button>'
        '<span class="hint">点击“教师提示”查看答题框架</span></div>'
        '<div class="cards">%s</div>%s'
        % ("".join(rows), meta)
    )
    body += build_teacher_card(cfg)
    return body


def build_roleplay(cfg):
    cards = cfg.get("cards") or []
    rows = []
    for i, c in enumerate(cards):
        ra = c.get("role_a") or {}
        rb = c.get("role_b") or {}
        reqs = "".join('<li>%s</li>' % esc(r) for r in (c.get("lang_reqs") or []))
        exprs = "".join('<span class="pill">%s</span>' % esc(e) for e in (c.get("expressions") or []))
        tree = '<div class="rtree">%s</div>' % esc(c.get("topic_tree", "")) if c.get("topic_tree") else ""
        rows.append(
            '<div class="rcard">'
            '<div class="rhead"><span class="rnum">%d</span><span class="rtitle">《%s》</span>%s'
            '<span class="rtime">⏱ %s</span></div>'
            '<div class="scenario">📌 情景：%s</div>'
            '<div class="roles">'
            '<div class="role roleA"><div class="role-name">A · %s</div><div class="role-focus">%s</div></div>'
            '<div class="role roleB"><div class="role-name">B · %s</div><div class="role-focus">%s</div></div>'
            '</div>'
            '<div class="goal">🎯 任务目标：%s</div>'
            '<div class="lang"><div class="lang-title">🗣 语言要求</div><ul>%s</ul></div>'
            '<div class="exprs"><div class="lang-title">💬 参考表达</div><div class="pill-row">%s</div></div>'
            '</div>'
            % (i + 1, esc(c.get("name", "")), tree,
               esc(c.get("duration", "")),
               esc(c.get("scenario", "")),
               esc(ra.get("name", "")), esc(ra.get("focus", "")),
               esc(rb.get("name", "")), esc(rb.get("focus", "")),
               esc(c.get("goal", "")), reqs, exprs)
        )
    body = '<div class="cards">%s</div>' % "".join(rows)
    body += build_teacher_card(cfg)
    return body


PAGE_CSS = """
  *{box-sizing:border-box}
  body{font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;margin:0;background:#f2f5fa;color:#2b3a52;line-height:1.7}
  .wrap{max-width:820px;margin:0 auto;padding:28px 18px 60px}
  .hero{background:linear-gradient(135deg,#1f4fd8,#3b6df0);color:#fff;border-radius:16px;padding:24px 26px;margin-bottom:16px}
  .hero h1{margin:0 0 8px;font-size:22px;letter-spacing:1px}
  .hero .tags{font-size:13px;opacity:.92}
  .tag{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:20px;padding:2px 10px;margin-right:6px}
  .card{background:#fff;border:1px solid #e3e8f0;border-radius:14px;padding:18px 20px;margin-bottom:14px;box-shadow:0 1px 3px rgba(15,41,93,.05)}
  .card.gray{background:#f6f8fb;border-color:#dde4ee}
  .card-title{font-size:15px;font-weight:700;color:#1c2b45;margin-bottom:10px}
  .ctrl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
  .btn{display:inline-block;background:#fff;color:#1f4fd8;border:1.5px solid #d6e1ff;border-radius:20px;padding:5px 14px;font-size:13px;cursor:pointer}
  .btn:hover{background:#eef3ff}
  .ctrl .hint{font-size:12px;color:#8a93a6;margin-left:4px}
  /* 问题卡 */
  .qcard{background:#fff;border:1px solid #e3e8f0;border-radius:14px;padding:16px 20px;margin-bottom:12px;box-shadow:0 1px 3px rgba(15,41,93,.05)}
  .qhead{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap}
  .qnum{display:inline-flex;width:26px;height:26px;border-radius:50%;background:#1f4fd8;color:#fff;align-items:center;justify-content:center;font-size:13px;font-weight:700}
  .stage{display:inline-block;border:1px solid;border-radius:20px;padding:1px 12px;font-size:12px;font-weight:600}
  .tip-toggle{margin-left:auto;background:#fff;color:#8a6d1f;border:1.5px solid #f0d99a;border-radius:20px;padding:3px 12px;font-size:12px;cursor:pointer}
  .tip-toggle:hover{background:#fdf6e3}
  .qtext{font-size:19px;font-weight:600;color:#1c2b45;letter-spacing:.5px}
  .tip-body{display:none;margin-top:10px;padding:10px 14px;background:#fdf8ec;border-left:3px solid #f0c14e;border-radius:6px;font-size:14px;color:#6b5a1f}
  .tip-body.open{display:block}
  .tip-body.tip-empty{color:#b0b7c4}
  .meta{margin:6px 2px 16px}
  .mk{display:inline-block;background:#1f4fd8;color:#fff;border-radius:12px;padding:1px 10px;font-size:12px;margin-right:8px}
  /* 角色扮演卡 */
  .rcard{background:#fff;border:1px solid #e3e8f0;border-radius:16px;padding:20px 22px;margin-bottom:16px;box-shadow:0 1px 3px rgba(15,41,93,.05)}
  .rhead{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
  .rnum{display:inline-flex;width:28px;height:28px;border-radius:50%;background:#d97a1f;color:#fff;align-items:center;justify-content:center;font-size:14px;font-weight:700}
  .rtitle{font-size:18px;font-weight:800;color:#1c2b45}
  .rtree{font-size:12px;color:#8a93a6;background:#f2f5fa;border-radius:12px;padding:2px 10px}
  .rtime{margin-left:auto;font-size:13px;font-weight:600;color:#d97a1f;background:#fdf1e7;border:1px solid #f0d3b8;border-radius:20px;padding:3px 12px}
  .scenario{padding:10px 14px;background:#eef3ff;border-left:4px solid #1f4fd8;border-radius:8px;font-size:15px;color:#1c3a63;margin-bottom:12px}
  .roles{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
  .role{border-radius:10px;padding:12px 14px;font-size:14px}
  .roleA{background:#eaf7ef;border:1px solid #bfe3cd}
  .roleB{background:#fdf1e7;border:1px solid #f0d3b8}
  .role-name{font-weight:800;margin-bottom:4px}
  .roleA .role-name{color:#24543a}
  .roleB .role-name{color:#5c3d24}
  .role-focus{color:#55627c;font-size:13px}
  .goal{padding:10px 14px;background:#fdf8ec;border:1px solid #f0d99a;border-radius:8px;font-size:15px;color:#6b5a1f;font-weight:600;margin-bottom:12px}
  .lang{margin-bottom:12px}
  .lang-title{font-size:13px;font-weight:700;color:#1c2b45;margin-bottom:6px}
  .lang ul{margin:0;padding-left:4px;list-style:none}
  .lang li{position:relative;padding:4px 4px 4px 20px;font-size:14px;color:#33415c}
  .lang li::before{content:"";position:absolute;left:4px;top:9px;width:8px;height:8px;border-radius:2px;background:#1f4fd8}
  .pill-row{display:flex;flex-wrap:wrap;gap:8px}
  .pill{display:inline-block;background:#f6f8fb;border:1px solid #dde4ee;color:#33415c;border-radius:16px;padding:4px 14px;font-size:14px}
  .pill:hover{background:#eef3ff;border-color:#9db6e8;color:#1f4fd8}
  table.info{width:100%;border-collapse:collapse;margin:4px 0;font-size:13px}
  table.info td{border:1px solid #e3e8f0;padding:7px 10px;vertical-align:top}
  table.info td.k{width:110px;font-weight:600;color:#1c2b45;white-space:nowrap;background:#f7f9fc}
  table.info ul.rb{margin:0;padding-left:18px}
  .foot{color:#8a93a6;font-size:12px;text-align:center;margin-top:18px}
  @media (max-width:600px){.roles{grid-template-columns:1fr}}
  @media print{
    body{background:#fff}
    .wrap{max-width:100%;padding:0}
    .hero,.card,.qcard,.rcard{box-shadow:none;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .ctrl .btn{display:none}
    .tip-body{display:block !important}
  }
"""


def render(cfg, mode):
    tags = "".join('<span class="tag">%s</span>' % esc(t) for t in (cfg.get("tags") or []))
    if mode == "discussion":
        body = build_discussion(cfg)
    else:
        body = build_roleplay(cfg)
    title = esc(cfg.get("title", "口语卡片"))
    meta = '<div class="hero"><h1>%s</h1><div class="tags">%s</div></div>' % (title, tags)
    mode_label = "话题问题卡" if mode == "discussion" else "角色扮演任务卡"
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n"
        "<div class=\"wrap\">\n%s\n%s\n<div class=\"foot\">%s · %s · "
        "由 HSK 对话材料生成器自动生成，可打印或保存为 PDF。</div>\n"
        "</div>\n<script>\n"
        "function toggleTip(btn){\n"
        "  var tb=btn.closest('.qcard').querySelector('.tip-body');\n"
        "  if(tb){tb.classList.toggle('open');\n"
        "    btn.textContent=tb.classList.contains('open')?'💡 收起提示':'💡 教师提示';}\n"
        "}\n"
        "function toggleAll(open){\n"
        "  var bodies=document.querySelectorAll('.tip-body');\n"
        "  var btns=document.querySelectorAll('.tip-toggle');\n"
        "  for(var i=0;i<bodies.length;i++){\n"
        "    if(open)bodies[i].classList.add('open');else bodies[i].classList.remove('open');}\n"
        "  for(var j=0;j<btns.length;j++){\n"
        "    btns[j].textContent=open?'💡 收起提示':'💡 教师提示';}\n"
        "}\n"
        "</script>\n</body>\n</html>" % (
            title, PAGE_CSS, meta, body,
            mode_label, esc(cfg.get("level_label", "HSK 口语卡片"))
        )
    )


def main():
    ap = argparse.ArgumentParser(description="问题卡/角色扮演卡 HTML 渲染器")
    ap.add_argument("--cards-json", required=True, help="卡片素材 JSON 路径")
    ap.add_argument("--mode", choices=["discussion", "roleplay"], default="",
                    help="卡片类型（省略时按 JSON 的 type 字段判断）")
    ap.add_argument("--output", default="/mnt/user-data/outputs/cards_display.html",
                    help="输出 HTML 路径")
    args = ap.parse_args()

    if not os.path.exists(args.cards_json):
        print(json.dumps({"error": "缺少输入：--cards-json 文件不存在"}, ensure_ascii=False))
        sys.exit(1)
    with open(args.cards_json, encoding="utf-8") as f:
        cfg = json.load(f)

    mode = args.mode or cfg.get("type", "discussion")
    if mode not in ("discussion", "roleplay"):
        print(json.dumps({"error": "无法识别卡片类型：%s（需 discussion 或 roleplay）" % mode},
                         ensure_ascii=False))
        sys.exit(1)

    html = render(cfg, mode)
    out = args.output
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(json.dumps({"success": True, "path": out, "mode": mode,
                      "cards": len(cfg.get("cards") or [])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
