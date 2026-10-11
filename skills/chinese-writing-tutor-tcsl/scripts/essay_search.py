#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分级范文库检索（能力三配套脚本，纯标准库）。

用法:
  python essay_search.py --level hsk5 --topic 网络
  python essay_search.py --level hsk4 --topic 学习 --topic 经历 --genre 记叙文 --top 3
  python essay_search.py --level hsk5 --push --since "2026-08-24 19:20"            # 首推（T0=会话起点）
  python essay_search.py --level hsk5 --push --since "2026-08-24 19:20" --now "2026-08-24 21:20" --exclude-title X

检索评分: 等级匹配(0-3) + 话题命中(每词最高3) + 体裁匹配(1)。
推送模式(--push): 用户相对时间轮换——slot = 距 T0(--since) 的整小时数，
同一小时重复触发结果稳定（幂等），跨小时自动换篇；候选=同级+高一级(i+1)，
--now 指定触发时刻（默认真实现在，用于模拟），--exclude-title 排除已推篇目。
结果输出到 stdout（JSON）；调试信息走 stderr。
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ESSAY_DIR = Path(__file__).resolve().parent.parent / "reference" / "model_essays"
LEVEL_NUM = {"hsk1": 1, "hsk2": 2, "hsk3": 3, "hsk4": 4, "hsk5": 5, "hsk6": 6}


def parse_front_matter(text):
    """解析 markdown 头部 '---' 之间的 key: value 元数据，支持 [a, b] 列表。"""
    meta = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([a-zA-Z_]+)\s*:\s*(.*)$", line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            val = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
        meta[key] = val
    return meta


def load_essays():
    essays = []
    if not ESSAY_DIR.exists():
        return essays
    for path in sorted(ESSAY_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta = parse_front_matter(text)
        if not meta.get("level") or not meta.get("title"):
            print("跳过缺少元数据的文件: %s" % path.name, file=sys.stderr)
            continue
        essays.append({"path": str(path.relative_to(ESSAY_DIR.parent.parent)), "meta": meta, "text": text})
    return essays


def level_score(essay_level, query_level):
    diff = LEVEL_NUM[essay_level] - LEVEL_NUM[query_level]
    if diff == 0:
        return 3.0, "等级完全匹配"
    if diff == 1:
        return 2.0, "略高于学生等级（i+1 拔高推荐）"
    if diff == -1:
        return 1.0, "略低于学生等级（巩固用）"
    if diff <= -2:
        return None, "低于学生等级2级以上，不推荐"
    return 0.5, "高于学生等级2级（难度较大）"


def topic_score(essay, topic):
    meta = essay["meta"]
    score, reasons = 0, []
    tags = meta.get("topics", [])
    if isinstance(tags, str):
        tags = [tags]
    for t in tags:
        if topic in t or t in topic:
            score += 2
            reasons.append("话题标签命中「%s」" % t)
            break
    title = meta.get("title", "")
    if topic in title:
        score += 1
        reasons.append("题目包含「%s」" % topic)
    return score, reasons


def body(e):
    """返回范文正文（剥离 frontmatter 元数据块）。"""
    text = e["text"]
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def search(level, topics, genre, top):
    essays = load_essays()
    if not essays:
        return {"query": {"level": level, "topics": topics, "genre": genre},
                "results": [], "note": "范文库为空或路径不存在: %s" % ESSAY_DIR}

    results = []
    for e in essays:
        elevel = str(e["meta"].get("level", "")).lower()
        if elevel not in LEVEL_NUM:
            continue
        lscore, lreason = level_score(elevel, level)
        if lscore is None:
            continue
        score, reasons = lscore, [lreason]
        for t in topics:
            ts, treasons = topic_score(e, t)
            score += ts
            reasons += treasons
        if genre:
            egenre = str(e["meta"].get("genre", ""))
            if genre in egenre or egenre in genre:
                score += 1
                reasons.append("体裁匹配「%s」" % egenre)
        results.append({
            "file": e["path"],
            "score": round(score, 1),
            "level": elevel,
            "title": e["meta"].get("title", ""),
            "genre": e["meta"].get("genre", ""),
            "topics": e["meta"].get("topics", []),
            "words": e["meta"].get("words", ""),
            "highlights": e["meta"].get("highlights", []),
            "reason": "；".join(dict.fromkeys(reasons)),
        })

    results.sort(key=lambda r: (-r["score"], r["title"]))
    results = results[:top]
    if results:
        by_title = {e["meta"].get("title", ""): e for e in essays}
        results[0]["content"] = body(by_title[results[0]["title"]])
    return {"query": {"level": level, "topics": topics, "genre": genre},
            "results": results}


def brief(e):
    return {
        "file": e["path"],
        "level": str(e["meta"].get("level", "")).lower(),
        "title": e["meta"].get("title", ""),
        "genre": e["meta"].get("genre", ""),
        "topics": e["meta"].get("topics", []),
        "words": e["meta"].get("words", ""),
        "highlights": e["meta"].get("highlights", []),
        "content": body(e),
    }


def _parse_at(s):
    if not s:
        return datetime.datetime.now()
    try:
        return datetime.datetime.fromisoformat(s.replace(" ", "T"))
    except ValueError:
        try:
            return datetime.datetime.fromisoformat(s.replace(" ", "T") + "T00:00")
        except ValueError:
            return None


def push(level, topics, genre, since_str, now_str, excludes):
    essays = load_essays()
    if not essays:
        return {"push": None, "note": "范文库为空或路径不存在: %s" % ESSAY_DIR}

    since = _parse_at(since_str) or datetime.datetime.now()
    now = _parse_at(now_str) or datetime.datetime.now()
    if since_str and _parse_at(since_str) is None:
        return {"push": None, "note": "时间格式无效: %s（应为 YYYY-MM-DD HH:MM）" % since_str}
    if now_str and _parse_at(now_str) is None:
        return {"push": None, "note": "时间格式无效: %s（应为 YYYY-MM-DD HH:MM）" % now_str}

    scored = []
    for e in essays:
        elevel = str(e["meta"].get("level", "")).lower()
        if elevel not in LEVEL_NUM:
            continue
        diff = LEVEL_NUM[elevel] - LEVEL_NUM[level]
        if diff not in (0, 1):
            continue
        score = -diff
        for t in topics:
            ts, _ = topic_score(e, t)
            score += ts
        if genre:
            egenre = str(e["meta"].get("genre", ""))
            if genre in egenre or egenre in genre:
                score += 1
        scored.append((score, e))

    if not scored:
        return {"push": None, "note": "无符合条件的候选范文（等级 %s）" % level}

    slot = max(0, int((now - since).total_seconds() // 3600))

    scored.sort(key=lambda se: (-se[0], se[1]["meta"].get("title", "")))
    ordered = [e for _, e in scored]
    pool = [e for e in ordered if e["meta"].get("title") not in excludes]
    exhausted = not pool
    if exhausted:
        pool = ordered

    idx = slot % len(pool)
    chosen = pool[idx]
    alternates = [e for e in pool if e is not chosen][:2]

    return {
        "push": {
            "since": since.strftime("%Y-%m-%d %H:%M"),
            "at": now.strftime("%Y-%m-%d %H:%M"),
            "slot": slot,
            "level": level,
            "rotation": "距首推第 %d 小时，池内第 %d/%d 篇（同一小时重复触发结果稳定）" % (slot, idx + 1, len(pool)),
            "essay": brief(chosen),
            "alternates": [brief(a) for a in alternates],
        },
        "note": "全部候选均已推送过，本次重复推送" if exhausted else "",
    }


def main():
    ap = argparse.ArgumentParser(description="分级范文检索")
    ap.add_argument("--level", required=True, help="学生 HSK 等级 hsk1-hsk6")
    ap.add_argument("--topic", action="append", default=[], help="话题关键词，可多次使用")
    ap.add_argument("--genre", default=None, help="体裁（记叙文/议论文/书信）")
    ap.add_argument("--top", type=int, default=3, help="返回数量，默认 3")
    ap.add_argument("--push", action="store_true", help="推送模式：按距 T0 的小时数轮换选 1 篇")
    ap.add_argument("--since", default=None, help="会话起点 T0（YYYY-MM-DD HH:MM），首推时传当前时刻")
    ap.add_argument("--now", default=None, help="本次触发时刻（YYYY-MM-DD HH:MM），默认真实现在，用于模拟")
    ap.add_argument("--exclude-title", action="append", default=[], help="已推送过的题目，排除，可多次使用")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出（默认即 JSON，保留参数兼容）")
    args = ap.parse_args()

    level = args.level.lower()
    if level not in LEVEL_NUM:
        print("错误: 无效等级 %s（可选 hsk1-hsk6）" % args.level, file=sys.stderr)
        sys.exit(2)

    if args.push:
        result = push(level, args.topic, args.genre, args.since, args.now, args.exclude_title)
    else:
        result = search(level, args.topic, args.genre, args.top)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
