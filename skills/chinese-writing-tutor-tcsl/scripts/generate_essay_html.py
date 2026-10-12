#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""All-in-one script: read essay text + good expressions, generate annotated HTML.

Usage:
    python3 generate_essay_html.py --essay-file essay.txt --expressions-json expr.json --output essay_旅行_HSK6.html --hsk-level 6

Or pipe essay text:
    echo "essay text" | python3 generate_essay_html.py --expressions-json expr.json --output out.html --hsk-level 6

The script:
1. Loads HSK vocabulary from CSV files (levels 1-6)
2. Segments essay text using longest-match against HSK vocab + common words
3. Annotates each word with pinyin, HSK level, English definition
4. Highlights good expressions
5. Generates a beautiful standalone HTML file
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
    """Segment Chinese text using longest-match against HSK vocab.
    Returns list of (word, is_punctuation) tuples.
    """
    # Common function words and particles not always in HSK list
    common_words = {
        "的": {"hsk": 1, "pinyin": "de", "en_def": "structural particle", "pos": "part"},
        "了": {"hsk": 1, "pinyin": "le", "en_def": "completed action", "pos": "part"},
        "是": {"hsk": 1, "pinyin": "shì", "en_def": "is; to be", "pos": "v"},
        "在": {"hsk": 1, "pinyin": "zài", "en_def": "at; in; on", "pos": "prep"},
        "有": {"hsk": 1, "pinyin": "yǒu", "en_def": "to have", "pos": "v"},
        "不": {"hsk": 1, "pinyin": "bù", "en_def": "not", "pos": "adv"},
        "我": {"hsk": 1, "pinyin": "wǒ", "en_def": "I; me", "pos": "pron"},
        "你": {"hsk": 1, "pinyin": "nǐ", "en_def": "you", "pos": "pron"},
        "他": {"hsk": 1, "pinyin": "tā", "en_def": "he; him", "pos": "pron"},
        "她": {"hsk": 1, "pinyin": "tā", "en_def": "she; her", "pos": "pron"},
        "们": {"hsk": 1, "pinyin": "men", "en_def": "plural marker", "pos": "suffix"},
        "和": {"hsk": 1, "pinyin": "hé", "en_def": "and", "pos": "conj"},
        "就": {"hsk": 2, "pinyin": "jiù", "en_def": "then; just", "pos": "adv"},
        "都": {"hsk": 2, "pinyin": "dōu", "en_def": "all; both", "pos": "adv"},
        "也": {"hsk": 1, "pinyin": "yě", "en_def": "also; too", "pos": "adv"},
        "这": {"hsk": 1, "pinyin": "zhè", "en_def": "this", "pos": "pron"},
        "那": {"hsk": 1, "pinyin": "nà", "en_def": "that", "pos": "pron"},
        "要": {"hsk": 1, "pinyin": "yào", "en_def": "to want; to need", "pos": "v"},
        "会": {"hsk": 1, "pinyin": "huì", "en_def": "can; will", "pos": "v"},
        "能": {"hsk": 2, "pinyin": "néng", "en_def": "can; able to", "pos": "v"},
        "着": {"hsk": 2, "pinyin": "zhe", "en_def": "particle for ongoing action", "pos": "part"},
        "过": {"hsk": 2, "pinyin": "guò", "en_def": "particle for past experience", "pos": "part"},
        "把": {"hsk": 3, "pinyin": "bǎ", "en_def": "object marker", "pos": "prep"},
        "被": {"hsk": 3, "pinyin": "bèi", "en_def": "passive marker", "pos": "prep"},
        "让": {"hsk": 3, "pinyin": "ràng", "en_def": "to let; to allow", "pos": "v"},
        "给": {"hsk": 1, "pinyin": "gěi", "en_def": "to give; for", "pos": "v"},
        "对": {"hsk": 1, "pinyin": "duì", "en_def": "to; toward; correct", "pos": "prep"},
        "从": {"hsk": 2, "pinyin": "cóng", "en_def": "from", "pos": "prep"},
        "到": {"hsk": 1, "pinyin": "dào", "en_def": "to; until; arrive", "pos": "v"},
        "里": {"hsk": 1, "pinyin": "lǐ", "en_def": "in; inside", "pos": "n"},
        "上": {"hsk": 1, "pinyin": "shàng", "en_def": "on; above", "pos": "n"},
        "下": {"hsk": 1, "pinyin": "xià", "en_def": "down; below", "pos": "n"},
        "中": {"hsk": 2, "pinyin": "zhōng", "en_def": "in; among", "pos": "n"},
        "地": {"hsk": 2, "pinyin": "de", "en_def": "adverb marker", "pos": "part"},
        "得": {"hsk": 2, "pinyin": "de", "en_def": "complement marker", "pos": "part"},
        "又": {"hsk": 2, "pinyin": "yòu", "en_def": "again; also", "pos": "adv"},
        "还": {"hsk": 2, "pinyin": "hái", "en_def": "still; also", "pos": "adv"},
        "很": {"hsk": 1, "pinyin": "hěn", "en_def": "very", "pos": "adv"},
        "但": {"hsk": 3, "pinyin": "dàn", "en_def": "but; however", "pos": "conj"},
        "而": {"hsk": 3, "pinyin": "ér", "en_def": "and; but", "pos": "conj"},
        "与": {"hsk": 3, "pinyin": "yǔ", "en_def": "and; with", "pos": "conj"},
        "或": {"hsk": 3, "pinyin": "huò", "en_def": "or", "pos": "conj"},
        "已": {"hsk": 3, "pinyin": "yǐ", "en_def": "already", "pos": "adv"},
        "才": {"hsk": 3, "pinyin": "cái", "en_def": "just; only then", "pos": "adv"},
        "再": {"hsk": 2, "pinyin": "zài", "en_def": "again; once more", "pos": "adv"},
        "只": {"hsk": 2, "pinyin": "zhǐ", "en_def": "only; just", "pos": "adv"},
        "一": {"hsk": 1, "pinyin": "yī", "en_def": "one", "pos": "num"},
        "个": {"hsk": 1, "pinyin": "gè", "en_def": "measure word", "pos": "measure"},
        "人": {"hsk": 1, "pinyin": "rén", "en_def": "person; people", "pos": "n"},
        "大": {"hsk": 1, "pinyin": "dà", "en_def": "big; large", "pos": "a"},
        "小": {"hsk": 1, "pinyin": "xiǎo", "en_def": "small; little", "pos": "a"},
        "多": {"hsk": 1, "pinyin": "duō", "en_def": "many; much", "pos": "a"},
        "少": {"hsk": 1, "pinyin": "shǎo", "en_def": "few; less", "pos": "a"},
        "好": {"hsk": 1, "pinyin": "hǎo", "en_def": "good", "pos": "a"},
        "来": {"hsk": 1, "pinyin": "lái", "en_def": "to come", "pos": "v"},
        "去": {"hsk": 1, "pinyin": "qù", "en_def": "to go", "pos": "v"},
        "看": {"hsk": 1, "pinyin": "kàn", "en_def": "to see; to look", "pos": "v"},
        "说": {"hsk": 1, "pinyin": "shuō", "en_def": "to say; to speak", "pos": "v"},
        "做": {"hsk": 2, "pinyin": "zuò", "en_def": "to do; to make", "pos": "v"},
        "想": {"hsk": 1, "pinyin": "xiǎng", "en_def": "to think; to want", "pos": "v"},
        "它": {"hsk": 1, "pinyin": "tā", "en_def": "it", "pos": "pron"},
        "为": {"hsk": 2, "pinyin": "wèi", "en_def": "for; because of", "pos": "prep"},
        "所": {"hsk": 3, "pinyin": "suǒ", "en_def": "that which", "pos": "pron"},
        "以": {"hsk": 2, "pinyin": "yǐ", "en_def": "by means of; with", "pos": "prep"},
        "可": {"hsk": 2, "pinyin": "kě", "en_def": "can; may", "pos": "v"},
        "个": {"hsk": 1, "pinyin": "gè", "en_def": "general measure word", "pos": "measure"},
        "吧": {"hsk": 1, "pinyin": "ba", "en_def": "particle (suggestion)", "pos": "part"},
        "呢": {"hsk": 1, "pinyin": "ne", "en_def": "particle (question)", "pos": "part"},
        "啊": {"hsk": 2, "pinyin": "a", "en_def": "particle (emotion)", "pos": "part"},
        "吗": {"hsk": 1, "pinyin": "ma", "en_def": "particle (yes/no question)", "pos": "part"},
        # Common single chars that appear in compound words
        "美": {"hsk": 0, "pinyin": "měi", "en_def": "beautiful", "pos": "a"},
        "丽": {"hsk": 0, "pinyin": "lì", "en_def": "beautiful", "pos": "a"},
        "福": {"hsk": 0, "pinyin": "fú", "en_def": "fortune; blessing", "pos": "n"},
        "景": {"hsk": 0, "pinyin": "jǐng", "en_def": "scenery; view", "pos": "n"},
        "情": {"hsk": 0, "pinyin": "qíng", "en_def": "feeling; emotion", "pos": "n"},
        "事": {"hsk": 0, "pinyin": "shì", "en_def": "thing; matter", "pos": "n"},
        "物": {"hsk": 0, "pinyin": "wù", "en_def": "thing; object", "pos": "n"},
        "心": {"hsk": 1, "pinyin": "xīn", "en_def": "heart", "pos": "n"},
        "力": {"hsk": 1, "pinyin": "lì", "en_def": "power; force", "pos": "n"},
        "道": {"hsk": 2, "pinyin": "dào", "en_def": "way; road; to say", "pos": "n"},
        "理": {"hsk": 0, "pinyin": "lǐ", "en_def": "reason; logic", "pos": "n"},
        "明": {"hsk": 1, "pinyin": "míng", "en_def": "bright; clear", "pos": "a"},
        "天": {"hsk": 1, "pinyin": "tiān", "en_def": "sky; day", "pos": "n"},
        "地": {"hsk": 1, "pinyin": "dì", "en_def": "earth; ground", "pos": "n"},
        "日": {"hsk": 1, "pinyin": "rì", "en_def": "sun; day", "pos": "n"},
        "月": {"hsk": 1, "pinyin": "yuè", "en_def": "moon; month", "pos": "n"},
        "年": {"hsk": 1, "pinyin": "nián", "en_def": "year", "pos": "n"},
        "时": {"hsk": 1, "pinyin": "shí", "en_def": "time", "pos": "n"},
        "分": {"hsk": 1, "pinyin": "fēn", "en_def": "minute; to divide", "pos": "n"},
        "点": {"hsk": 1, "pinyin": "diǎn", "en_def": "point; o'clock", "pos": "n"},
        "话": {"hsk": 1, "pinyin": "huà", "en_def": "speech; words", "pos": "n"},
        "字": {"hsk": 1, "pinyin": "zì", "en_def": "character; word", "pos": "n"},
        "书": {"hsk": 1, "pinyin": "shū", "en_def": "book", "pos": "n"},
        "手": {"hsk": 1, "pinyin": "shǒu", "en_def": "hand", "pos": "n"},
        "目": {"hsk": 0, "pinyin": "mù", "en_def": "eye; item", "pos": "n"},
        "口": {"hsk": 1, "pinyin": "kǒu", "en_def": "mouth; entrance", "pos": "n"},
        "门": {"hsk": 1, "pinyin": "mén", "en_def": "door; gate", "pos": "n"},
        "路": {"hsk": 1, "pinyin": "lù", "en_def": "road; way", "pos": "n"},
        "头": {"hsk": 1, "pinyin": "tóu", "en_def": "head", "pos": "n"},
        "长": {"hsk": 1, "pinyin": "cháng", "en_def": "long", "pos": "a"},
        "高": {"hsk": 1, "pinyin": "gāo", "en_def": "tall; high", "pos": "a"},
        "低": {"hsk": 0, "pinyin": "dī", "en_def": "low", "pos": "a"},
        "快": {"hsk": 1, "pinyin": "kuài", "en_def": "fast; quick", "pos": "a"},
        "慢": {"hsk": 0, "pinyin": "màn", "en_def": "slow", "pos": "a"},
        "远": {"hsk": 2, "pinyin": "yuǎn", "en_def": "far", "pos": "a"},
        "近": {"hsk": 2, "pinyin": "jìn", "en_def": "near", "pos": "a"},
        "重": {"hsk": 2, "pinyin": "zhòng", "en_def": "heavy; important", "pos": "a"},
        "轻": {"hsk": 0, "pinyin": "qīng", "en_def": "light", "pos": "a"},
        "深": {"hsk": 2, "pinyin": "shēn", "en_def": "deep", "pos": "a"},
        "浅": {"hsk": 0, "pinyin": "qiǎn", "en_def": "shallow", "pos": "a"},
        "真": {"hsk": 1, "pinyin": "zhēn", "en_def": "true; real", "pos": "a"},
        "假": {"hsk": 0, "pinyin": "jiǎ", "en_def": "fake; false", "pos": "a"},
        "老": {"hsk": 1, "pinyin": "lǎo", "en_def": "old", "pos": "a"},
        "新": {"hsk": 1, "pinyin": "xīn", "en_def": "new", "pos": "a"},
        "早": {"hsk": 1, "pinyin": "zǎo", "en_def": "early", "pos": "a"},
        "晚": {"hsk": 1, "pinyin": "wǎn", "en_def": "late; evening", "pos": "a"},
        "前": {"hsk": 1, "pinyin": "qián", "en_def": "front; before", "pos": "n"},
        "后": {"hsk": 1, "pinyin": "hòu", "en_def": "back; after", "pos": "n"},
        "左": {"hsk": 1, "pinyin": "zuǒ", "en_def": "left", "pos": "n"},
        "右": {"hsk": 1, "pinyin": "yòu", "en_def": "right", "pos": "n"},
        "内": {"hsk": 2, "pinyin": "nèi", "en_def": "inside", "pos": "n"},
        "外": {"hsk": 1, "pinyin": "wài", "en_def": "outside", "pos": "n"},
        "东": {"hsk": 1, "pinyin": "dōng", "en_def": "east", "pos": "n"},
        "西": {"hsk": 1, "pinyin": "xī", "en_def": "west", "pos": "n"},
        "南": {"hsk": 1, "pinyin": "nán", "en_def": "south", "pos": "n"},
        "北": {"hsk": 1, "pinyin": "běi", "en_def": "north", "pos": "n"},
        "声": {"hsk": 1, "pinyin": "shēng", "en_def": "sound; voice", "pos": "n"},
        "色": {"hsk": 1, "pinyin": "sè", "en_def": "color", "pos": "n"},
        "光": {"hsk": 1, "pinyin": "guāng", "en_def": "light", "pos": "n"},
        "风": {"hsk": 1, "pinyin": "fēng", "en_def": "wind", "pos": "n"},
        "雨": {"hsk": 1, "pinyin": "yǔ", "en_def": "rain", "pos": "n"},
        "云": {"hsk": 1, "pinyin": "yún", "en_def": "cloud", "pos": "n"},
        "水": {"hsk": 1, "pinyin": "shuǐ", "en_def": "water", "pos": "n"},
        "火": {"hsk": 1, "pinyin": "huǒ", "en_def": "fire", "pos": "n"},
        "山": {"hsk": 1, "pinyin": "shān", "en_def": "mountain", "pos": "n"},
        "河": {"hsk": 1, "pinyin": "hé", "en_def": "river", "pos": "n"},
        "花": {"hsk": 1, "pinyin": "huā", "en_def": "flower", "pos": "n"},
        "草": {"hsk": 0, "pinyin": "cǎo", "en_def": "grass", "pos": "n"},
        "树": {"hsk": 1, "pinyin": "shù", "en_def": "tree", "pos": "n"},
        "叶": {"hsk": 0, "pinyin": "yè", "en_def": "leaf", "pos": "n"},
        "鸟": {"hsk": 1, "pinyin": "niǎo", "en_def": "bird", "pos": "n"},
        "鱼": {"hsk": 1, "pinyin": "yú", "en_def": "fish", "pos": "n"},
        "马": {"hsk": 1, "pinyin": "mǎ", "en_def": "horse", "pos": "n"},
        "牛": {"hsk": 0, "pinyin": "niú", "en_def": "cow; ox", "pos": "n"},
        "羊": {"hsk": 0, "pinyin": "yáng", "en_def": "sheep", "pos": "n"},
        "虫": {"hsk": 0, "pinyin": "chóng", "en_def": "insect; bug", "pos": "n"},
        "走": {"hsk": 1, "pinyin": "zǒu", "en_def": "to walk; to go", "pos": "v"},
        "跑": {"hsk": 0, "pinyin": "pǎo", "en_def": "to run", "pos": "v"},
        "飞": {"hsk": 1, "pinyin": "fēi", "en_def": "to fly", "pos": "v"},
        "吃": {"hsk": 1, "pinyin": "chī", "en_def": "to eat", "pos": "v"},
        "喝": {"hsk": 1, "pinyin": "hē", "en_def": "to drink", "pos": "v"},
        "住": {"hsk": 1, "pinyin": "zhù", "en_def": "to live; to stay", "pos": "v"},
        "用": {"hsk": 1, "pinyin": "yòng", "en_def": "to use", "pos": "v"},
        "爱": {"hsk": 1, "pinyin": "ài", "en_def": "to love", "pos": "v"},
        "怕": {"hsk": 0, "pinyin": "pà", "en_def": "to fear", "pos": "v"},
        "笑": {"hsk": 2, "pinyin": "xiào", "en_def": "to laugh; smile", "pos": "v"},
        "哭": {"hsk": 0, "pinyin": "kū", "en_def": "to cry", "pos": "v"},
        "听": {"hsk": 1, "pinyin": "tīng", "en_def": "to listen; hear", "pos": "v"},
        "写": {"hsk": 1, "pinyin": "xiě", "en_def": "to write", "pos": "v"},
        "读": {"hsk": 2, "pinyin": "dú", "en_def": "to read", "pos": "v"},
        "学": {"hsk": 1, "pinyin": "xué", "en_def": "to learn; study", "pos": "v"},
        "教": {"hsk": 2, "pinyin": "jiāo", "en_def": "to teach", "pos": "v"},
        "买": {"hsk": 1, "pinyin": "mǎi", "en_def": "to buy", "pos": "v"},
        "卖": {"hsk": 2, "pinyin": "mài", "en_def": "to sell", "pos": "v"},
        "开": {"hsk": 1, "pinyin": "kāi", "en_def": "to open", "pos": "v"},
        "关": {"hsk": 1, "pinyin": "guān", "en_def": "to close; shut", "pos": "v"},
        "坐": {"hsk": 1, "pinyin": "zuò", "en_def": "to sit", "pos": "v"},
        "站": {"hsk": 2, "pinyin": "zhàn", "en_def": "to stand", "pos": "v"},
        "死": {"hsk": 2, "pinyin": "sǐ", "en_def": "to die", "pos": "v"},
        "活": {"hsk": 2, "pinyin": "huó", "en_def": "to live; alive", "pos": "v"},
        "白": {"hsk": 1, "pinyin": "bái", "en_def": "white", "pos": "a"},
        "黑": {"hsk": 1, "pinyin": "hēi", "en_def": "black", "pos": "a"},
        "红": {"hsk": 2, "pinyin": "hóng", "en_def": "red", "pos": "a"},
        "绿": {"hsk": 0, "pinyin": "lǜ", "en_def": "green", "pos": "a"},
        "蓝": {"hsk": 0, "pinyin": "lán", "en_def": "blue", "pos": "a"},
        "黄": {"hsk": 1, "pinyin": "huáng", "en_def": "yellow", "pos": "a"},
        "金": {"hsk": 2, "pinyin": "jīn", "en_def": "gold", "pos": "n"},
        "银": {"hsk": 0, "pinyin": "yín", "en_def": "silver", "pos": "n"},
        "铁": {"hsk": 0, "pinyin": "tiě", "en_def": "iron", "pos": "n"},
        "石": {"hsk": 0, "pinyin": "shí", "en_def": "stone; rock", "pos": "n"},
        "土": {"hsk": 0, "pinyin": "tǔ", "en_def": "earth; soil", "pos": "n"},
        "田": {"hsk": 0, "pinyin": "tián", "en_def": "field; farmland", "pos": "n"},
        "林": {"hsk": 0, "pinyin": "lín", "en_def": "forest; woods", "pos": "n"},
        "木": {"hsk": 0, "pinyin": "mù", "en_def": "wood; tree", "pos": "n"},
        "足": {"hsk": 0, "pinyin": "zú", "en_def": "foot; enough", "pos": "n"},
        "身": {"hsk": 0, "pinyin": "shēn", "en_def": "body", "pos": "n"},
        "体": {"hsk": 1, "pinyin": "tǐ", "en_def": "body", "pos": "n"},
        "面": {"hsk": 1, "pinyin": "miàn", "en_def": "face; side", "pos": "n"},
        "首": {"hsk": 0, "pinyin": "shǒu", "en_def": "head; first", "pos": "n"},
        "半": {"hsk": 2, "pinyin": "bàn", "en_def": "half", "pos": "num"},
        "双": {"hsk": 0, "pinyin": "shuāng", "en_def": "pair; double", "pos": "num"},
        "万": {"hsk": 1, "pinyin": "wàn", "en_def": "ten thousand", "pos": "num"},
        "千": {"hsk": 1, "pinyin": "qiān", "en_def": "thousand", "pos": "num"},
        "百": {"hsk": 1, "pinyin": "bǎi", "en_def": "hundred", "pos": "num"},
        "十": {"hsk": 1, "pinyin": "shí", "en_def": "ten", "pos": "num"},
        "两": {"hsk": 1, "pinyin": "liǎng", "en_def": "two", "pos": "num"},
        "第": {"hsk": 2, "pinyin": "dì", "en_def": "number prefix", "pos": "prefix"},
        "次": {"hsk": 1, "pinyin": "cì", "en_def": "time; order", "pos": "measure"},
        "回": {"hsk": 1, "pinyin": "huí", "en_def": "to return; time", "pos": "v"},
        "位": {"hsk": 1, "pinyin": "wèi", "en_def": "seat; position", "pos": "measure"},
        "本": {"hsk": 1, "pinyin": "běn", "en_def": "book; measure word", "pos": "measure"},
        "只": {"hsk": 1, "pinyin": "zhǐ", "en_def": "only; measure word", "pos": "measure"},
        "些": {"hsk": 2, "pinyin": "xiē", "en_def": "some; a few", "pos": "measure"},
        "每": {"hsk": 2, "pinyin": "měi", "en_def": "every; each", "pos": "pron"},
        "各": {"hsk": 3, "pinyin": "gè", "en_def": "each; every", "pos": "pron"},
        "另": {"hsk": 0, "pinyin": "lìng", "en_def": "another; other", "pos": "pron"},
        "别": {"hsk": 2, "pinyin": "bié", "en_def": "other; don't", "pos": "pron"},
        "其": {"hsk": 3, "pinyin": "qí", "en_def": "its; that", "pos": "pron"},
        "此": {"hsk": 0, "pinyin": "cǐ", "en_def": "this", "pos": "pron"},
        "若": {"hsk": 0, "pinyin": "ruò", "en_def": "if; as if", "pos": "conj"},
        "故": {"hsk": 0, "pinyin": "gù", "en_def": "therefore; old", "pos": "conj"},
        "虽": {"hsk": 0, "pinyin": "suī", "en_def": "although", "pos": "conj"},
        "因": {"hsk": 3, "pinyin": "yīn", "en_def": "cause; because", "pos": "prep"},
        "由": {"hsk": 3, "pinyin": "yóu", "en_def": "from; by", "pos": "prep"},
        "让": {"hsk": 3, "pinyin": "ràng", "en_def": "to let; allow", "pos": "v"},
        "使": {"hsk": 3, "pinyin": "shǐ", "en_def": "to make; cause", "pos": "v"},
        "令": {"hsk": 0, "pinyin": "lìng", "en_def": "to make; cause", "pos": "v"},
        "成": {"hsk": 2, "pinyin": "chéng", "en_def": "to become; succeed", "pos": "v"},
        "化": {"hsk": 0, "pinyin": "huà", "en_def": "to change; transform", "pos": "v"},
        "动": {"hsk": 2, "pinyin": "dòng", "en_def": "to move", "pos": "v"},
        "静": {"hsk": 0, "pinyin": "jìng", "en_def": "quiet; still", "pos": "a"},
        "安": {"hsk": 0, "pinyin": "ān", "en_def": "safe; peaceful", "pos": "a"},
        "全": {"hsk": 2, "pinyin": "quán", "en_def": "all; complete", "pos": "a"},
        "保": {"hsk": 0, "pinyin": "bǎo", "en_def": "to protect; keep", "pos": "v"},
        "持": {"hsk": 0, "pinyin": "chí", "en_def": "to hold; maintain", "pos": "v"},
        "生": {"hsk": 1, "pinyin": "shēng", "en_def": "to be born; life", "pos": "v"},
        "死": {"hsk": 2, "pinyin": "sǐ", "en_def": "to die; death", "pos": "v"},
        "平": {"hsk": 0, "pinyin": "píng", "en_def": "flat; peaceful", "pos": "a"},
        "正": {"hsk": 1, "pinyin": "zhèng", "en_def": "correct; straight", "pos": "a"},
        "反": {"hsk": 2, "pinyin": "fǎn", "en_def": "reverse; opposite", "pos": "a"},
        "同": {"hsk": 2, "pinyin": "tóng", "en_def": "same; together", "pos": "a"},
        "异": {"hsk": 0, "pinyin": "yì", "en_def": "different; strange", "pos": "a"},
        "特": {"hsk": 0, "pinyin": "tè", "en_def": "special; particular", "pos": "a"},
        "奇": {"hsk": 0, "pinyin": "qí", "en_def": "strange; wonder", "pos": "a"},
        "怪": {"hsk": 0, "pinyin": "guài", "en_def": "strange; to blame", "pos": "a"},
        "意": {"hsk": 0, "pinyin": "yì", "en_def": "meaning; intention", "pos": "n"},
        "义": {"hsk": 0, "pinyin": "yì", "en_def": "meaning; justice", "pos": "n"},
        "思": {"hsk": 1, "pinyin": "sī", "en_def": "to think; thought", "pos": "v"},
        "念": {"hsk": 0, "pinyin": "niàn", "en_def": "to miss; read", "pos": "v"},
        "记": {"hsk": 2, "pinyin": "jì", "en_def": "to remember; record", "pos": "v"},
        "忘": {"hsk": 0, "pinyin": "wàng", "en_def": "to forget", "pos": "v"},
        "感": {"hsk": 0, "pinyin": "gǎn", "en_def": "to feel; sense", "pos": "v"},
        "觉": {"hsk": 1, "pinyin": "jué", "en_def": "to feel; wake", "pos": "v"},
        "知": {"hsk": 2, "pinyin": "zhī", "en_def": "to know", "pos": "v"},
        "识": {"hsk": 0, "pinyin": "shí", "en_def": "to know; knowledge", "pos": "v"},
        "信": {"hsk": 2, "pinyin": "xìn", "en_def": "letter; trust", "pos": "n"},
        "望": {"hsk": 0, "pinyin": "wàng", "en_def": "to look; hope", "pos": "v"},
        "期": {"hsk": 0, "pinyin": "qī", "en_def": "period; hope", "pos": "n"},
        "待": {"hsk": 0, "pinyin": "dài", "en_def": "to wait; treat", "pos": "v"},
        "自": {"hsk": 2, "pinyin": "zì", "en_def": "self; from", "pos": "pron"},
        "己": {"hsk": 1, "pinyin": "jǐ", "en_def": "self", "pos": "pron"},
        "相": {"hsk": 3, "pinyin": "xiāng", "en_def": "mutually", "pos": "adv"},
        "比": {"hsk": 2, "pinyin": "bǐ", "en_def": "to compare", "pos": "v"},
        "较": {"hsk": 0, "pinyin": "jiào", "en_def": "to compare; relatively", "pos": "v"},
        "最": {"hsk": 2, "pinyin": "zuì", "en_def": "most", "pos": "adv"},
        "更": {"hsk": 2, "pinyin": "gèng", "en_def": "more; even more", "pos": "adv"},
        "太": {"hsk": 1, "pinyin": "tài", "en_def": "too; very", "pos": "adv"},
        "极": {"hsk": 0, "pinyin": "jí", "en_def": "extremely", "pos": "adv"},
        "非": {"hsk": 3, "pinyin": "fēi", "en_def": "not; non-", "pos": "adv"},
        "常": {"hsk": 1, "pinyin": "cháng", "en_def": "often; constant", "pos": "adv"},
        "须": {"hsk": 0, "pinyin": "xū", "en_def": "must; need", "pos": "v"},
        "需": {"hsk": 0, "pinyin": "xū", "en_def": "to need; require", "pos": "v"},
        "应": {"hsk": 0, "pinyin": "yīng", "en_def": "should; respond", "pos": "v"},
        "当": {"hsk": 0, "pinyin": "dāng", "en_def": "should; to be", "pos": "v"},
        "肯": {"hsk": 0, "pinyin": "kěn", "en_def": "willing; to agree", "pos": "v"},
        "敢": {"hsk": 0, "pinyin": "gǎn", "en_def": "to dare", "pos": "v"},
        "或": {"hsk": 3, "pinyin": "huò", "en_def": "or; perhaps", "pos": "conj"},
        "者": {"hsk": 0, "pinyin": "zhě", "en_def": "person who...", "pos": "suffix"},
        "的": {"hsk": 1, "pinyin": "de", "en_def": "possessive particle", "pos": "part"},
        "确": {"hsk": 0, "pinyin": "què", "en_def": "indeed; true", "pos": "a"},
        "实": {"hsk": 2, "pinyin": "shí", "en_def": "real; solid", "pos": "a"},
        "行": {"hsk": 2, "pinyin": "xíng", "en_def": "to go; OK", "pos": "v"},
        "止": {"hsk": 0, "pinyin": "zhǐ", "en_def": "to stop", "pos": "v"},
        "起": {"hsk": 2, "pinyin": "qǐ", "en_def": "to rise; start", "pos": "v"},
        "落": {"hsk": 0, "pinyin": "luò", "en_def": "to fall; drop", "pos": "v"},
        "转": {"hsk": 2, "pinyin": "zhuǎn", "en_def": "to turn; change", "pos": "v"},
        "换": {"hsk": 0, "pinyin": "huàn", "en_def": "to change; exchange", "pos": "v"},
        "接": {"hsk": 2, "pinyin": "jiē", "en_def": "to receive; connect", "pos": "v"},
        "受": {"hsk": 2, "pinyin": "shòu", "en_def": "to receive; accept", "pos": "v"},
        "给": {"hsk": 1, "pinyin": "gěi", "en_def": "to give", "pos": "v"},
        "取": {"hsk": 0, "pinyin": "qǔ", "en_def": "to take; get", "pos": "v"},
        "放": {"hsk": 1, "pinyin": "fàng", "en_def": "to put; release", "pos": "v"},
        "带": {"hsk": 2, "pinyin": "dài", "en_def": "to bring; carry", "pos": "v"},
        "拉": {"hsk": 0, "pinyin": "lā", "en_def": "to pull", "pos": "v"},
        "推": {"hsk": 0, "pinyin": "tuī", "en_def": "to push", "pos": "v"},
        "打": {"hsk": 1, "pinyin": "dǎ", "en_def": "to hit; play", "pos": "v"},
        "找": {"hsk": 1, "pinyin": "zhǎo", "en_def": "to look for; find", "pos": "v"},
        "穿": {"hsk": 2, "pinyin": "chuān", "en_def": "to wear; pierce", "pos": "v"},
        "戴": {"hsk": 0, "pinyin": "dài", "en_def": "to wear (accessories)", "pos": "v"},
        "洗": {"hsk": 0, "pinyin": "xǐ", "en_def": "to wash", "pos": "v"},
        "照": {"hsk": 2, "pinyin": "zhào", "en_def": "to shine; photo", "pos": "v"},
        "算": {"hsk": 0, "pinyin": "suàn", "en_def": "to calculate; count", "pos": "v"},
        "数": {"hsk": 1, "pinyin": "shù", "en_def": "number; to count", "pos": "n"},
        "量": {"hsk": 2, "pinyin": "liàng", "en_def": "quantity; amount", "pos": "n"},
        "度": {"hsk": 0, "pinyin": "dù", "en_def": "degree; extent", "pos": "n"},
        "线": {"hsk": 0, "pinyin": "xiàn", "en_def": "line; thread", "pos": "n"},
        "面": {"hsk": 1, "pinyin": "miàn", "en_def": "face; surface", "pos": "n"},
        "点": {"hsk": 1, "pinyin": "diǎn", "en_def": "point; dot", "pos": "n"},
    }

    # Merge common words into vocab (don't override existing HSK entries)
    for word, info in common_words.items():
        if word not in vocab:
            info["pinyin"] = normalize_pinyin(info.get("pinyin", ""))
            vocab[word] = info

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


def collect_new_words(essay_text, vocab, user_level):
    """Collect new words: HSK level >= user's level.

    Definition (unified): if the user is at HSK5, then HSK5 and HSK6 words
    are ALL new words. Words BELOW the user's level are NEVER new words.
    """
    try:
        user_level = int(user_level)
    except (TypeError, ValueError):
        user_level = 6
    if user_level < 1:
        user_level = 1
    if user_level > 6:
        user_level = 6

    segments = segment_text(essay_text, vocab)
    found = {}
    order = []
    for word, is_punct in segments:
        if is_punct or not word.strip():
            continue
        info = vocab.get(word, {})
        hsk = info.get("hsk", 0)
        if hsk >= user_level and hsk > 0 and word not in found:
            example = extract_example_sentence(essay_text, word)
            found[word] = {
                "word": word,
                "pinyin": normalize_pinyin(info.get("pinyin", "")),
                "hsk": hsk,
                "pos": info.get("pos", ""),
                "en_def": info.get("en_def", ""),
                "example": example,
            }
            order.append(word)

    words = sorted(found.values(), key=lambda x: (x["hsk"], order.index(x["word"])))
    return words


def generate_new_words_html(new_words, user_level):
    """Render the New Words section HTML."""
    try:
        level_int = int(user_level)
    except (TypeError, ValueError):
        level_int = 6

    if not new_words:
        return '''<div class="nw-empty">No new words found — every word in this essay is below HSK %d. Great job!</div>''' % level_int

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

    Restores the real writing scenario (方格作文纸). Each paragraph starts with
    two blank cells (首行空两格). Punctuation also occupies one cell.
    """
    paras = []
    for raw in essay_text.split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        cells = []
        for ch in raw:
            if ch == " ":
                continue
            cells.append(f'<span class="gc">{esc(ch)}</span>')
        if cells:
            indent = '<span class="gc blank"></span><span class="gc blank"></span>'
            paras.append(f'<p class="gpara">{indent}{"".join(cells)}</p>')
    paras_html = "\n".join(paras)
    return f'''
  <div class="paper-head">{esc(title)}</div>
  <div class="paper-body">
{paras_html}
  </div>'''


def generate_html(essay_text, title, hsk_level, source_url, word_count, good_expressions, vocab):
    """Generate the complete HTML page."""
    # Build highlight set from good expressions
    highlight_words = set()
    for expr in good_expressions:
        expr_text = expr.get("expression", "")
        if expr_text:
            highlight_words.add(expr_text)

    # Segment and render essay
    segments = segment_text(essay_text, vocab)

    # Split into paragraphs by newlines or double punctuation
    paragraphs = []
    current_para = []
    for word, is_punct in segments:
        if word == "\n" or (is_punct and word.strip() == ""):
            if current_para:
                paragraphs.append(current_para)
                current_para = []
        else:
            current_para.append((word, is_punct))
    if current_para:
        paragraphs.append(current_para)

    # If no paragraph breaks, try splitting by 。and！and？
    if len(paragraphs) <= 1:
        paragraphs = []
        current_para = []
        for word, is_punct in segments:
            current_para.append((word, is_punct))
            if is_punct and word.strip() in ("。", "！", "？", "!?", "..."):
                paragraphs.append(current_para)
                current_para = []
        if current_para:
            paragraphs.append(current_para)

    essay_html_parts = []
    for para in paragraphs:
        parts = []
        for word, is_punct in para:
            if is_punct:
                parts.append(render_punctuation(word))
            else:
                parts.append(render_word(word, vocab, highlight_words))
        essay_html_parts.append('<p class="para">' + "".join(parts) + '</p>')
    essay_html = "\n".join(essay_html_parts)

    # Build composition-paper view (方格/横线作文纸, KaiTi font, 首行空两格)
    paper_html = build_paper_view(essay_text, title)

    # Collect new words (HSK level >= user's level) and render the section
    new_words = collect_new_words(essay_text, vocab, hsk_level)
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

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_esc} - Essay Display</title>
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
  .para {{ margin-bottom: 22px; text-align: justify; line-height: 1.5; text-indent: 2em; }}
  .w {{
    display: inline-flex; flex-direction: column; align-items: center;
    vertical-align: top; margin: 0 1px 8px; padding: 4px 5px 3px;
    border-radius: 7px; position: relative; transition: all 0.2s ease;
    border-bottom: 3px solid var(--c, transparent); background: var(--bg, transparent);
  }}
  .w:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 10; }}
  .py {{
    font-size: 11px; font-weight: 500; color: var(--c, #999);
    font-family: "Georgia", "Times New Roman", serif; line-height: 1.1;
    margin-bottom: 2px; min-height: 13px; text-align: center;
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
    border-bottom-color: #ffc107; border-bottom-width: 4px;
    box-shadow: 0 2px 8px rgba(255,193,7,0.2);
  }}
  .w.hl .cz {{ color: #e65100; }}
  .star {{ position: absolute; top: -8px; right: -4px; font-size: 13px; color: #ff9800; text-shadow: 0 1px 2px rgba(255,152,0,0.3); }}
  .punct {{ font-size: 20px; color: #555; font-weight: 600; vertical-align: top; display: inline-block; margin: 0 1px; padding-top: 18px; }}
  .view-bar {{ display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-bottom: 24px; }}
  .view-btn {{
    border: 2px solid rgba(255,255,255,0.7); background: rgba(255,255,255,0.15);
    color: white; font-size: 14px; font-weight: 600; padding: 9px 20px;
    border-radius: 22px; cursor: pointer; transition: all 0.2s ease;
  }}
  .view-btn:hover {{ background: rgba(255,255,255,0.32); }}
  .view-btn.active {{ background: white; color: #5b4b8a; border-color: white; box-shadow: 0 4px 14px rgba(0,0,0,0.18); }}
  .paper {{ background: white; border-radius: 20px; padding: 34px 30px 40px; box-shadow: 0 8px 32px rgba(0,0,0,0.12); margin-bottom: 32px; }}
  .paper-head {{
    text-align: center; font-size: 28px; font-weight: 700; color: #1a1a2e;
    font-family: "KaiTi", "楷体", "STKaiti", "Kaiti SC", "TW-Kai", serif;
    margin-bottom: 24px; letter-spacing: 4px;
  }}
  .gc {{ font-family: "KaiTi", "楷体", "STKaiti", "Kaiti SC", "TW-Kai", serif; font-size: 26px; color: #1a1a2e; }}
  .gpara {{ margin: 0; line-height: 34px; }}
  .paper.grid .paper-body {{
    border: 2px solid #d99a9f;
    background-image:
      linear-gradient(to right, #f2c6ca 1px, transparent 1px),
      linear-gradient(to bottom, #f2c6ca 1px, transparent 1px);
    background-size: 34px 34px;
    padding: 0;
  }}
  .paper.grid .gc {{ display: inline-flex; width: 34px; height: 34px; align-items: center; justify-content: center; }}
  .paper.grid .gc.blank {{ visibility: hidden; }}
  .paper.lines .paper-body {{
    border: 2px solid #b8c4d9;
    background-image: linear-gradient(to bottom, #b8c4d9 1px, transparent 1px);
    background-size: 100% 34px;
    padding: 0;
  }}
  .paper.lines .gpara {{ text-indent: 2em; }}
  .paper.lines .gc.blank {{ display: none; }}
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
    .w {{ padding: 3px 3px 2px; margin: 0 0px 6px; }}
    .py {{ font-size: 9px; min-height: 11px; }}
    .cz {{ font-size: 17px; }}
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
    <h1>{title_esc}</h1>
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
    <div class="expr-title">📚 生词表 | New Words (HSK {level_label} &amp; above)</div>
    <div class="nw-note">生词定义：你所选等级及以上的词汇。例句均取自本篇原文。 (New words are words at your HSK level and above. All examples are taken from this essay.)</div>
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
    parser.add_argument("--title", default="Essay", help="Essay title")
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
