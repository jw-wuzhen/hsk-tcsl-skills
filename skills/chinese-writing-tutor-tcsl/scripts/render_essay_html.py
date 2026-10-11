#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a beautifully styled HTML display for a recommended essay.

Every word in the essay body shows:
- Pinyin annotation above
- HSK level color coding (colored underline + dot)
- English definition visible below the word
- Good expressions highlighted with star marker

The "Useful Expressions" section at the bottom remains as detailed cards.
"""
import json
import sys
import os
import html as html_module
import argparse

HSK_COLORS = {
    1: "#e74c3c",
    2: "#e67e22",
    3: "#f39c12",
    4: "#27ae60",
    5: "#2980b9",
    6: "#8e44ad",
}

HSK_LIGHT_BG = {
    1: "#fef5f5",
    2: "#fef9f3",
    3: "#fefcf5",
    4: "#f3faf5",
    5: "#f3f8fd",
    6: "#f8f5fd",
}

HSK_LABELS = {
    1: "HSK 1",
    2: "HSK 2",
    3: "HSK 3",
    4: "HSK 4",
    5: "HSK 5",
    6: "HSK 6",
}


def esc(text):
    return html_module.escape(str(text), quote=False)


def is_punctuation(text):
    """Check if the text is punctuation or whitespace."""
    return all(c in '，。！？、；：""''「」（）()【】《》〈〉…—·,.!?;:"\' \t\n\r…' or ord(c) < 128 for c in text)


def render_word(word):
    text = esc(word.get("text", ""))
    pinyin = esc(word.get("pinyin", ""))
    hsk = word.get("hsk", 0)
    en_def = esc(word.get("en_def", ""))
    highlight = word.get("highlight", False)

    if not text.strip():
        return text

    # Punctuation: just render as-is, no annotation
    if is_punctuation(text):
        return f'<span class="punct">{text}</span>'

    color = HSK_COLORS.get(hsk, "#aaa")
    light_bg = HSK_LIGHT_BG.get(hsk, "transparent")
    label = HSK_LABELS.get(hsk, "")

    highlight_cls = " hl" if highlight else ""
    hsk_cls = f" hsk{hsk}" if hsk > 0 else " nohsk"

    parts = []
    parts.append(f'<span class="w{hsk_cls}{highlight_cls}" style="--c:{color};--bg:{light_bg};">')

    # Pinyin on top
    if pinyin:
        parts.append(f'<span class="py">{pinyin}</span>')
    else:
        parts.append('<span class="py"></span>')

    # Chinese text
    parts.append(f'<span class="cz">{text}</span>')

    # English definition below
    if en_def:
        parts.append(f'<span class="en">{en_def}</span>')
    else:
        parts.append('<span class="en"></span>')

    # HSK dot
    if hsk > 0:
        parts.append(f'<span class="dot" title="{label}"></span>')

    if highlight:
        parts.append('<span class="star">★</span>')

    parts.append('</span>')
    return "".join(parts)


def render_paragraph(para_words):
    parts = [render_word(w) for w in para_words]
    return '<p class="para">' + "".join(parts) + '</p>'


def render_good_expression(idx, expr):
    expression = esc(expr.get("expression", ""))
    pinyin = esc(expr.get("pinyin", ""))
    hsk = expr.get("hsk", 0)
    en_def = esc(expr.get("en_def", ""))
    explanation = esc(expr.get("explanation", ""))
    example = esc(expr.get("example", ""))
    color = HSK_COLORS.get(hsk, "#555")
    label = HSK_LABELS.get(hsk, "")
    bg = HSK_LIGHT_BG.get(hsk, "#f9f9f9")

    return f'''
    <div class="ecard" style="--c:{color};--bg:{bg};">
      <div class="ecard-head">
        <span class="ecard-text">{expression}</span>
        <span class="ecard-py">{pinyin}</span>
        <span class="ecard-hsk" style="background:{color};">{label}</span>
      </div>
      <div class="ecard-en">{en_def}</div>
      <div class="ecard-exp">{explanation}</div>
      <div class="ecard-ex"><span class="ecard-ex-label">Example:</span> {example}</div>
    </div>'''


def generate_html(data):
    title = esc(data.get("title", ""))
    hsk_level = data.get("hsk_level", "")
    source_url = esc(data.get("source_url", ""))
    word_count = data.get("word_count", 0)
    paragraphs = data.get("paragraphs", [])
    good_expressions = data.get("good_expressions", [])

    level_label = HSK_LABELS.get(int(hsk_level), f"HSK {hsk_level}")
    level_color = HSK_COLORS.get(int(hsk_level), "#333")

    essay_html = "\n".join(render_paragraph(p) for p in paragraphs)
    expr_html = "\n".join(render_good_expression(i, e) for i, e in enumerate(good_expressions))

    legend_items = "".join(
        f'<span class="lg-item"><span class="lg-dot" style="background:{color};"></span>{HSK_LABELS[level]}</span>'
        for level, color in HSK_COLORS.items()
    )

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - Essay Display</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif;
    background: linear-gradient(160deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #2c3e50;
    padding: 0;
  }}

  .container {{
    max-width: 920px;
    margin: 0 auto;
    padding: 36px 20px 60px;
  }}

  /* === Header === */
  .header {{
    text-align: center;
    margin-bottom: 28px;
    padding: 36px 28px;
    background: white;
    border-radius: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12);
  }}
  .header h1 {{
    font-size: 30px;
    font-weight: 800;
    color: #1a1a2e;
    margin-bottom: 14px;
    letter-spacing: 3px;
  }}
  .meta {{
    display: flex;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 18px;
    border-radius: 24px;
    font-size: 14px;
    font-weight: 600;
  }}
  .badge-level {{
    background: {level_color};
    color: white;
  }}
  .badge-count {{
    background: #f0f2f5;
    color: #555;
  }}
  .badge-source {{
    background: #f0f2f5;
    color: #555;
  }}
  .badge-source a {{ color: inherit; text-decoration: none; }}
  .badge-source a:hover {{ text-decoration: underline; }}

  /* === Legend === */
  .legend {{
    display: flex;
    justify-content: center;
    gap: 14px;
    flex-wrap: wrap;
    margin-bottom: 24px;
    padding: 14px 24px;
    background: rgba(255,255,255,0.95);
    border-radius: 14px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  }}
  .lg-item {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 500;
    color: #444;
  }}
  .lg-dot {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
  }}

  /* === Essay Body === */
  .essay {{
    background: white;
    border-radius: 20px;
    padding: 48px 40px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12);
    margin-bottom: 32px;
  }}
  .para {{
    margin-bottom: 22px;
    text-align: justify;
    line-height: 1.5;
  }}

  /* === Word Annotation (key feature) === */
  .w {{
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    vertical-align: top;
    margin: 0 1px 8px;
    padding: 4px 5px 3px;
    border-radius: 7px;
    position: relative;
    transition: all 0.2s ease;
    border-bottom: 3px solid var(--c, transparent);
    background: var(--bg, transparent);
  }}
  .w:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    z-index: 10;
  }}

  /* Pinyin */
  .py {{
    font-size: 11px;
    font-weight: 500;
    color: var(--c, #999);
    font-family: "Georgia", "Times New Roman", serif;
    line-height: 1.1;
    margin-bottom: 2px;
    min-height: 13px;
    text-align: center;
  }}

  /* Chinese characters */
  .cz {{
    font-size: 20px;
    font-weight: 600;
    color: #1a1a2e;
    line-height: 1.3;
    text-align: center;
  }}

  /* English definition */
  .en {{
    font-size: 10px;
    font-weight: 400;
    color: #888;
    font-style: italic;
    line-height: 1.1;
    margin-top: 2px;
    min-height: 12px;
    text-align: center;
    max-width: 80px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}

  /* HSK dot */
  .dot {{
    position: absolute;
    top: 3px;
    right: 3px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--c, #ccc);
    opacity: 0.6;
  }}

  /* No HSK word: subtle styling */
  .w.nohsk {{
    border-bottom-color: transparent;
    background: transparent;
  }}
  .w.nohsk .py {{
    color: #bbb;
  }}
  .w.nohsk .en {{
    color: #ccc;
  }}

  /* Highlighted (good expression) */
  .w.hl {{
    background: linear-gradient(135deg, #fff8e1, #fff3c4);
    border-bottom-color: #ffc107;
    border-bottom-width: 4px;
    box-shadow: 0 2px 8px rgba(255,193,7,0.2);
  }}
  .w.hl .cz {{
    color: #e65100;
  }}
  .star {{
    position: absolute;
    top: -8px;
    right: -4px;
    font-size: 13px;
    color: #ff9800;
    text-shadow: 0 1px 2px rgba(255,152,0,0.3);
  }}

  /* Punctuation */
  .punct {{
    font-size: 20px;
    color: #555;
    font-weight: 600;
    vertical-align: top;
    display: inline-block;
    margin: 0 1px;
    padding-top: 18px;
  }}

  /* === Useful Expressions Section === */
  .expr-sec {{
    background: white;
    border-radius: 20px;
    padding: 40px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12);
  }}
  .expr-title {{
    font-size: 24px;
    font-weight: 800;
    color: #1a1a2e;
    margin-bottom: 24px;
    padding-bottom: 14px;
    border-bottom: 3px solid #f0f2f5;
  }}
  .ecard {{
    border-left: 5px solid var(--c, #ccc);
    background: var(--bg, #f9f9f9);
    border-radius: 10px;
    padding: 22px 26px;
    margin-bottom: 16px;
    transition: transform 0.2s, box-shadow 0.2s;
  }}
  .ecard:hover {{
    transform: translateX(6px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  }}
  .ecard-head {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }}
  .ecard-text {{
    font-size: 22px;
    font-weight: 800;
    color: #1a1a2e;
  }}
  .ecard-py {{
    font-size: 15px;
    color: #888;
    font-family: "Georgia", serif;
  }}
  .ecard-hsk {{
    font-size: 12px;
    color: white;
    padding: 3px 12px;
    border-radius: 12px;
    font-weight: 700;
  }}
  .ecard-en {{
    font-size: 15px;
    color: #555;
    font-style: italic;
    margin-bottom: 10px;
  }}
  .ecard-exp {{
    font-size: 14px;
    color: #333;
    line-height: 1.8;
    margin-bottom: 10px;
  }}
  .ecard-ex {{
    font-size: 14px;
    color: #555;
    background: rgba(0,0,0,0.04);
    padding: 10px 14px;
    border-radius: 8px;
    line-height: 1.7;
  }}
  .ecard-ex-label {{
    font-weight: 700;
    color: #7f8c8d;
  }}

  /* === Footer === */
  .footer {{
    text-align: center;
    padding: 24px;
    font-size: 14px;
    color: rgba(255,255,255,0.7);
  }}
  .footer a {{
    color: rgba(255,255,255,0.9);
    text-decoration: none;
  }}
  .footer a:hover {{
    text-decoration: underline;
  }}

  /* === Responsive === */
  @media (max-width: 600px) {{
    .container {{ padding: 16px 10px 40px; }}
    .header {{ padding: 24px 16px; border-radius: 16px; }}
    .header h1 {{ font-size: 24px; }}
    .essay {{ padding: 24px 14px; border-radius: 16px; }}
    .w {{ padding: 3px 3px 2px; margin: 0 0px 6px; }}
    .py {{ font-size: 9px; min-height: 11px; }}
    .cz {{ font-size: 17px; }}
    .en {{ font-size: 9px; max-width: 60px; }}
    .punct {{ font-size: 17px; padding-top: 15px; }}
    .expr-sec {{ padding: 24px 16px; border-radius: 16px; }}
    .ecard {{ padding: 16px 18px; }}
    .ecard-text {{ font-size: 18px; }}
  }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>{title}</h1>
    <div class="meta">
      <span class="badge badge-level">{level_label}</span>
      <span class="badge badge-count">约 {word_count} 字</span>
      <span class="badge badge-source"><a href="{source_url}" target="_blank">📍 zuowen.com</a></span>
    </div>
  </div>

  <div class="legend">
    {legend_items}
    <span class="lg-item"><span class="lg-dot" style="background:#ffc107;"></span>★ Good Expression</span>
  </div>

  <div class="essay">
    {essay_html}
  </div>

  <div class="expr-sec">
    <div class="expr-title">★ Useful Expressions &amp; Key Sentences</div>
    {expr_html}
  </div>

  <div class="footer">
    Generated by Chinese Writing Tutor · Source: <a href="{source_url}" target="_blank">zuowen.com</a>
  </div>

</div>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate HTML display for essay")
    parser.add_argument("json_file", help="Path to JSON file with essay data")
    parser.add_argument("--output", default="/mnt/user-data/outputs/essay_display.html",
                        help="Output HTML file path")
    args = parser.parse_args()

    with open(args.json_file, encoding="utf-8") as f:
        data = json.load(f)

    html_content = generate_html(data)

    output_path = args.output
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    # Write with UTF-8 BOM to ensure correct encoding detection
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write(html_content)

    print(f"HTML_SAVED:{output_path}")


if __name__ == "__main__":
    main()
