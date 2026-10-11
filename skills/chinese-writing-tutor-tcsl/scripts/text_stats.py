#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文文本统计与 HSK 简化难度预检（能力二配套脚本，纯标准库）。

用法:
  python text_stats.py --text "要分析的文本" --level hsk4 --json
  python text_stats.py --text "要分析的文本" --level hsk3
  echo "要分析的文本" | python text_stats.py - --level hsk3 --json

--text 直接传原文（推荐，无需临时文件）；也可传文本文件路径或 - 表示 stdin。
结果输出到 stdout（--json 为 JSON，否则人读格式）；调试信息走 stderr。
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

MARKERS_PATH = Path(__file__).resolve().parent / "vocab_markers.json"
SENT_SPLIT = re.compile(r"[。！？；!?;]+")
PUNCT = re.compile(r"[\s\u201c\u201d\u2018\u2019\"'，。！？；：、,.!?;:·—…（）()《》<>【\[\]]")


def load_markers():
    with open(MARKERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def split_sentences(text):
    parts = [p.strip() for p in SENT_SPLIT.split(text) if p.strip()]
    return parts


def sentence_length(sent):
    return len(PUNCT.sub("", sent))


def find_hits(sent, patterns):
    hits = []
    for p in patterns:
        if re.search(p, sent):
            hits.append(p)
    return hits


def analyze(text, level, markers):
    sentences = split_sentences(text)
    limit = markers["length_limits"].get(level)
    if limit is None:
        raise ValueError("无效等级: %s（可选 hsk1-hsk6）" % level)

    lens = [sentence_length(s) for s in sentences]
    total_chars = sum(lens)
    avg = round(total_chars / len(lens), 1) if lens else 0
    long_sents = [(s, l) for s, l in zip(sentences, lens) if l > limit]

    conj_groups = markers["complex_conjunctions"]
    allowed_group = {"hsk3": "hsk4_plus", "hsk4": "hsk5_plus", "hsk5": None, "hsk6": None}
    forbidden_groups = []
    grp = allowed_group.get(level)
    if grp:
        forbidden_groups.append((grp, conj_groups[grp]))
    if level in ("hsk3", "hsk4"):
        forbidden_groups.append(("hsk5_plus", conj_groups["hsk5_plus"]))

    formal_hits, conj_hits, struct_hits, chengyu_hits = [], [], [], []
    for s in sentences:
        formal_hits += [(s, m) for m in find_hits(s, markers["formal_markers"])]
        for name, pats in forbidden_groups:
            conj_hits += [(s, p, name) for p in find_hits(s, pats)]
        for name, pats in markers["structure_patterns"].items():
            struct_hits += [(s, p, name) for p in find_hits(s, pats)]
        chengyu_hits += [(s, m) for m in find_hits(s, markers["chengyu_sample"])]

    hot = []
    for s, l in long_sents:
        hot.append({"sentence": s, "length": l, "reason": "超过%s句长上限%d字" % (level, limit)})
    for s, p, g in conj_hits:
        hot.append({"sentence": s, "pattern": p, "reason": "含该级慎用关联句式（%s）" % g})
    for s, m in formal_hits:
        hot.append({"sentence": s, "pattern": m, "reason": "含书面语/文言标记词"})
    for s, m in chengyu_hits:
        hot.append({"sentence": s, "pattern": m, "reason": "含四字词语（HSK6 级表达）"})

    return {
        "level": level,
        "sentence_count": len(sentences),
        "total_chars": total_chars,
        "avg_sentence_length": avg,
        "max_sentence_length": max(lens) if lens else 0,
        "length_limit": limit,
        "long_sentence_ratio": round(len(long_sents) / len(sentences), 2) if sentences else 0,
        "formal_marker_count": len(formal_hits),
        "complex_conjunction_count": len(conj_hits),
        "structure_pattern_count": len(struct_hits),
        "hot_sentences": hot[:20],
    }


def human_report(r):
    lines = [
        "目标等级: %s（句长上限 %d 字）" % (r["level"], r["length_limit"]),
        "句数: %d｜总字数: %d｜平均句长: %s｜最长句: %d 字" % (
            r["sentence_count"], r["total_chars"], r["avg_sentence_length"], r["max_sentence_length"]),
        "长句占比: %d%%｜书面语标记: %d｜复杂关联句式: %d｜特殊句式: %d" % (
            int(r["long_sentence_ratio"] * 100), r["formal_marker_count"],
            r["complex_conjunction_count"], r["structure_pattern_count"]),
        "",
        "重点简化句子:",
    ]
    for h in r["hot_sentences"]:
        lines.append("  - [%s] %s" % (h["reason"], h["sentence"]))
    if not r["hot_sentences"]:
        lines.append("  （无——句长与标记均已达标）")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="中文文本 HSK 难度预检")
    ap.add_argument("input", nargs="?", default=None, help="文本文件路径，或 - 表示 stdin（与 --text 二选一）")
    ap.add_argument("--text", default=None, help="直接传入原文文本（推荐，避免创建临时文件）")
    ap.add_argument("--level", default="hsk4", help="目标等级 hsk1-hsk6，默认 hsk4")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = ap.parse_args()

    if args.text:
        text = args.text
    elif args.input == "-":
        text = sys.stdin.read()
    elif args.input:
        text = Path(args.input).read_text(encoding="utf-8")
    else:
        print("错误: 未提供输入，用 --text 传原文或传文件路径", file=sys.stderr)
        sys.exit(2)

    try:
        if not text.strip():
            print("错误: 输入为空", file=sys.stderr)
            sys.exit(2)
        result = analyze(text, args.level, load_markers())
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else human_report(result))
    except FileNotFoundError as e:
        print("错误: 文件不存在 %s" % e, file=sys.stderr)
        sys.exit(2)
    except ValueError as e:
        print("错误: %s" % e, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
