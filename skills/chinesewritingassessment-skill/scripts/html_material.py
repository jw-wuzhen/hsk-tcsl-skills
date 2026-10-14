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

# 论文四维度评分量表标签（史剑雄、王佶旻 2022）
DIMENSION_LABELS = {
    "language_accuracy": "语言准确性",
    "language_richness": "语言丰富性",
    "discourse_rationality": "篇章合理性",
    "writing_normalization": "写作规范性",
}
DIMENSION_LABELS_EN = {
    "language_accuracy": "Linguistic Accuracy",
    "language_richness": "Linguistic Richness",
    "discourse_rationality": "Discourse Rationality",
    "writing_normalization": "Writing Normalization",
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


def _char_cell(char, pinyin, title, level, color):
    """生成田字格单字单元：拼音固定在字上方，汉字居中在田字格内，逐字严格对齐。"""
    py_html = f'<span class="py">{html.escape(pinyin)}</span>' if pinyin else '<span class="py">&nbsp;</span>'
    return (
        f'<span class="char-cell level-{level}" style="--level-color:{color}" '
        f'title="{html.escape(title, quote=True)}">{py_html}'
        f'<span class="box"><span class="char">{html.escape(char)}</span></span></span>'
    )


def _is_punct(char):
    """标点/空白字符不套田字格，保持自然排版。"""
    return bool(re.match(r"[\u3000-\u303f\uff00-\uffef\s，。！？；：、""''（）【】《》〈〉…—·～]", char))


def _annotated_text(text, words):
    """逐字标注拼音：每个汉字放入田字格单元，拼音固定在格子上方，全文对齐成网格。"""
    word_map = {w["word"]: w for w in words}
    parts = []
    for token_type, value in _tokenize(text, words):
        if token_type == "char":
            if _is_punct(value):
                parts.append(f'<span class="punct">{html.escape(value)}</span>')
            else:
                parts.append(f'<span class="char-cell"><span class="box"><span class="char">{html.escape(value)}</span></span></span>')
            continue
        item = word_map[value]
        level = _clean_level(item.get("level"))
        color = LEVEL_COLORS.get(level, "#f0f0f0")
        pinyin = item.get("pinyin", "") or ""
        en_def = item.get("en_def", "") or item.get("usage_note", "") or ""
        title = f"HSK{level} | {en_def}"
        pinyin_parts = pinyin.split() if pinyin else []
        if len(pinyin_parts) == len(value) and len(value) > 1:
            # 多字词：逐字拼音一一对应
            for i, char in enumerate(value):
                parts.append(_char_cell(char, pinyin_parts[i], title, level, color))
        else:
            # 单字词或音节数不一致：整串拼音标在首字上方，其余字无拼音
            for i, char in enumerate(value):
                py = pinyin_parts[i] if i < len(pinyin_parts) else ""
                parts.append(_char_cell(char, py if i == 0 else (pinyin_parts[i] if i < len(pinyin_parts) else ""), title, level, color))
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
    """生成中英双语标题：英文默认半隐藏，点击 EN 徽章展开。"""
    return f'{zh} <button class="en-toggle" type="button" aria-label="Show English">EN</button> <span class="en-sub" hidden>{en}</span>'


def _bilingual_sub(zh, en):
    """面板副标题：中文 + 半隐藏英文。"""
    return f'{zh} <button class="en-toggle" type="button">EN</button> <span class="en-sub" hidden>{en}</span>'


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
            <p class="panel-sub">{_bilingual_sub("识别作文中的语病、搭配错误、用词错误、逻辑问题", "Identify grammar, collocation, word choice and logic issues")}</p></div>
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
        <p class="panel-sub">{_bilingual_sub("识别作文中的语病、搭配错误、用词错误、逻辑问题", "Identify grammar, collocation, word choice and logic issues")}</p></div>
      </div>
      <div class="error-stats">
        <div class="stat-item"><span class="stat-num">{len(real_issues)}</span><span class="stat-label">问题总数<br><small>Total</small></span></div>
        <div class="stat-item"><span class="stat-num conf-high-text">{confirmed}</span><span class="stat-label">确定错误<br><small>Confirmed</small></span></div>
        <div class="stat-item"><span class="stat-num conf-mid-text">{possible}</span><span class="stat-label">可能问题<br><small>Possible</small></span></div>
      </div>
      <div class="error-list">{''.join(cards)}</div>
    </section>'''


def _build_attribution_panel(attribution_report):
    if not attribution_report:
        return ''
    real_attrs = [a for a in attribution_report if a.get("type") != "无明显错误"]
    if not real_attrs:
        return f'''
        <section class="panel core-panel" id="attribution">
          <div class="panel-header">
            <span class="panel-icon">🧩</span>
            <div><h2>{_bilingual("二、错题归因报告", "Error Attribution Report")}</h2>
            <p class="panel-sub">{_bilingual_sub("基于错误定位，输出错因分析，关联权威国际中文教学资料中的汉语知识点", "Analyze error causes and link to Chinese grammar knowledge points")}</p></div>
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
              <div class="attr-cause">
                <span class="attr-text">{html.escape(attr.get("attribution", ""))}</span>
                {f'<button class="en-toggle" type="button">EN 解释</button><span class="en-sub attr-en" hidden>{html.escape(attr.get("attribution_en", ""))}</span>' if attr.get("attribution_en") else ''}
              </div>
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
    return f'''
    <section class="panel core-panel" id="attribution">
      <div class="panel-header">
        <span class="panel-icon">🧩</span>
        <div><h2>{_bilingual("二、错题归因报告", "Error Attribution Report")}</h2>
        <p class="panel-sub">{_bilingual_sub("基于错误定位，输出错因分析，关联权威国际中文教学资料中的汉语知识点", "Analyze error causes and link to Chinese grammar knowledge points")}</p></div>
      </div>
      <div class="attr-list">{''.join(cards)}</div>
    </section>'''


def _build_reference_panel(reference_sources):
    """权威参考来源面板：独立成段，置于报告最底部。"""
    if not reference_sources:
        return ''
    if isinstance(reference_sources, dict):
        sources = reference_sources.get("sources", []) or reference_sources.get("references", [])
    elif isinstance(reference_sources, list):
        sources = reference_sources
    else:
        sources = []
    if not sources:
        return ''
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
    if not ref_items:
        return ''
    return f'''
    <section class="panel" id="references" style="margin-top:24px">
      <h2>📚 权威参考来源 <span class="en-sub">Authoritative References</span></h2>
      <p class="panel-sub">{_bilingual_sub("评分量表与教学依据来自以下权威研究与国际中文教学标准", "Assessment scales and teaching standards are based on the following authoritative references")}</p>
      <ul class="reference-list">{''.join(ref_items)}</ul>
    </section>'''


def _build_evaluation_panel(evaluation, issues):
    score = evaluation.get("overall_score", "--")
    target_level = evaluation.get("target_level", "HSK3")
    logic_eval = evaluation.get("logic_evaluation", "")
    dimensions = evaluation.get("evaluation_dimensions", {})
    suggestions = evaluation.get("global_suggestions", [])

    DIMENSION_ICONS = {"language_accuracy": "🎯", "language_richness": "💬", "discourse_rationality": "📐", "writing_normalization": "✍️"}
    dim_bars = []
    for key, label_zh in DIMENSION_LABELS.items():
        dim = dimensions.get(key, {})
        dim_score = dim.get("score", 0)          # 1-4 级（论文量表）
        dim_percent = dim.get("percent", 0)      # 百分制换算
        if not dim_percent:
            dim_percent = round(dim_score / 4 * 100)
        dim_level_label = dim.get("level_label", "一般")
        dim_desc = dim.get("level_description", "")
        dim_note = dim.get("note", "")
        label_en = DIMENSION_LABELS_EN.get(key, key)
        icon = DIMENSION_ICONS.get(key, "📊")
        bar_color = "#27ae60" if dim_score >= 4 else ("#f39c12" if dim_score >= 3 else ("#e67e22" if dim_score == 2 else "#e74c3c"))
        ticks = "".join(
            f'<i class="dim-tick{" on" if dim_score >= lv else ""}" style="left:{((lv - 1) / 3) * 100:.1f}%"></i>'
            for lv in range(1, 5)
        )
        dim_bars.append(f'''
        <div class="dim-card" style="--dim-color:{bar_color}">
          <div class="dim-head">
            <span class="dim-icon">{icon}</span>
            <span class="dim-name">{html.escape(label_zh)} <small>{html.escape(label_en)}</small></span>
            <span class="dim-badge">{dim_score}/4 <small>{html.escape(dim_level_label)}</small></span>
          </div>
          <div class="dim-track">
            <span class="dim-fill" style="width:{dim_percent}%"></span>
            {ticks}
          </div>
          <div class="dim-foot">
            <span class="dim-desc">{html.escape(dim_desc)}</span>
            {f'<span class="dim-note">{html.escape(dim_note)}</span>' if dim_note else ''}
          </div>
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
        <p class="panel-sub">{_bilingual_sub("提供整体评分、篇章逻辑评价及全局性写作提升建议", "Overall score, discourse logic evaluation and global writing improvement suggestions")}</p></div>
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
        <h4>四维度评价 <small class="en-sub">Four-Dimension Evaluation (Shi &amp; Wang 2022)</small></h4>
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


def build_html_material(text, words, issues, evaluation, attribution_report=None, reference_sources=None, target_level="HSK3"):
    """构建完整的中文写作评估 HTML 报告（中英双语 + 逐字拼音标注）。

    词汇学习卡片按统一生词定义过滤：仅保留目标等级及以上的词
    （含词库未收录的超纲词），低于目标等级的词汇视为已掌握，不展示。
    """
    used = OrderedDict()
    for item in words:
        if item.get("word") and item["word"] in text:
            used[item["word"]] = item
    used_words = list(used.values())
    # 生词过滤：level >= 目标等级 或 未收录等级（超纲词）
    target_num = int(re.search(r"\d", str(target_level)).group(0)) if re.search(r"\d", str(target_level)) else 3
    new_word_items = []
    filtered_mastered = []
    for item in used_words:
        lv_match = re.search(r"[1-6]", str(item.get("level", "")))
        lv = int(lv_match.group(0)) if lv_match else None
        if lv is None or lv >= target_num:
            new_word_items.append(item)
        else:
            filtered_mastered.append(item)
    grouped = {}
    for item in new_word_items:
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
    attribution_panel = _build_attribution_panel(attribution_report or [])
    evaluation_panel = _build_evaluation_panel(evaluation, issues)
    reference_panel = _build_reference_panel(reference_sources)

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
/* 半隐藏英文：默认隐藏，点击 EN 徽章展开 */
.en-toggle {{ border:1px solid #b9c7cd; background:#f0f4f5; color:#176b87; border-radius:4px; padding:0 7px; font:11px Arial,sans-serif; cursor:pointer; vertical-align:2px; line-height:1.6; }}
.en-toggle:hover {{ background:#ddecf0; }}
.en-toggle.active {{ background:#176b87; color:white; border-color:#176b87; }}
.toolbar {{ position:sticky; top:0; z-index:10; display:flex; justify-content:flex-end; gap:10px; padding:14px max(20px,calc((100% - 1080px)/2)); background:#18323a; }}
button {{ border:1px solid #8bb5b5; border-radius:8px; padding:8px 14px; color:white; background:transparent; cursor:pointer; font-size:14px; }}
button.primary {{ background:#e89a56; border-color:#e89a56; }}
.page {{ max-width:1080px; margin:0 auto; padding:0 20px 60px; }}
.hero {{ padding:42px 44px; border-radius:0 0 18px 18px; color:white; background:linear-gradient(135deg,#174c58,#287c84); box-shadow:0 18px 40px #234b4b22; margin-bottom:28px; }}
.kicker {{ letter-spacing:.16em; text-transform:uppercase; color:#b9e2d8; font-size:12px; }}
h1 {{ margin:5px 0 10px; font-size:clamp(28px,5vw,42px); line-height:1.2; }}
h1 .en-sub {{ color:#b9e2d8; font-size:0.45em; }}
h1 .hero-toggle {{ font-size:0.3em; vertical-align:0.45em; padding:0 0.7em; background:transparent; border-color:#8bb5b5; color:#b9e2d8; }}
h1 .hero-toggle:hover {{ background:#287c84; }}
h1 .hero-toggle.active {{ background:#e89a56; border-color:#e89a56; color:#fff; }}
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
.attr-cause {{ flex:1; min-width:0; }}
.attr-cause .en-toggle {{ margin-top:4px; }}
.attr-en {{ display:block; margin-top:6px; padding:8px 10px; background:#f7fafb; border-left:3px solid #b9c7cd; border-radius:4px; font-size:13px; line-height:1.7; color:#445; }}
.tag-group {{ display:flex; flex-wrap:wrap; gap:6px; }}
.kp-tag {{ padding:2px 10px; border-radius:12px; background:#e8f4fd; color:#2980b9; font-size:12px; }}
.rw-tag {{ padding:2px 8px; border-radius:4px; background:#f0e3ff; color:#8e44ad; font-size:12px; }}
.tag-empty {{ color:var(--muted); font-size:13px; }}
.reference-list {{ margin:10px 0 0; padding-left:0; list-style:none; }}
.reference-list li {{ margin-bottom:10px; padding:12px 16px; background:#f0f7f4; border-left:4px solid #27ae60; border-radius:8px; font-size:14px; }}
.reference-list a {{ color:#2980b9; font-weight:bold; text-decoration:none; }}
.reference-list a:hover {{ text-decoration:underline; }}
.eval-overview {{ display:grid; grid-template-columns:200px 1fr; gap:24px; margin-bottom:24px; }}
.eval-score-box {{ text-align:center; padding:24px; background:linear-gradient(135deg,#174c58,#287c84); border-radius:14px; color:white; }}
.eval-score {{ font-size:56px; font-weight:bold; line-height:1; color:#ffd89b; }}
.eval-score-label {{ font-size:13px; color:#b9e2d8; margin-top:4px; }}
.eval-level {{ font-size:14px; margin-top:10px; color:#e0f1ec; }}
.eval-logic {{ padding:18px; background:#f8f9fa; border-radius:10px; }}
.eval-logic p {{ margin:0; color:#555; }}
.eval-dimensions {{ margin-bottom:24px; }}
.dim-card {{ padding:16px 18px; border-radius:12px; background:#fff; border:1px solid var(--line); box-shadow:0 3px 12px #294c4610; margin-bottom:12px; }}
.dim-head {{ display:flex; align-items:center; gap:10px; margin-bottom:12px; }}
.dim-icon {{ font-size:22px; }}
.dim-name {{ font-size:16px; font-weight:bold; color:var(--ink); line-height:1.2; }}
.dim-name small {{ display:block; font-size:11px; color:var(--muted); font-weight:normal; }}
.dim-badge {{ margin-left:auto; flex-shrink:0; padding:4px 14px; border-radius:20px; background:var(--dim-color); color:white; font-size:15px; font-weight:bold; text-align:center; line-height:1.15; }}
.dim-badge small {{ display:block; font-size:10px; font-weight:normal; opacity:0.92; }}
.dim-track {{ position:relative; height:10px; border-radius:6px; background:#eef1f3; }}
.dim-fill {{ position:absolute; left:0; top:0; bottom:0; border-radius:6px; background:linear-gradient(90deg, color-mix(in srgb, var(--dim-color) 45%, #fff), var(--dim-color)); }}
.dim-tick {{ position:absolute; top:-3px; width:16px; height:16px; border-radius:50%; background:#fff; border:2px solid #c8d0d5; transform:translateX(-50%); box-sizing:border-box; }}
.dim-tick.on {{ background:var(--dim-color); border-color:var(--dim-color); }}
.dim-foot {{ display:flex; flex-wrap:wrap; gap:4px 16px; margin-top:10px; font-size:13px; color:var(--muted); }}
.dim-desc {{ color:#444; }}
.eval-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:24px; }}
.eval-col {{ padding:16px; background:#f8f9fa; border-radius:10px; }}
.eval-col ul {{ margin:0; padding-left:18px; }}
.eval-col li {{ margin-bottom:4px; font-size:14px; }}
.eval-suggestions {{ padding:18px; background:#fff8e1; border-radius:10px; border-left:4px solid #f39c12; }}
.eval-suggestions h4 {{ color:#d68910; }}
.eval-suggestions ol {{ margin:8px 0 0; padding-left:20px; }}
.eval-suggestions li {{ margin-bottom:6px; }}
.original {{ padding:25px; min-height:180px; font-size:22px; line-height:2.4; background:#fff; border-left:5px solid var(--warm); border-radius:4px 12px 12px 4px; letter-spacing:0; }}
/* 田字格逐字对齐：拼音固定在上、汉字居中在格内，全文字格网格严格对齐 */
.char-cell {{ display:inline-flex; flex-direction:column; align-items:center; width:1.55em; margin:0 1px; vertical-align:top; }}
.char-cell .py {{ display:block; height:1.1em; line-height:1.1; font:10px/1.1 Arial,sans-serif; color:#55717a; text-align:center; white-space:nowrap; overflow:hidden; }}
.char-cell .box {{ position:relative; display:flex; align-items:center; justify-content:center; width:1.42em; height:1.42em; border:1px solid #d8d2c8; border-radius:3px; background:var(--level-color,#fff); }}
.char-cell .box::before, .char-cell .box::after {{ content:""; position:absolute; background:#e6e0d6; pointer-events:none; }}
.char-cell .box::before {{ left:0; right:0; top:50%; height:1px; }}
.char-cell .box::after {{ top:0; bottom:0; left:50%; width:1px; }}
.char-cell .box .char {{ position:relative; z-index:1; font-size:0.92em; line-height:1; }}
.original .char-cell {{ margin-top:0.35em; }}
/* 标点：置于字格中线附近，与汉字网格对齐 */
.original .punct {{ display:inline-block; vertical-align:top; margin-top:1.42em; line-height:1; color:var(--ink); }}
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
.toc {{ display:grid; grid-template-columns:repeat(6, 1fr); gap:10px; margin-bottom:24px; padding:14px 18px; background:#fff; border-radius:10px; border:1px solid var(--line); }}
.toc a {{ padding:8px 6px; border-radius:6px; background:#f0f4f5; color:var(--accent); text-decoration:none; font-size:13px; text-align:center; white-space:nowrap; }}
.toc a:hover {{ background:var(--accent); color:white; }}
ul, ol {{ padding-left:22px; }}
footer {{ margin-top:28px; color:var(--muted); font-size:13px; text-align:center; }}
@media(max-width:760px) {{
  .toc {{ grid-template-columns:repeat(2, 1fr); }}
  .hero {{ padding:30px 24px; }}
  .panel {{ padding:21px; }}
  .original {{ font-size:19px; }}
  .glossary-item {{ grid-template-columns:48px 60px 80px 1fr; font-size:13px; }}
  .eval-overview {{ grid-template-columns:1fr; }}
  .eval-grid {{ grid-template-columns:1fr; }}
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
  <h1>{html.escape(title)} <button class="en-toggle hero-toggle" type="button" aria-label="Show English title">EN</button> <span class="en-sub" hidden>{html.escape(title_en)}</span></h1>
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
  <h2>📖 {_bilingual("原文精读", "Close Reading with Pinyin")}</h2>
  <div class="original">{_annotated_text(text, words)}</div>
  <div class="legend">{''.join(f'<span class="level-dot level-{level}" style="--level-color:{LEVEL_COLORS.get(level, "#f0f0f0")}">HSK{level}</span>' for level in sorted(grouped))}</div>
</section>

<section class="panel" id="vocab" style="margin-top:24px">
  <h2>📚 {_bilingual("生词学习卡片", "New Word Cards")}</h2>
  <p class="panel-sub">{_bilingual_sub(f"生词定义：目标等级 <strong>HSK{target_num}</strong> 及以上的词汇（含词库未收录的超纲词）均为生词；已过滤低于目标等级的已掌握词汇 {len(filtered_mastered)} 个，仅展示 {len(new_word_items)} 个生词，保证复习的针对性。", f"Words at or above the target level (HSK{target_num}) are treated as new words; {len(filtered_mastered)} mastered words below the target level are filtered out.")}</p>
  <div class="glossary">{''.join(glossary) or '<p>本文暂未匹配到目标等级及以上的词库词语。<br><span class="en-sub">No new HSK vocabulary at or above the target level matched.</span></p>'}</div>
</section>

<section class="panel" id="sentences" style="margin-top:24px">
  <h2>✏️ {_bilingual("长难句与篇章观察", "Sentence & Discourse Analysis")}</h2>
  <div class="sentence-list">{_sentence_cards(text, issues)}</div>
</section>

{reference_panel}

<footer>本报告由中文写作评估技能生成：错误定位基于本地规则库与 HSK 1-6 词库；四维度评分量表依据史剑雄、王佶旻（2022）《诊断性写作测试评分量表的构建研究》（语言文字应用 2022年第3期）。可在浏览器中直接打印、保存或下载。<br>
<span class="en-sub">Generated by Chinese Writing Assessment Skill. Errors detected by local rule engine; four-dimension scale based on Shi &amp; Wang (2022), Language Application, No.3.</span></footer>
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
/* 半隐藏英文：点击 EN 徽章展开/收起 */
document.querySelectorAll('.en-toggle').forEach(function (btn) {{
  btn.addEventListener('click', function () {{
    var sub = btn.nextElementSibling;
    while (sub && !(sub.classList && sub.classList.contains('en-sub'))) {{ sub = sub.nextElementSibling; }}
    if (sub) {{
      var show = sub.hidden;
      sub.hidden = !show;
      btn.classList.toggle('active', show);
    }}
  }});
}});
</script>
</body></html>'''
