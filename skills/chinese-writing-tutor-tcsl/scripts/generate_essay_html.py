#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""All-in-one script: read essay text + good expressions, generate annotated HTML.

Usage:
    python3 generate_essay_html.py --essay-file essay.txt --expressions-json expr.json --output essay_旅行_HSK6.html --hsk-level 6

Or pipe essay text:
    echo "essay text" | python3 generate_essay_html.py --expressions-json expr.json --output out.html --hsk-level 6

The script:
1. Loads HSK vocabulary from CSV files (levels 1-6)
2. Segments essay text by scanning every HSK word: words present in the essay
   get marked with their level/pinyin, absent words are skipped
3. Annotates each word with pinyin, HSK level, English definition
4. Highlights good expressions
5. Generates a beautiful standalone HTML file (standard composition format:
   title on its own line indented 4 chars 标题空四格, each paragraph indented 2 chars)
"""
import sys
import os
import re
import json
import argparse
import html as html_module
import unicodedata


def normalize_pinyin(py):
    """Ensure tone marks are precomposed (NFC), not separate combining characters."""
    if not py:
        return ""
    return unicodedata.normalize("NFC", py)

# === HSK Vocabulary Loading ===

HSK_COLORS = {
    1: "#e74c3c", 2: "#e67e22", 3: "#f39c12",
    4: "#27ae60", 5: "#2980b9", 6: "#8e44ad",
}
HSK_LIGHT_BG = {
    1: "#fef5f5", 2: "#fef9f3", 3: "#fefcf5",
    4: "#f3faf5", 5: "#f3f8fd", 6: "#f8f5fd",
}
HSK_LABELS = {1: "HSK 1", 2: "HSK 2", 3: "HSK 3", 4: "HSK 4", 5: "HSK 5", 6: "HSK 6"}


def load_hsk_vocab(vocab_dir):
    """Load all HSK vocabulary from CSV files. Returns dict: word -> {hsk, pinyin, en_def, pos}
    Also extracts individual character pinyin from multi-char words.
    """
    vocab = {}
    char_pinyin = {}  # char -> pinyin (for fallback)

    for level in range(1, 7):
        csv_path = os.path.join(vocab_dir, f"HSK{level}.csv")
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, encoding="utf-8-sig") as f:
            lines = f.readlines()
            if len(lines) < 2:
                continue
            header = lines[0].strip().split(",")
            idx_simplified = header.index("简体") if "简体" in header else 2
            idx_pinyin = header.index("拼音") if "拼音" in header else 4
            idx_en = header.index("英文释义") if "英文释义" in header else 8
            idx_pos = header.index("词性") if "词性" in header else 6

            for line in lines[1:]:
                parts = line.strip().split(",")
                if len(parts) <= max(idx_simplified, idx_pinyin, idx_en, idx_pos):
                    continue
                word = parts[idx_simplified].strip()
                if not word:
                    continue
                pinyin_raw = parts[idx_pinyin].strip()
                pinyin_nfc = normalize_pinyin(pinyin_raw)

                if word not in vocab:
                    vocab[word] = {
                        "hsk": level,
                        "pinyin": pinyin_nfc,
                        "en_def": parts[idx_en].strip() if parts[idx_en].strip() else "",
                        "pos": parts[idx_pos].strip() if idx_pos < len(parts) else "",
                    }

                # Extract individual character pinyin from multi-char words
                syllables = pinyin_nfc.split()
                if len(syllables) == len(word) and len(word) > 1:
                    for ch, syl in zip(word, syllables):
                        if "\u4e00" <= ch <= "\u9fff" and ch not in char_pinyin:
                            char_pinyin[ch] = syl
                elif len(word) == 1 and pinyin_nfc:
                    if word not in char_pinyin:
                        char_pinyin[word] = pinyin_nfc

    # Also load char_pinyin.json if it exists (pre-generated comprehensive mapping)
    char_pinyin_path = os.path.join(vocab_dir, "..", "char_pinyin.json")
    if os.path.exists(char_pinyin_path):
        with open(char_pinyin_path, encoding="utf-8") as f:
            extra = json.load(f)
            for ch, py in extra.items():
                py_nfc = normalize_pinyin(py)
                if ch not in char_pinyin:
                    char_pinyin[ch] = py_nfc

    # Merge char_pinyin into vocab as single-char entries (don't override existing)
    for ch, py in char_pinyin.items():
        if ch not in vocab:
            vocab[ch] = {"hsk": 0, "pinyin": py, "en_def": "", "pos": ""}

    return vocab


def segment_text(text, vocab):
    """Word-list-scan segmentation for the reading view:
    scan every word in the HSK vocabulary (longest first), check whether it
    occurs in the essay; mark found words in place, skip words not present.
    Returns list of (word, is_punctuation) tuples.
    """

    # Punctuation pattern
    punct_pattern = re.compile(r'[，。！？、；：""''「」（）()【】《》〈〉…—·,.!?;:\' \t\n\r…]')

    n = len(text)
    if n == 0:
        return []

    # === Dictionary-scan segmentation ===
    # Strategy: iterate over every word in HSK vocab (longest first),
    # find all occurrences in text, mark those positions as claimed.
    # Then build segments from claimed (HSK words) + unclaimed (unknown text).

    # Step 1: Only use words with hsk > 0 for claiming positions.
    # Sort by length (longest first) so longer words get priority.
    hsk_words = [(w, info) for w, info in vocab.items() if info.get("hsk", 0) > 0]
    hsk_words.sort(key=lambda x: len(x[0]), reverse=True)

    # Step 2: For each HSK word, find all occurrences in text and claim positions
    claimed = [False] * n
    word_at = {}  # start_pos -> (word, end_pos)

    for word, info in hsk_words:
        if not word:
            continue
        start = 0
        while True:
            idx = text.find(word, start)
            if idx == -1:
                break
            end = idx + len(word)
            # Only claim if none of these positions are already claimed
            if not any(claimed[i] for i in range(idx, end)):
                for i in range(idx, end):
                    claimed[i] = True
                word_at[idx] = (word, end)
            start = idx + 1

    # Step 3: Build segments by scanning left to right
    segments = []
    i = 0
    while i < n:
        # Check punctuation first
        if punct_pattern.match(text[i]):
            j = i
            while j < n and punct_pattern.match(text[j]):
                j += 1
            segments.append((text[i:j], True))
            i = j
            continue

        # Check if this position starts a claimed HSK word
        if i in word_at:
            word, end = word_at[i]
            segments.append((word, False))
            i = end
            continue

        # Unclaimed character: collect consecutive unclaimed non-punctuation chars
        j = i + 1
        while j < n and not punct_pattern.match(text[j]) and not claimed[j]:
            j += 1

        # The unclaimed run is text[i:j]
        # Split into 2-char groups (most Chinese words are 2 chars)
        # But check if any 2-char group is actually a common word
        unknown = text[i:j]
        k = 0
        while k < len(unknown):
            if k + 2 <= len(unknown):
                pair = unknown[k:k + 2]
                segments.append((pair, False))
                k += 2
            else:
                segments.append((unknown[k:k + 1], False))
                k += 1
        i = j

    return segments


def esc(text):
    return html_module.escape(str(text), quote=False)


# POS abbreviation codes used in HSK CSVs -> full English names
POS_FULL = {
    "n": "noun", "v": "verb", "a": "adjective", "ad": "adverb", "d": "adverb",
    "r": "pronoun", "m": "measure word", "q": "measure word", "p": "preposition",
    "c": "conjunction", "u": "particle", "e": "interjection", "t": "time word",
    "s": "locality word", "b": "distinguishing word", "z": "state word",
    "h": "prefix", "k": "suffix", "j": "abbreviation", "i": "idiom",
    "l": "set phrase", "g": "morpheme", "o": "onomatopoeia", "f": "locality word",
}
# Combination codes used in HSK CSVs -> base codes
COMBO_POS = {
    "vn": ["v", "n"], "an": ["a", "n"], "vd": ["v", "d"],
    "nv": ["n", "v"], "av": ["a", "v"], "dv": ["d", "v"],
}


def expand_pos(pos):
    """Expand POS codes like 'v;vn;b' to full English names, no duplicates."""
    if not pos:
        return ""
    parts = []
    for p in pos.split(";"):
        p = p.strip()
        if not p:
            continue
        for code in COMBO_POS.get(p, [p]):
            full = POS_FULL.get(code, code)
            if full not in parts:
                parts.append(full)
    return " / ".join(parts)


def render_word(word_text, vocab, highlight_words):
    """Render a single word as HTML with annotations."""
    if not word_text.strip():
        return word_text

    info = vocab.get(word_text, {})
    hsk = info.get("hsk", 0)
    pinyin = normalize_pinyin(info.get("pinyin", ""))
    en_def = info.get("en_def", "")

    # If word not in vocab or has no pinyin, build from individual chars
    if not pinyin:
        char_pinyins = []
        char_defs = []
        char_hsk_max = 0
        for ch in word_text:
            ch_info = vocab.get(ch, {})
            ch_hsk = ch_info.get("hsk", 0)
            if ch_hsk > 0:
                char_hsk_max = max(char_hsk_max, ch_hsk)
            ch_py = normalize_pinyin(ch_info.get("pinyin", ""))
            ch_def = ch_info.get("en_def", "")
            if ch_py:
                char_pinyins.append(ch_py)
            if ch_def:
                char_defs.append(ch_def)
        if char_pinyins:
            pinyin = " ".join(char_pinyins)
        if char_defs:
            en_def = "; ".join(char_defs)[:40]
        if char_hsk_max > 0:
            hsk = char_hsk_max

    # Last resort: if still no pinyin, try each char individually
    if not pinyin:
        char_pinyins = []
        for ch in word_text:
            if "\u4e00" <= ch <= "\u9fff":
                ch_info = vocab.get(ch, {})
                ch_py = normalize_pinyin(ch_info.get("pinyin", ""))
                if ch_py:
                    char_pinyins.append(ch_py)
                else:
                    char_pinyins.append("")  # empty slot for unknown char
            else:
                char_pinyins.append("")
        pinyin = " ".join(char_pinyins) if any(char_pinyins) else ""

    color = HSK_COLORS.get(hsk, "#aaa")
    light_bg = HSK_LIGHT_BG.get(hsk, "transparent")
    label = HSK_LABELS.get(hsk, "")

    is_highlight = word_text in highlight_words
    highlight_cls = " hl" if is_highlight else ""
    hsk_cls = f" hsk{hsk}" if hsk > 0 else " nohsk"

    text = esc(word_text)
    py = esc(pinyin) if pinyin else ""

    # Build tooltip text: full English definition + HSK label
    tooltip_parts = []
    if en_def:
        tooltip_parts.append(esc(en_def))
    if hsk > 0:
        tooltip_parts.append(f"[{label}]")
    tooltip = " ".join(tooltip_parts)

    parts = [f'<span class="w{hsk_cls}{highlight_cls}" style="--c:{color};--bg:{light_bg};" title="{tooltip}">']
    parts.append(f'<span class="py">{py}</span>')
    parts.append(f'<span class="cz">{text}</span>')
    if is_highlight:
        parts.append('<span class="star">★</span>')
    parts.append('</span>')
    return "".join(parts)


def render_punctuation(punct):
    """Render punctuation without annotations."""
    if not punct.strip():
        return ""
    return f'<span class="punct">{esc(punct)}</span>'


def extract_example_sentence(essay_text, expression):
    """Find the sentence in essay text that contains the expression."""
    if not expression or not expression.strip():
        return ""
    # Split essay into sentences by Chinese sentence-ending punctuation
    sentences = re.split(r'(?<=[。！？…\n])', essay_text)
    for sent in sentences:
        sent = sent.strip()
        if expression in sent and len(sent) > 5:
            return sent
    # Try splitting by commas too for shorter expressions
    clauses = re.split(r'(?<=[，；])', essay_text)
    for clause in clauses:
        clause = clause.strip()
        if expression in clause and len(clause) > 5:
            return clause
    return ""


LOW_VALUE_POS = {"r", "u", "c", "p", "e", "m", "q", "h", "k", "j"}
MAX_NEW_WORDS = 12


def collect_new_words(essay_text, vocab, user_level, expressions=()):
    """Collect new words, curated by learning value (max 12).

    Candidates are words at or above the user's HSK level (words BELOW the
    user's level are NEVER new words). Only high-value words are shown:
    pure function words (pronouns/particles/conjunctions/prepositions/measure
    words etc.) are skipped, words already taught in Key Words & Sentences
    are not repeated, and words nearer the user's level rank first, then
    longer words (idioms), then earlier words in the essay.
    """
    try:
        user_level = int(user_level)
    except (TypeError, ValueError):
        user_level = 6
    if user_level < 1:
        user_level = 1
    if user_level > 6:
        user_level = 6

    taught = set()
    for ex in expressions or ():
        word = (ex.get("expression") or "").strip() if isinstance(ex, dict) else str(ex).strip()
        if word:
            taught.add(word)

    segments = segment_text(essay_text, vocab)
    found = {}
    order = []
    for word, is_punct in segments:
        if is_punct or not word.strip():
            continue
        if word in taught:
            continue
        info = vocab.get(word, {})
        hsk = info.get("hsk", 0)
        if hsk >= user_level and hsk > 0 and word not in found:
            pos_codes = set(str(info.get("pos", "")).split(";"))
            if pos_codes and pos_codes <= LOW_VALUE_POS:
                continue
            en_def = info.get("en_def", "")
            if not en_def or en_def.lstrip().lower().startswith("used in"):
                continue  # bound morpheme entries (e.g. 假 "used in 假装") carry no learning value
            example = extract_example_sentence(essay_text, word)
            found[word] = {
                "word": word,
                "pinyin": normalize_pinyin(info.get("pinyin", "")),
                "hsk": hsk,
                "pos": info.get("pos", ""),
                "en_def": en_def,
                "example": example,
            }
            order.append(word)

    ranked = sorted(
        found.values(),
        key=lambda nw: (abs(nw["hsk"] - user_level), -len(nw["word"]), order.index(nw["word"])),
    )
    selected = ranked[:MAX_NEW_WORDS]
    selected.sort(key=lambda nw: (nw["hsk"], order.index(nw["word"])))
    return selected


def generate_new_words_html(new_words, user_level):
    """Render the New Words section HTML."""
    try:
        level_int = int(user_level)
    except (TypeError, ValueError):
        level_int = 6

    if not new_words:
        return '''<div class="nw-empty">No more high-value new words at HSK %d and above — the essential ones are covered in Key Words &amp; Sentences. Great job!</div>''' % level_int

    cards = []
    for nw in new_words:
        color = HSK_COLORS.get(nw["hsk"], "#555")
        label = HSK_LABELS.get(nw["hsk"], "")
        bg = HSK_LIGHT_BG.get(nw["hsk"], "#f9f9f9")
        pos_full = expand_pos(nw.get("pos", ""))
        example = esc(nw.get("example", ""))
        en_def = esc(nw.get("en_def", ""))
        pos_html = f'<div class="ecard-meta">{esc(pos_full)}</div>' if pos_full else ""

        cards.append(f'''
    <div class="ecard" style="--c:{color};--bg:{bg};">
      <div class="ecard-head">
        <span class="ecard-text">{esc(nw["word"])}</span>
        <span class="ecard-py">{esc(nw["pinyin"])}</span>
        <span class="ecard-hsk" style="background:{color};">{label}</span>
      </div>
      {pos_html}
      <div class="ecard-en">{en_def}</div>
      <div class="ecard-ex"><span class="ecard-ex-label">Example:</span> {example}</div>
    </div>''')
    return "\n".join(cards)


def build_paper_view(essay_text, title):
    """Build the composition-paper view: one character per grid cell, KaiTi font.

    Restores the real writing scenario (方格作文纸). The title takes the first
    row starting at the 5th cell (标题空四格); each body paragraph starts with
    two blank cells (首行空两格). Punctuation also occupies one cell.
    """
    paras = []
    if title and title.strip():
        title_cells = [f'<span class="gc">{esc(ch)}</span>' for ch in title if ch not in (" ", "\u3000")]
        if title_cells:
            indent = '<span class="gc blank"></span>' * 4
            paras.append(f'<p class="gpara">{indent}{"".join(title_cells)}</p>')
    for raw in essay_text.split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        cells = []
        for ch in raw:
            if ch in (" ", "\u3000"):
                continue
            cells.append(f'<span class="gc">{esc(ch)}</span>')
        if cells:
            indent = '<span class="gc blank"></span><span class="gc blank"></span>'
            paras.append(f'<p class="gpara">{indent}{"".join(cells)}</p>')
    paras_html = "\n".join(paras)
    return f'''
  <div class="paper-body">
{paras_html}
  </div>'''


def _strip_title_line(essay_text, title):
    """Drop the title line from the body when the first non-empty line matches it."""
    if not title or not title.strip():
        return essay_text
    lines = essay_text.split("\n")
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        if ln.strip() == title.strip():
            return "\n".join(lines[:i] + lines[i + 1:])
        return essay_text
    return essay_text


def generate_html(essay_text, title, hsk_level, source_url, word_count, good_expressions, vocab):
    """Generate the complete HTML page."""
    # Build highlight set from good expressions
    highlight_words = set()
    for expr in good_expressions:
        expr_text = expr.get("expression", "")
        if expr_text:
            highlight_words.add(expr_text)

    # The title renders on its own line (indented 4 chars), never as body text
    body_text = _strip_title_line(essay_text, title)

    # One paragraph per input line (每段首行空两格)
    paragraph_texts = [ln.strip() for ln in body_text.split("\n") if ln.strip()]

    essay_html_parts = []
    if title and title.strip():
        essay_html_parts.append(f'<p class="essay-title-line">{esc(title)}</p>')
    for para_text in paragraph_texts:
        parts = []
        for word, is_punct in segment_text(para_text, vocab):
            if is_punct:
                parts.append(render_punctuation(word))
            else:
                parts.append(render_word(word, vocab, highlight_words))
        essay_html_parts.append('<p class="para">' + "".join(parts) + '</p>')
    essay_html = "\n".join(essay_html_parts)

    # Build composition-paper view (方格/横线作文纸, KaiTi font, 标题空四格+首行空两格)
    paper_html = build_paper_view(body_text, title)

    # Collect new words (curated, HSK level >= user's level) and render the section
    new_words = collect_new_words(body_text, vocab, hsk_level, good_expressions)
    new_words_html = generate_new_words_html(new_words, hsk_level)

    # Render good expression cards
    expr_cards = []
    for expr in good_expressions:
        expression_raw = expr.get("expression", "")
        expression = esc(expression_raw)
        pinyin = esc(expr.get("pinyin", ""))
        hsk = expr.get("hsk", 0)
        en_def = esc(expr.get("en_def", ""))
        explanation = esc(expr.get("explanation", ""))
        example = expr.get("example", "")
        # Auto-extract example from essay if not provided
        if not example or not example.strip():
            example = extract_example_sentence(essay_text, expression_raw)
        example = esc(example)
        color = HSK_COLORS.get(hsk, "#555")
        label = HSK_LABELS.get(hsk, "")
        bg = HSK_LIGHT_BG.get(hsk, "#f9f9f9")

        expr_cards.append(f'''
    <div class="ecard" style="--c:{color};--bg:{bg};">
      <div class="ecard-head">
        <span class="ecard-text">{expression}</span>
        <span class="ecard-py">{pinyin}</span>
        <span class="ecard-hsk" style="background:{color};">{label}</span>
      </div>
      <div class="ecard-en">{en_def}</div>
      <div class="ecard-exp">{explanation}</div>
      <div class="ecard-ex"><span class="ecard-ex-label">Example:</span> {example}</div>
    </div>''')
    expr_html = "\n".join(expr_cards)

    level_label = HSK_LABELS.get(int(hsk_level), f"HSK {hsk_level}")
    level_color = HSK_COLORS.get(int(hsk_level), "#333")

    legend_items = "".join(
        f'<span class="lg-item"><span class="lg-dot" style="background:{color};"></span>{HSK_LABELS[level]}</span>'
        for level, color in HSK_COLORS.items()
    )

    title_esc = esc(title)
    source_esc = esc(source_url)
    header_h1 = f"<h1>{title_esc}</h1>" if title_esc else ""
    title_tag = esc(f"{title} - Essay Display") if title and title.strip() else "Essay Display"

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_tag}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif;
    background: linear-gradient(160deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #2c3e50;
    padding: 0;
  }}
  .container {{ max-width: 920px; margin: 0 auto; padding: 36px 20px 60px; }}
  .header {{
    text-align: center; margin-bottom: 28px; padding: 36px 28px;
    background: white; border-radius: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.12);
  }}
  .header h1 {{ font-size: 30px; font-weight: 800; color: #1a1a2e; margin-bottom: 14px; letter-spacing: 3px; }}
  .meta {{ display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }}
  .badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 18px; border-radius: 24px; font-size: 14px; font-weight: 600; }}
  .badge-level {{ background: {level_color}; color: white; }}
  .badge-count {{ background: #f0f2f5; color: #555; }}
  .badge-source {{ background: #f0f2f5; color: #555; }}
  .badge-source a {{ color: inherit; text-decoration: none; }}
  .badge-source a:hover {{ text-decoration: underline; }}
  .legend {{
    display: flex; justify-content: center; gap: 14px; flex-wrap: wrap;
    margin-bottom: 24px; padding: 14px 24px; background: rgba(255,255,255,0.95);
    border-radius: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  }}
  .lg-item {{ display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; color: #444; }}
  .lg-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
  .essay {{
    background: white; border-radius: 20px; padding: 48px 40px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12); margin-bottom: 32px;
  }}
  .para {{ margin-bottom: 20px; text-align: justify; line-height: 1.5; text-indent: 2em; }}
  .essay-title-line {{ margin: 0 0 26px; text-indent: 4em; text-align: left; font-size: 22px; font-weight: 800; color: #1a1a2e; letter-spacing: 2px; line-height: 1.5; }}
  .w {{
    display: inline-flex; flex-direction: column; align-items: center;
    vertical-align: top; margin: 0 0 7px; padding: 2px 2px 3px;
    border-radius: 5px; position: relative; transition: all 0.2s ease;
    border-bottom: 2px solid var(--c, transparent); background: var(--bg, transparent);
  }}
  .w:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 10; }}
  .py {{
    font-size: 10px; font-weight: 500; color: var(--c, #999);
    font-family: "Georgia", "Times New Roman", serif; line-height: 1.15;
    margin-bottom: 2px; min-height: 11px; text-align: center;
  }}
  .cz {{ font-size: 20px; font-weight: 600; color: #1a1a2e; line-height: 1.3; text-align: center; }}
  .w.nohsk {{ border-bottom-color: transparent; background: transparent; }}
  .w.nohsk .py {{ color: #bbb; }}
  .w[title]:hover::after {{
    content: attr(title); position: absolute; bottom: calc(100% + 6px); left: 50%;
    transform: translateX(-50%); background: rgba(20,20,40,0.95); color: #fff;
    padding: 10px 18px; border-radius: 8px; font-size: 14px; font-weight: 400;
    font-style: normal; line-height: 1.6; white-space: normal; max-width: 800px;
    min-width: 200px; text-align: left; z-index: 100; pointer-events: none;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
  }}
  .w[title]:hover::before {{
    content: ""; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
    border: 5px solid transparent; border-top-color: rgba(20,20,40,0.95); z-index: 100;
  }}
  .w.hl {{
    background: linear-gradient(135deg, #fff8e1, #fff3c4);
    border-bottom-color: #ffc107; border-bottom-width: 3px;
    box-shadow: 0 2px 8px rgba(255,193,7,0.2);
  }}
  .w.hl .cz {{ color: #e65100; }}
  .star {{ position: absolute; top: -8px; right: -4px; font-size: 13px; color: #ff9800; text-shadow: 0 1px 2px rgba(255,152,0,0.3); }}
  .punct {{ font-size: 20px; color: #555; font-weight: 600; vertical-align: top; display: inline-block; margin: 0; padding-top: 15px; }}
  .view-bar {{ display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-bottom: 24px; }}
  .view-btn {{
    border: 2px solid rgba(255,255,255,0.7); background: rgba(255,255,255,0.15);
    color: white; font-size: 14px; font-weight: 600; padding: 9px 20px;
    border-radius: 22px; cursor: pointer; transition: all 0.2s ease;
  }}
  .view-btn:hover {{ background: rgba(255,255,255,0.32); }}
  .view-btn.active {{ background: white; color: #5b4b8a; border-color: white; box-shadow: 0 4px 14px rgba(0,0,0,0.18); }}
  .paper {{ background: white; border-radius: 20px; padding: 34px 30px 40px; box-shadow: 0 8px 32px rgba(0,0,0,0.12); margin-bottom: 32px; }}
  .gc {{ font-family: "KaiTi", "楷体", "STKaiti", "Kaiti SC", "TW-Kai", serif; font-size: 26px; color: #1a1a2e; }}
  .gpara {{ margin: 0; }}
  .paper.grid .paper-body {{
    border: 2px solid #d99a9f;
    background-image:
      linear-gradient(to right, #f2c6ca 1px, transparent 1px),
      linear-gradient(to bottom, #f2c6ca 1px, transparent 1px);
    background-size: 34px 34px;
    padding: 0;
  }}
  .paper.grid .gpara {{ font-size: 0; line-height: 0; }}
  .paper.grid .gc {{ display: inline-block; width: 34px; height: 34px; line-height: 34px; text-align: center; vertical-align: top; }}
  .paper.grid .gc.blank {{ visibility: hidden; }}
  .paper.lines .paper-body {{
    border: 2px solid #b8c4d9;
    background-image: linear-gradient(to bottom, #b8c4d9 1px, transparent 1px);
    background-size: 100% 34px;
    background-position: 0 31px;
    padding: 0;
  }}
  .paper.lines .gpara {{ font-size: 0; line-height: 0; margin: 0; }}
  .paper.lines .gc {{ font-size: 26px; display: inline-block; height: 34px; line-height: 34px; vertical-align: top; transform: translateY(var(--dy, 0px)); }}
  .paper.lines .gc.blank {{ visibility: hidden; width: 26px; }}
  .nw-note {{ font-size: 14px; color: #888; margin-bottom: 18px; }}
  .nw-empty {{ font-size: 15px; color: #888; padding: 10px 0; }}
  .ecard-meta {{ font-size: 13px; font-weight: 600; color: var(--c, #888); margin-bottom: 6px; text-transform: capitalize; }}
  .expr-sec {{ background: white; border-radius: 20px; padding: 40px; box-shadow: 0 8px 32px rgba(0,0,0,0.12); }}
  .expr-title {{ font-size: 24px; font-weight: 800; color: #1a1a2e; margin-bottom: 24px; padding-bottom: 14px; border-bottom: 3px solid #f0f2f5; }}
  .ecard {{ border-left: 5px solid var(--c, #ccc); background: var(--bg, #f9f9f9); border-radius: 10px; padding: 22px 26px; margin-bottom: 16px; transition: transform 0.2s, box-shadow 0.2s; }}
  .ecard:hover {{ transform: translateX(6px); box-shadow: 0 4px 16px rgba(0,0,0,0.1); }}
  .ecard-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }}
  .ecard-text {{ font-size: 22px; font-weight: 800; color: #1a1a2e; }}
  .ecard-py {{ font-size: 15px; color: #888; font-family: "Georgia", serif; }}
  .ecard-hsk {{ font-size: 12px; color: white; padding: 3px 12px; border-radius: 12px; font-weight: 700; }}
  .ecard-en {{ font-size: 15px; color: #555; font-style: italic; margin-bottom: 10px; }}
  .ecard-exp {{ font-size: 14px; color: #333; line-height: 1.8; margin-bottom: 10px; }}
  .ecard-ex {{ font-size: 14px; color: #555; background: rgba(0,0,0,0.04); padding: 10px 14px; border-radius: 8px; line-height: 1.7; }}
  .ecard-ex-label {{ font-weight: 700; color: #7f8c8d; }}
  .footer {{ text-align: center; padding: 24px; font-size: 14px; color: rgba(255,255,255,0.7); }}
  .footer a {{ color: rgba(255,255,255,0.9); text-decoration: none; }}
  .footer a:hover {{ text-decoration: underline; }}
  @media (max-width: 600px) {{
    .container {{ padding: 16px 10px 40px; }}
    .header {{ padding: 24px 16px; border-radius: 16px; }}
    .header h1 {{ font-size: 24px; }}
    .essay {{ padding: 24px 14px; border-radius: 16px; }}
    .w {{ padding: 2px 1px 2px; margin: 0 0 6px; }}
    .py {{ font-size: 8.5px; min-height: 10px; }}
    .cz {{ font-size: 17px; }}
    .punct {{ font-size: 17px; padding-top: 13px; }}
    .essay-title-line {{ font-size: 19px; margin-bottom: 20px; }}
    .expr-sec {{ padding: 24px 16px; border-radius: 16px; }}
    .ecard {{ padding: 16px 18px; }}
    .ecard-text {{ font-size: 18px; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    {header_h1}
    <div class="meta">
      <span class="badge badge-level">{level_label}</span>
      <span class="badge badge-count">约 {word_count} 字</span>
      <span class="badge badge-source"><a href="{source_esc}" target="_blank">📍 zuowen.com</a></span>
    </div>
  </div>
  <div class="view-bar">
    <button class="view-btn active" data-mode="reading" onclick="switchMode('reading')">📖 阅读模式</button>
    <button class="view-btn" data-mode="grid" onclick="switchMode('grid')">⬛ 作文纸（方格）</button>
    <button class="view-btn" data-mode="lines" onclick="switchMode('lines')">📏 作文纸（横线）</button>
  </div>
  <div id="reading-view">
  <div class="legend">
    {legend_items}
    <span class="lg-item"><span class="lg-dot" style="background:#ffc107;"></span>★ Key Expression</span>
  </div>
  <div class="essay">
{essay_html}
  </div>
  </div>
  <div id="paper-view" class="paper grid" style="display:none;">
{paper_html}
  </div>
  <div class="expr-sec">
    <div class="expr-title">★ 重点词句 | Key Words &amp; Sentences</div>
{expr_html}
  </div>
  <div class="expr-sec">
    <div class="expr-title">📚 生词表 | New Words ({level_label} &amp; above)</div>
    <div class="nw-note">生词表为精选：从你所选等级及以上的词汇中挑选最值得学习的若干个（纯功能词与重点词句已讲解的不再重复），例句均取自本篇原文。 (A curated selection of high-value new words at your HSK level and above; pure function words and expressions already taught are not repeated. All examples are from this essay.)</div>
{new_words_html}
  </div>
  <div class="footer">
    Generated by Chinese Writing Tutor · Source: <a href="{source_esc}" target="_blank">zuowen.com</a>
  </div>
</div>
<script>
function switchMode(mode) {{
  var btns = document.querySelectorAll('.view-btn');
  for (var i = 0; i < btns.length; i++) {{
    btns[i].classList.toggle('active', btns[i].getAttribute('data-mode') === mode);
  }}
  document.getElementById('reading-view').style.display = (mode === 'reading') ? '' : 'none';
  var pv = document.getElementById('paper-view');
  pv.style.display = (mode === 'reading') ? 'none' : '';
  pv.className = (mode === 'grid') ? 'paper grid' : 'paper lines';
}}
(function() {{
  var HIGH = {{"\u201c":1, "\u201d":1, "\u2018":1, "\u2019":1, '"':1, "'":1, "\uff02":1, "\uff07":1, "\u2014":1, "\uff5e":1, "\u301c":1, "\u00b7":1, "-":1, "~":1, "\u00d7":1, "\u00f7":1}};
  try {{
    var paper = document.querySelector('.paper');
    if (!paper) return;
    var gcs = paper.querySelectorAll('.gc');
    var cv = document.createElement('canvas');
    var ctx = cv.getContext('2d');
    ctx.font = '26px "KaiTi", "楷体", "STKaiti", "Kaiti SC", "TW-Kai", serif';
    var probe = ctx.measureText('游');
    if (!probe || probe.fontBoundingBoxAscent === undefined) return;
    var hl = (34 - probe.fontBoundingBoxAscent - probe.fontBoundingBoxDescent) / 2;
    var base = hl + probe.fontBoundingBoxAscent;
    var cap = (31 - 1 - base - probe.actualBoundingBoxDescent) + 4;
    var cache = {{}};
    for (var i = 0; i < gcs.length; i++) {{
      var s = gcs[i];
      if (s.className.indexOf('blank') >= 0) continue;
      var ch = s.textContent;
      if (!ch || ch.length !== 1) continue;
      if (HIGH[ch]) continue;
      var d = cache[ch];
      if (d === undefined) d = cache[ch] = ctx.measureText(ch).actualBoundingBoxDescent;
      var t = 31 - 1 - base - d;
      if (d < 2) t -= 3;
      if (t > cap) t = cap;
      if (t < -3) t = -3;
      s.style.setProperty('--dy', (Math.round(t * 10) / 10) + 'px');
    }}
  }} catch (e) {{}}
}})();
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate annotated HTML essay display")
    parser.add_argument("--essay-file", help="Path to text file containing essay")
    parser.add_argument("--essay-text", help="Essay text directly (alternative to --essay-file)")
    parser.add_argument("--expressions-json", help="JSON file with good expressions array")
    parser.add_argument("--output", default="/mnt/user-data/outputs/essay_display.html")
    parser.add_argument("--hsk-level", default="6", help="HSK level for header display")
    parser.add_argument("--title", default="", help="Essay title")
    parser.add_argument("--source-url", default="", help="Source URL")
    parser.add_argument("--word-count", default="0", help="Word count")
    parser.add_argument("--vocab-dir", default="", help="Directory with HSK CSV files")
    args = parser.parse_args()

    # Get essay text
    if args.essay_file:
        with open(args.essay_file, encoding="utf-8") as f:
            essay_text = f.read()
    elif args.essay_text:
        essay_text = args.essay_text
    else:
        # Read from stdin
        essay_text = sys.stdin.read()

    # Get good expressions
    good_expressions = []
    if args.expressions_json and os.path.exists(args.expressions_json):
        with open(args.expressions_json, encoding="utf-8") as f:
            good_expressions = json.load(f)

    # Find vocab directory
    vocab_dir = args.vocab_dir
    if not vocab_dir:
        # Try to find relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        vocab_dir = os.path.join(script_dir, "..", "reference", "hsk_vocabulary")
        if not os.path.exists(vocab_dir):
            # Try workspace path
            vocab_dir = "/mnt/skills/user/chinese-writing-tutor-tcsl/v2.0.0/reference/hsk_vocabulary"

    vocab = load_hsk_vocab(vocab_dir)

    html_content = generate_html(
        essay_text=essay_text,
        title=args.title,
        hsk_level=args.hsk_level,
        source_url=args.source_url,
        word_count=args.word_count,
        good_expressions=good_expressions,
        vocab=vocab,
    )

    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8-sig") as f:
        f.write(html_content)

    print(f"HTML_SAVED:{args.output}")


if __name__ == "__main__":
    main()
