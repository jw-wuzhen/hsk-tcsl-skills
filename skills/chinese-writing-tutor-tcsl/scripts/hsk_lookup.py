#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HSK 词汇查词脚本：输入词语列表，在 HSK1-6 词汇表中查找并返回匹配条目。"""

import csv
import json
import os
import sys
import argparse


def load_all_hsk(ref_dir):
    vocab_dir = os.path.join(ref_dir, "hsk_vocabulary")
    all_entries = {}

    for level in range(1, 7):
        csv_path = os.path.join(vocab_dir, "HSK{}.csv".format(level))
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = (row.get("简体") or "").strip()
                if not word:
                    continue
                entry = {
                    "word": word,
                    "level": int(row.get("等级", level)),
                    "traditional": (row.get("繁体") or "").strip(),
                    "pinyin": (row.get("拼音") or "").strip(),
                    "num_pinyin": (row.get("数字拼音") or "").strip(),
                    "pos": (row.get("词性") or "").strip(),
                    "cn_def": (row.get("中文释义") or "").strip(),
                    "en_def": (row.get("英文释义") or "").strip(),
                    "measure": (row.get("量词") or "").strip(),
                    "radical": (row.get("部首") or "").strip(),
                }
                if word not in all_entries:
                    all_entries[word] = []
                all_entries[word].append(entry)

    return all_entries


def lookup_words(words, all_entries):
    found = []
    not_found = []
    for w in words:
        w = w.strip()
        if not w:
            continue
        if w in all_entries:
            found.extend(all_entries[w])
        else:
            not_found.append(w)
    return found, not_found


def main():
    parser = argparse.ArgumentParser(description="HSK 词汇查词")
    parser.add_argument("--words", required=True, help="逗号分隔的词语列表，如: 我,在,今天,遇到")
    parser.add_argument("--ref-dir", default=None, help="reference 目录路径（默认自动推断）")
    args = parser.parse_args()

    if args.ref_dir:
        ref_dir = args.ref_dir
    else:
        ref_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference")

    all_entries = load_all_hsk(ref_dir)

    words = [w.strip() for w in args.words.split(",") if w.strip()]
    found, not_found = lookup_words(words, all_entries)

    output = {
        "found": found,
        "not_found": not_found,
        "total_found": len(found),
        "total_not_found": len(not_found),
        "total_loaded": len(all_entries),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
