#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HSK 词汇查词脚本（2026 新大纲口径）。

读取技能包 reference/ 下的 2026 版 HSK 分级词表 JSON，查询词语等级。
支持两种词表格式：
  1) {"hsk1": ["词1", ...], "hsk2": [...]}   （写作包 hsk_vocab.json）
  2) {"词": 1, ...}                           （对话包 hsk30_words.json）

用法:
  python3 hsk_lookup.py --words "外滩,春联,坚持,帮助"
  python3 hsk_lookup.py --words "词1,词2" --data /path/to/vocab.json

--words 逗号分隔的词语列表；--data 指定词表路径（默认自动推断）。
结果输出为 JSON：{"found": [{"word","level"}...], "not_found": [...], "total_loaded": N}
"""
import argparse
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def default_data_path():
    ref_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference")
    for name in ("hsk_vocab.json", "hsk30_words.json"):
        p = os.path.join(ref_dir, name)
        if os.path.exists(p):
            return p
    return None


def _level_of_key(k):
    """从等级键名解析等级数字，兼容 "hsk1"~"hsk6" 与合并键 "hsk7-9"（取主数字 7）"""
    s = k.lower().replace("hsk", "").strip()
    m = re.match(r"^(\d+)", s)
    return int(m.group(1)) if m else 0


def load_vocab(path):
    """加载词表，统一为 {词: 等级(整数)}"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    word2level = {}
    if isinstance(data, dict):
        # 格式1: {"hsk1": [...], "hsk7-9": [...]} 或 格式2: {"词": 1}
        for k, v in data.items():
            if isinstance(v, list):
                lv = _level_of_key(k)
                for w in v:
                    w = w.strip()
                    if w and (w not in word2level or word2level[w] > lv):
                        word2level[w] = lv
            elif isinstance(v, int):
                w = k.strip()
                if w:
                    # 词条可能含多个变体，用 | 分隔（如 "爸爸|爸"）
                    for part in w.split("|"):
                        part = part.strip()
                        if part and (part not in word2level or word2level[part] > v):
                            word2level[part] = v
    return word2level


def main():
    ap = argparse.ArgumentParser(description="HSK 词汇查词（2026 新大纲）")
    ap.add_argument("--words", required=True, help="逗号分隔的词语列表，如: 我,在,今天,遇到")
    ap.add_argument("--data", default=None, help="词表 JSON 路径（默认自动推断）")
    args = ap.parse_args()

    path = args.data or default_data_path()
    if not path or not os.path.exists(path):
        print(json.dumps({"error": "词表文件缺失，请将 hsk_vocab.json 或 hsk30_words.json 放在 reference/ 目录"}, ensure_ascii=False))
        sys.exit(1)

    word2level = load_vocab(path)
    words = [w.strip() for w in args.words.split(",") if w.strip()]

    found = [{"word": w, "level": word2level[w]} for w in words if w in word2level]
    not_found = [w for w in words if w not in word2level]

    output = {
        "found": found,
        "not_found": not_found,
        "total_found": len(found),
        "total_not_found": len(not_found),
        "total_loaded": len(word2level),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
