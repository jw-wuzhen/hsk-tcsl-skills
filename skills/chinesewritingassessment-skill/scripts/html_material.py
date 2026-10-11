from __future__ import annotations

import html
import re
from collections import OrderedDict


LEVEL_COLORS = {
    "1": "#dff5e5",
    "2": "#e4f0ff",
    "3": "#fff1c7",
    "4": "#ffe3d5",
    "5": "#f0e3ff",
    "6": "#ffdfe8",
}

ERROR_TYPE_COLORS = {
    "量词缺失": "#e67e22", "量词误用": "#d35400", "搭配错误": "#c0392b",
    "虚词误用": "#8e44ad", "用词错误": "#2980b9", "句式冗余": "#7f8c8d",
    "冗余重复": "#95a5a6", "语序问题": "#16a085", "语义协调": "#e91e63",
    "篇章衔接": "#27ae60", "逻辑问题": "#2c3e50", "无明显错误": "#27ae60",
}

DIMENSION_LABELS = {
    "content_and_task_response": "内容与任务完成",
    "organization_and_coherence": "组织与连贯",
    "language_accuracy_and_range": "语言准确性与广度",
    "lexical_and_grammatical_control": "词汇与语法控制",
}
DIMENSION_LABELS_EN = {
    "content_and_task_response": "Content & Task Response",
    "organization_and_coherence": "Organization & Coherence",
    "language_accuracy_and_range": "Language Accuracy & Range",
    "lexical_and_grammatical_control": "Lexical & Grammatical Control",
}
ERROR_TYPE_EN = {
    "量词缺失": "Missing Measure Word", "量词误用": "Misused Measure Word",
    "搭配错误": "Collocation Error", "虚词误用": "Function Word Error",
    "用词错误": "Word Choice Error", "句式冗余": "Sentence Redundancy",
    "冗余重复": "Repetition", "语序问题": "Word Order Issue",
    "语义协调": "Semantic Coordination", "篇章衔接": "Discourse Cohesion",
    "逻辑问题": "Logic Issue", "无明显错误": "No Obvious Errors",
}
CONFIDENCE_EN = {"高": "Confirmed", "中": "Possible"}


def split_sentences(text):
    parts = re.split(r"(?<=[。！？!?；;])\s*", text)
    return [p.strip() for p in parts if p.strip()]


def _clean_level(level):
    match = re.search(r"[1-6]", str(level))
    return match.group(0) if match else "?"


def _tokenize(text, words):
    ordered_words = sorted({w["word"] for w in words if w.get("word")}, key=len, reverse=True)
    tokens, index = [], 0
    while index < len(text):
        matched = next((word for word in ordered_words if text.startswith(word, index)), None)
        if matched:
            tokens.append(("word", matched))
            index += len(matched)
        else:
            tokens.append(("char", text[index]))
            index += 1
    return tokens


def _annotated_text(text, words):
    """逐字标注拼音：每个字的拼音精确对应在字上方。"""
    word_map = {w["word"]: w for w in words}
    parts = []
    for token_type, value in _tokenize(text, words):
        if token_type == "char":
            parts.append(html.escape(value))
            continue
        item = word_map[value]
        level = _clean_level(item.get("level"))
        color = LEVEL_COLORS.get(level, "#f0f0f0")
        pinyin = item.get("pinyin", "") or ""
        en_def = item.get("en_def", "") or item.get("usage_note", "") or ""
        title = f"HSK{level} | {en_def}"
        pinyin_parts = pinyin.split() if pinyin else []
        if len(pinyin_parts) == len(value) and len(value) > 1:
            ruby_chars = []
            for i, char in enumerate(value):
                ruby_chars.append(
                    f'<ruby class="word-char" title="{html.escape(title, quote=True)}">'
                    f'{html.escape(char)}<rt>{html.escape(pinyin_parts[i])}</rt></ruby>'
                )
            parts.append(
                f'<span class="word-group level-{level}" style="--level-color:{color}">'
                + ''.join(ruby_chars) + '</span>'
            )
        else:
            parts.append(
                f'<ruby class="word level-{level}" style="--level-color:{color}" '
                f'title="{html.escape(title, quote=True)}">{html.escape(value)}'
                f'<rt>{html.escape(pinyin)}</rt></ruby>'
            )
    return "".join(parts)


def _sentence_cards(text, issues):
    sentences = split_sentences(text)
    cards = []
    for index, sentence in enumerate(sentences, 1):
        related = [item for item in issues if item.get("sentence_index") == index]
        if related:
            note = "；".join(item["issue"] for item in related)
            badge, tone = "需要关注", "attention"
        else:
            note = "句子结构整体清晰，可作为阅读与复述练习。"
            badge, tone = "表达观察", "steady"
        cards.append(
            f'<article class="sentence-card {tone}"><div class="sentence-head">'
            f'<span>句子 {index} / Sentence {index}</span><b>{badge}</b></div>'
            f'<p>{html.escape(sentence)}</p><small>{html.escape(note)}</small></article>'
        )
    return "".join(cards)


def _error_type_color(error_type):
    return ERROR_TYPE_COLORS.get(error_type, "#666")


def _bilingual(zh, en):
    """生成中英双语标题。"""
    return f'{zh} <span class="en-sub">{en}</span>'


def _build_error_panel(issues):
    real_issues = [i for i in issues if i.get("type") != "无明显错误"]
    confirmed = sum(1 for i in real_issues if i.get("confidence", "高") == "高")
    possible = sum(1 for i in real_issues if i.get("confidence", "高") == "中")

    if not real_issues:
        return f'''
        <section class="panel core-panel" id="error-location">
          <div class="panel-header">
            <span class="panel-icon">🔍</span>
            <div><h2>{_bilingual("一、语法/语义错误定位", "Grammar & Semantic Error Detection")}</h2>
            <p class="panel-sub">识别作文中的语病、搭配错误、用词错误、逻辑问题 / Identify grammar, collocation, word choice and logic issues</p></div>
          </div>
          <div class="empty-state">
            <div class="empty-icon">✓</div>
            <h3>未检测到明显的语法或语义问题</h3>
            <p class="en-sub">No obvious grammar or semantic issues detected</p>
            <p>作文表达整体准确，可继续提升表达自然度与篇章组织能力。</p>
          </div>
        </section>'''

    cards = []
    for idx, issue in enumerate(real_issues, 1):
        etype = issue.get("type", "未知")
        color = _error_type_color(etype)
        etype_en = ERROR_TYPE_EN.get(etype, etype)
        confidence = issue.get("confidence", "高")
        conf_class = "conf-high" if confidence == "高" else "conf-mid"
        conf_label = f'{confidence} / {CONFIDENCE_EN.get(confidence, confidence)}'
        cards.append(f'''
        <article class="error-card" style="--error-color:{color}">
          <div class="error-card-head">
            <span class="error-num">{idx}</span>
            <span class="error-type-tag">{html.escape(etype)} <small>{html.escape(etype_en)}</small></span>
            <span class="confidence-badge {conf_class}">{conf_label}</span>
            <span class="error-location">{html.escape(issue.get("location", ""))}</span>
          </div>
          <div class="error-card-body">
            <div class="error-row">
              <span class="row-label">原文片段<br><small>Original</small></span>
              <span class="error-fragment">{html.escape(issue.get("original_fragment", ""))}</span>
            </div>
            <div class="error-row">
              <span class="row-label">问题说明<br><small>Issue</small></span>
              <span>{html.escape(issue.get("issue", ""))}</span>
            </div>
            <div class="error-row suggestion-row">
              <span class="row-label">修改建议<br><small>Suggestion</small></span>
              <span class="suggestion-text">{html.escape(issue.get("suggestion", ""))}</span>
            </div>
          </div>
        </article>''')

    return f'''
    <section class="panel core-panel" id="error-location">
      <div class="panel-header">
        <span class="panel-icon">🔍</span>
        <div><h2>{_bilingual("一、语法/语义错误定位", "Grammar & Semantic Error Detection")}</h2>
        <p class="panel-sub">识别作文中的语病、搭配错误、用词错误、逻辑问题 / Identify grammar, collocation, word choice and logic issues</p></div>
      </div>
      <div class="error-stats">
        <div class="stat-item"><span class="stat-num">{len(real_issues)}</span><span class="stat-label">问题总数<br><small>Total</small></span></div>
        <div class="stat-item"><span class="stat-num conf-high-text">{confirmed}</span><span class="stat-label">确定错误<br><small>Confirmed</small></span></div>
        <div class="stat-item"><span class="stat-num conf-mid-text">{possible}</span><span class="stat-label">可能问题<br><small>Possible</small></span></div>
      </div>
      <div class="error-list">{''.join(cards)}</div>
    </section>'''


def _build_attribution_panel(attribution_report, reference_sources):
    if not attribution_report:
        return ''
    real_attrs = [a for a in attribution_report if a.get("type") != "无明显错误"]
    if not real_attrs:
        return f'''
        <section class="panel core-panel" id="attribution">
          <div class="panel-header">
            <span class="panel-icon">🧩</span>
            <div><h2>{_bilingual("二、错题归因报告", "Error Attribution Report")}</h2>
            <p class="panel-sub">基于错误定位，输出错因分析，关联权威国际中文教学资料中的汉语知识点 / Analyze error causes and link to Chinese grammar knowledge points</p></div>
          </div>
          <div class="empty-state"><p>无需要归因的错误。<br><small class="en-sub">No errors to attribute.</small></p></div>
        </section>'''

    cards = []
    for idx, attr in enumerate(real_attrs, 1):
        etype = attr.get("type", "")
        color = _error_type_color(etype)
        etype_en = ERROR_TYPE_EN.get(etype, etype)
        knowledge_points = attr.get("knowledge_points", []) or []
        kp_tags = "".join(f'<span class="kp-tag">{html.escape(kp)}</span>' for kp in knowledge_points)
        related_words = attr.get("related_hsk_words", []) or []
        rw_tags = "".join(f'<span class="rw-tag">{html.escape(w.get("word", w) if isinstance(w, dict) else str(w))}</span>' for w in related_words[:8])

        cards.append(f'''
        <article class="attr-card" style="--attr-color:{color}">
          <div class="attr-card-head">
            <span class="attr-num">{idx}</span>
            <span class="attr-type">{html.escape(etype)} <small>{html.escape(etype_en)}</small></span>
            <span class="attr-location">{html.escape(attr.get("location", ""))}</span>
          </div>
          <div class="attr-card-body">
            <div class="attr-row">
              <span class="row-label">对应问题<br><small>Issue</small></span>
              <span>{html.escape(attr.get("issue", ""))}</span>
            </div>
            <div class="attr-row">
              <span class="row-label">错因分析<br><small>Cause</small></span>
              <span class="attr-text">{html.escape(attr.get("attribution", ""))}</span>
            </div>
            <div class="attr-row">
              <span class="row-label">关联知识点<br><small>Knowledge Points</small></span>
              <div class="tag-group">{kp_tags or '<span class="tag-empty">待补充</span>'}</div>
            </div>
            {f'<div class="attr-row"><span class="row-label">关联HSK词汇<br><small>HSK Words</small></span><div class="tag-group">{rw_tags}</div></div>' if rw_tags else ''}
            <div class="attr-row">
              <span class="row-label">练习建议<br><small>Practice</small></span>
              <span class="suggestion-text">{html.escape(attr.get("suggestion", ""))}</span>
            </div>
          </div>
        </article>''')

    ref_html = ""
    if reference_sources:
        if isinstance(reference_sources, dict):
            sources = reference_sources.get("sources", []) or reference_sources.get("references", [])
        elif isinstance(reference_sources, list):
            sources = reference_sources
        else:
            sources = []
        if sources:
            ref_items = []
            for s in sources:
                if isinstance(s, dict):
                    name = s.get("name", s.get("title", ""))
                    url = s.get("url", s.get("link", ""))
                    desc = s.get("description", s.get("desc", ""))
                    if url:
                        ref_items.append(f'<li><a href="{html.escape(url)}" target="_blank">{html.escape(name)}</a> — {html.escape(desc)}</li>')
                    else:
                        ref_items.append(f'<li>{html.escape(name)} — {html.escape(desc)}</li>')
            if ref_items:
                ref_html = f'''
                <div class="reference-box">
                  <h4>📚 权威参考来源 <small class="en-sub">Authoritative References</small></h4>
                  <ul>{''.join(ref_items)}</ul>
                </div>'''

    return f'''
    <section class="panel core-panel" id="attribution">
      <div class="panel-header">
        <span class="panel-icon">🧩</span>
        <div><h2>{_bilingual("二、错题归因报告", "Error Attribution Report")}</h2>
        <p class="panel-sub">基于错误定位，输出错因分析，关联权威国际中文教学资料中的汉语知识点 / Analyze error causes and link to Chinese grammar knowledge points</p></div>
      </div>
      <div class="attr-list">{''.join(cards)}</div>
      {ref_html}
    </section>'''


def _build_evaluation_panel(evaluation, issues):
    score = evaluation.get("overall_score", "--")
    target_level = evaluation.get("target_level", "HSK3")
    logic_eval = evaluation.get("logic_evaluation", "")
    dimensions = evaluation.get("evaluation_dimensions", {})
    suggestions = evaluation.get("global_suggestions", [])

    dim_bars = []
    for key, label_zh in DIMENSION_LABELS.items():
        dim = dimensions.get(key, {})
        dim_score = dim.get("score", 0)
        dim_note = dim.get("note", "")
        label_en = DIMENSION_LABELS_EN.get(key, key)
        bar_color = "#27ae60" if dim_score >= 80 else ("#f39c12" if dim_score >= 65 else "#e74c3c")
        dim_bars.append(f'''
        <div class="dim-row">
          <div class="dim-label">{html.escape(label_zh)}<br><small class="en-sub">{html.escape(label_en)}</small></div>
          <div class="dim-bar-wrap"><div class="dim-bar" style="width:{dim_score}%;background:{bar_color}"></div></div>
          <div class="dim-score">{dim_score}</div>
          <div class="dim-note">{html.escape(dim_note)}</div>
        </div>''')

    real_issues = [i for i in issues if i.get("type") != "无明显错误"]
    issue_types = list(dict.fromkeys(i.get("type", "") for i in real_issues))
    strengths = ["表达意愿明确，有完整的篇章意识"]
    if not real_issues or len(real_issues) <= 1:
        strengths.append("语言准确性较好，语法错误较少")
    if score >= 70:
        strengths.append("整体表达基本通顺，能够传达核心意思")
    main_problems = []
    if issue_types:
        main_problems.append("存在" + "、".join(issue_types[:3]) + "等问题")
    if logic_eval and "需" in logic_eval:
        main_problems.append("篇章衔接和逻辑组织仍需加强")
    if not main_problems:
        main_problems.append("无明显系统性问题，可进一步提升表达丰富度")

    strength_items = "".join(f"<li>{html.escape(s)}</li>" for s in strengths)
    problem_items = "".join(f"<li>{html.escape(p)}</li>" for p in main_problems)
    suggestion_items = "".join(f"<li>{html.escape(s)}</li>" for s in suggestions)

    return f'''
    <section class="panel core-panel" id="evaluation">
      <div class="panel-header">
        <span class="panel-icon">📊</span>
        <div><h2>{_bilingual("三、全文评价", "Overall Evaluation")}</h2>
        <p class="panel-sub">提供整体评分、篇章逻辑评价及全局性写作提升建议 / Overall score, discourse logic evaluation and global writing improvement suggestions</p></div>
      </div>
      <div class="eval-overview">
        <div class="eval-score-box">
          <div class="eval-score">{score}</div>
          <div class="eval-score-label">总体评分 / Overall Score</div>
          <div class="eval-level">目标等级 / Target: {html.escape(str(target_level))}</div>
        </div>
        <div class="eval-logic">
          <h4>篇章逻辑评价 <small class="en-sub">Discourse Logic Evaluation</small></h4>
          <p>{html.escape(logic_eval)}</p>
        </div>
      </div>
      <div class="eval-dimensions">
        <h4>六维度评价 <small class="en-sub">Six-Dimension Evaluation</small></h4>
        {''.join(dim_bars)}
      </div>
      <div class="eval-grid">
        <div class="eval-col">
          <h4>✅ 作文优势 <small class="en-sub">Strengths</small></h4>
          <ul>{strength_items}</ul>
        </div>
        <div class="eval-col">
          <h4>⚠️ 主要问题 <small class="en-sub">Main Issues</small></h4>
          <ul>{problem_items}</ul>
        </div>
      </div>
      <div class="eval-suggestions">
        <h4>🎯 优先改进建议 <small class="en-sub">Priority Improvement Suggestions</small></h4>
        <ol>{suggestion_items}</ol>
      </div>
    </section>'''


def build_html_material(text, words, issues, evaluation, attribution_report=None, reference_sources=None):
    """构建完整的中文写作评估 HTML 报告（中英双语 + 逐字拼音标注）。"""
    used = OrderedDict()
    for item in words:
        if item.get("word") and item["word"] in text:
            used[item["word"]] = item
    used_words = list(used.values())
    grouped = {}
    for item in used_words:
        grouped.setdefault(_clean_level(item.get("level")), []).append(item)
    glossary = []
    for level in sorted(grouped, key=lambda value: (value == "?", value)):
        for item in grouped[level]:
            en_def = item.get("en_def", "") or item.get("usage_note", "") or "词语释义待补充"
            glossary.append(
                f'<div class="glossary-item">'
                f'<span class="level-dot level-{level}">HSK{level}</span>'
                f'<strong>{html.escape(item["word"])}</strong>'
                f'<span class="pinyin">{html.escape(item.get("pinyin", ""))}</span>'
                f'<span>{html.escape(en_def)}</span></div>'
            )

    title = "中文写作评估报告"
    title_en = "Chinese Writing Assessment Report"
    score = evaluation.get("overall_score", "--")
    issue_count = sum(1 for item in issues if item.get("type") != "无明显错误")
    target_level = evaluation.get("target_level", "HSK3")
    char_count = len(text.strip())

    error_panel = _build_error_panel(issues)
    attribution_panel = _build_attribution_panel(attribution_report or [], reference_sources)
    evaluation_panel = _build_evaluation_panel(evaluation, issues)

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} | {html.escape(title_en)}</title>
<style>
:root {{ --ink:#202b35; --muted:#6d7b86; --paper:#fffdf8; --line:#e7e1d8; --accent:#176b87; --warm:#ef9b57; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--ink); background:#edf3f1; font-family:"Noto Serif SC","Microsoft YaHei",Georgia,serif; line-height:1.8; }}
.en-sub {{ color:var(--muted); font-size:0.7em; font-weight:normal; font-family:Arial,sans-serif; }}
.toolbar {{ position:sticky; top:0; z-index:10; display:flex; justify-content:flex-end; gap:10px; padding:14px max(20px,calc((100% - 1080px)/2)); background:#18323a; }}
button {{ border:1px solid #8bb5b5; border-radius:8px; padding:8px 14px; color:white; background:transparent; cursor:pointer; font-size:14px; }}
button.primary {{ background:#e89a56; border-color:#e89a56; }}
.page {{ max-width:1080px; margin:0 auto; padding:0 20px 60px; }}
.hero {{ padding:42px 44px; border-radius:0 0 18px 18px; color:white; background:linear-gradient(135deg,#174c58,#287c84); box-shadow:0 18px 40px #234b4b22; margin-bottom:28px; }}
.kicker {{ letter-spacing:.16em; text-transform:uppercase; color:#b9e2d8; font-size:12px; }}
h1 {{ margin:5px 0 10px; font-size:clamp(28px,5vw,42px); line-height:1.2; }}
h1 .en-sub {{ color:#b9e2d8; font-size:0.45em; }}
.hero p {{ max-width:720px; margin:0; color:#e0f1ec; }}
.hero-stats {{ display:flex; gap:28px; margin-top:22px; flex-wrap:wrap; }}
.hero-stat {{ display:flex; flex-direction:column; }}
.hero-stat .num {{ font-size:32px; font-weight:bold; color:#ffd89b; }}
.hero-stat .label {{ font-size:13px; color:#b9e2d8; }}
.core-panel {{ margin-bottom:24px; border-left:5px solid var(--accent); }}
.panel-header {{ display:flex; align-items:center; gap:14px; margin-bottom:20px; padding-bottom:14px; border-bottom:2px solid var(--line); }}
.panel-icon {{ font-size:32px; }}
.panel-header h2 {{ margin:0; font-size:22px; color:var(--accent); line-height:1.3; }}
.panel-sub {{ margin:2px 0 0; color:var(--muted); font-size:13px; }}
.panel {{ padding:28px; background:var(--paper); border:1px solid var(--line); border-radius:14px; box-shadow:0 8px 24px #294c4610; }}
h2 {{ margin:0 0 18px; font-size:22px; }}
h3 {{ margin:0 0 8px; color:var(--accent); }}
h4 {{ margin:0 0 10px; color:var(--accent); font-size:16px; }}
.error-stats {{ display:flex; gap:16px; margin-bottom:20px; }}
.stat-item {{ flex:1; text-align:center; padding:14px; background:#f8f9fa; border-radius:10px; }}
.stat-num {{ display:block; font-size:28px; font-weight:bold; color:var(--accent); }}
.stat-label {{ font-size:13px; color:var(--muted); }}
.stat-label small {{ display:block; font-size:11px; }}
.conf-high-text {{ color:#c0392b; }}
.conf-mid-text {{ color:#e67e22; }}
.error-list {{ display:grid; gap:14px; }}
.error-card {{ border:1px solid var(--line); border-left:4px solid var(--error-color); border-radius:10px; overflow:hidden; background:#fff; }}
.error-card-head {{ display:flex; align-items:center; gap:10px; padding:10px 16px; background:#fafafa; border-bottom:1px solid var(--line); flex-wrap:wrap; }}
.error-num {{ display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; background:var(--error-color); color:white; font-size:13px; font-weight:bold; }}
.error-type-tag {{ padding:2px 10px; border-radius:12px; background:var(--error-color); color:white; font-size:12px; }}
.error-type-tag small {{ display:block; font-size:10px; opacity:0.9; }}
.confidence-badge {{ padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold; }}
.conf-high {{ background:#fde8e8; color:#c0392b; }}
.conf-mid {{ background:#fef3e2; color:#e67e22; }}
.error-location {{ margin-left:auto; color:var(--muted); font-size:13px; }}
.error-card-body {{ padding:14px 16px; }}
.error-row {{ display:flex; gap:12px; margin-bottom:8px; align-items:flex-start; }}
.error-row:last-child {{ margin-bottom:0; }}
.row-label {{ flex-shrink:0; width:90px; color:var(--muted); font-size:13px; font-weight:bold; }}
.row-label small {{ display:block; font-weight:normal; font-size:11px; }}
.error-fragment {{ background:#fff3cd; padding:2px 6px; border-radius:4px; font-weight:bold; }}
.suggestion-row .row-label {{ color:#27ae60; }}
.suggestion-text {{ color:#1e8449; }}
.attr-list {{ display:grid; gap:14px; }}
.attr-card {{ border:1px solid var(--line); border-left:4px solid var(--attr-color); border-radius:10px; overflow:hidden; background:#fff; }}
.attr-card-head {{ display:flex; align-items:center; gap:10px; padding:10px 16px; background:#fafafa; border-bottom:1px solid var(--line); }}
.attr-num {{ display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; background:var(--attr-color); color:white; font-size:13px; font-weight:bold; }}
.attr-type {{ font-weight:bold; color:var(--attr-color); }}
.attr-type small {{ display:block; font-weight:normal; font-size:11px; color:var(--muted); }}
.attr-location {{ margin-left:auto; color:var(--muted); font-size:13px; }}
.attr-card-body {{ padding:14px 16px; }}
.attr-row {{ display:flex; gap:12px; margin-bottom:10px; align-items:flex-start; }}
.attr-row:last-child {{ margin-bottom:0; }}
.attr-text {{ color:#555; }}
.tag-group {{ display:flex; flex-wrap:wrap; gap:6px; }}
.kp-tag {{ padding:2px 10px; border-radius:12px; background:#e8f4fd; color:#2980b9; font-size:12px; }}
.rw-tag {{ padding:2px 8px; border-radius:4px; background:#f0e3ff; color:#8e44ad; font-size:12px; }}
.tag-empty {{ color:var(--muted); font-size:13px; }}
.reference-box {{ margin-top:20px; padding:16px; background:#f0f7f4; border-radius:10px; border-left:4px solid #27ae60; }}
.reference-box h4 {{ color:#1e8449; }}
.reference-box ul {{ margin:8px 0 0; padding-left:20px; }}
.reference-box li {{ margin-bottom:4px; font-size:14px; }}
.reference-box a {{ color:#2980b9; }}
.eval-overview {{ display:grid; grid-template-columns:200px 1fr; gap:24px; margin-bottom:24px; }}
.eval-score-box {{ text-align:center; padding:24px; background:linear-gradient(135deg,#174c58,#287c84); border-radius:14px; color:white; }}
.eval-score {{ font-size:56px; font-weight:bold; line-height:1; color:#ffd89b; }}
.eval-score-label {{ font-size:13px; color:#b9e2d8; margin-top:4px; }}
.eval-level {{ font-size:14px; margin-top:10px; color:#e0f1ec; }}
.eval-logic {{ padding:18px; background:#f8f9fa; border-radius:10px; }}
.eval-logic p {{ margin:0; color:#555; }}
.eval-dimensions {{ margin-bottom:24px; }}
.dim-row {{ display:grid; grid-template-columns:160px 1fr 40px; gap:10px; align-items:center; margin-bottom:10px; }}
.dim-label {{ font-size:14px; color:var(--ink); }}
.dim-label small {{ display:block; font-size:11px; color:var(--muted); }}
.dim-bar-wrap {{ height:20px; background:#e9ecef; border-radius:10px; overflow:hidden; }}
.dim-bar {{ height:100%; border-radius:10px; transition:width .3s; }}
.dim-score {{ text-align:right; font-weight:bold; font-size:14px; }}
.dim-note {{ grid-column:1 / -1; font-size:12px; color:var(--muted); margin-top:-4px; padding-left:170px; }}
.eval-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:24px; }}
.eval-col {{ padding:16px; background:#f8f9fa; border-radius:10px; }}
.eval-col ul {{ margin:0; padding-left:18px; }}
.eval-col li {{ margin-bottom:4px; font-size:14px; }}
.eval-suggestions {{ padding:18px; background:#fff8e1; border-radius:10px; border-left:4px solid #f39c12; }}
.eval-suggestions h4 {{ color:#d68910; }}
.eval-suggestions ol {{ margin:8px 0 0; padding-left:20px; }}
.eval-suggestions li {{ margin-bottom:6px; }}
.original {{ padding:25px; min-height:180px; font-size:22px; line-height:2.35; background:#fff; border-left:5px solid var(--warm); border-radius:4px 12px 12px 4px; }}
/* 逐字拼音标注：word-group 包裹，word-char 单字 */
.word-group {{ display:inline-flex; padding:0 3px; margin:0 1px; border-radius:4px; background:var(--level-color); cursor:help; vertical-align:baseline; }}
ruby.word-char {{ display:inline-block; margin:0; padding:0; background:transparent; }}
ruby.word-char rt {{ color:#55717a; font-family:Arial,sans-serif; font-size:10px; line-height:1; }}
/* 整体标注（单字词或音节数不一致） */
ruby.word {{ display:inline-block; padding:0 3px; margin:0 1px; border-radius:4px; background:var(--level-color); cursor:help; }}
ruby rt {{ color:#55717a; font-family:Arial,sans-serif; font-size:10px; line-height:1; }}
.legend {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }}
.level-dot {{ display:inline-block; padding:1px 7px; border-radius:12px; font:12px Arial,sans-serif; background:var(--level-color); }}
.glossary {{ display:grid; gap:10px; }}
.glossary-item {{ display:grid; grid-template-columns:52px 80px 110px 1fr; gap:8px; align-items:center; padding:8px 0; border-bottom:1px dashed var(--line); }}
.pinyin {{ color:var(--muted); font:13px Arial,sans-serif; }}
.sentence-list {{ display:grid; gap:12px; }}
.sentence-card {{ padding:15px 18px; border-radius:10px; background:#f4f8f5; border-left:4px solid #74a99a; }}
.sentence-card.attention {{ background:#fff6ed; border-left-color:#e89a56; }}
.sentence-head {{ display:flex; justify-content:space-between; color:var(--muted); font:13px Arial,sans-serif; }}
.sentence-head b {{ color:#b5672f; }}
.sentence-card p {{ margin:4px 0; font-size:17px; }}
.sentence-card small {{ color:var(--muted); }}
.empty-state {{ text-align:center; padding:40px 20px; }}
.empty-icon {{ display:inline-flex; align-items:center; justify-content:center; width:60px; height:60px; border-radius:50%; background:#d4edda; color:#27ae60; font-size:28px; margin-bottom:12px; }}
.empty-state h3 {{ margin:0 0 8px; color:#27ae60; }}
.empty-state p {{ margin:0; color:var(--muted); }}
.toc {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:24px; padding:14px 18px; background:#fff; border-radius:10px; border:1px solid var(--line); }}
.toc a {{ padding:6px 14px; border-radius:6px; background:#f0f4f5; color:var(--accent); text-decoration:none; font-size:14px; }}
.toc a:hover {{ background:var(--accent); color:white; }}
ul, ol {{ padding-left:22px; }}
footer {{ margin-top:28px; color:var(--muted); font-size:13px; text-align:center; }}
@media(max-width:760px) {{
  .grid {{ grid-template-columns:1fr; }}
  .hero {{ padding:30px 24px; }}
  .panel {{ padding:21px; }}
  .original {{ font-size:19px; }}
  .glossary-item {{ grid-template-columns:48px 60px 80px 1fr; font-size:13px; }}
  .eval-overview {{ grid-template-columns:1fr; }}
  .eval-grid {{ grid-template-columns:1fr; }}
  .dim-row {{ grid-template-columns:120px 1fr 36px; }}
  .dim-note {{ padding-left:0; }}
  .error-stats {{ flex-direction:column; }}
  .row-label {{ width:70px; }}
}}
@media print {{
  .toolbar {{ display:none; }}
  .toc {{ display:none; }}
  body {{ background:white; }}
  .page {{ margin:0; }}
  .core-panel {{ break-inside:avoid; }}
}}
</style>
</head>
<body>
<div class="toolbar">
  <button onclick="window.print()">🖨️ 打印 / Print</button>
  <button class="primary" onclick="downloadHtml()">⬇️ 下载 HTML / Download</button>
</div>
<main class="page">
<header class="hero">
  <div class="kicker">Chinese Writing Assessment · 中文写作评估</div>
  <h1>{html.escape(title)} <span class="en-sub">{html.escape(title_en)}</span></h1>
  <p>基于国际中文教学标准与 HSK 词汇体系，对作文进行语法/语义错误定位、错题归因分析和全文能力评价。<br>
  <span class="en-sub">Grammar/semantic error detection, error attribution, and overall writing evaluation based on International Chinese Teaching Standards and HSK vocabulary.</span></p>
  <div class="hero-stats">
    <div class="hero-stat"><span class="num">{score}</span><span class="label">总体评分 / Score</span></div>
    <div class="hero-stat"><span class="num">{issue_count}</span><span class="label">检测问题 / Issues</span></div>
    <div class="hero-stat"><span class="num">{char_count}</span><span class="label">作文字数 / Words</span></div>
    <div class="hero-stat"><span class="num">{html.escape(str(target_level))}</span><span class="label">目标等级 / Level</span></div>
  </div>
</header>

<nav class="toc">
  <a href="#error-location">🔍 错误定位 / Errors</a>
  <a href="#attribution">🧩 错题归因 / Attribution</a>
  <a href="#evaluation">📊 全文评价 / Evaluation</a>
  <a href="#reading">📖 原文精读 / Reading</a>
  <a href="#vocab">📚 词语卡片 / Vocabulary</a>
  <a href="#sentences">✏️ 长难句 / Sentences</a>
</nav>

{error_panel}
{attribution_panel}
{evaluation_panel}

<section class="panel" id="reading" style="margin-top:24px">
  <h2>📖 原文精读 <span class="en-sub">Close Reading with Pinyin</span></h2>
  <div class="original">{_annotated_text(text, words)}</div>
  <div class="legend">{''.join(f'<span class="level-dot level-{level}" style="--level-color:{LEVEL_COLORS.get(level, "#f0f0f0")}">HSK{level}</span>' for level in sorted(grouped))}</div>
</section>

<section class="panel" id="vocab" style="margin-top:24px">
  <h2>📚 词语卡片 <span class="en-sub">Vocabulary Cards</span></h2>
  <div class="glossary">{''.join(glossary) or '<p>本文暂未匹配到词库词语。<br><span class="en-sub">No HSK vocabulary matched.</span></p>'}</div>
</section>

<section class="panel" id="sentences" style="margin-top:24px">
  <h2>✏️ 长难句与篇章观察 <span class="en-sub">Sentence & Discourse Analysis</span></h2>
  <div class="sentence-list">{_sentence_cards(text, issues)}</div>
</section>

<footer>本报告由中文写作评估技能生成，基于 HSK 1-6 词库与国际中文教学标准，可在浏览器中直接打印、保存或下载。<br>
<span class="en-sub">Generated by Chinese Writing Assessment Skill. Based on HSK 1-6 vocabulary and International Chinese Teaching Standards.</span></footer>
</main>
<script>
function downloadHtml() {{
  const blob = new Blob([document.documentElement.outerHTML], {{type:'text/html;charset=utf-8'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '中文写作评估报告_Chinese_Writing_Assessment.html';
  a.click();
  URL.revokeObjectURL(a.href);
}}
</script>
</body></html>'''
