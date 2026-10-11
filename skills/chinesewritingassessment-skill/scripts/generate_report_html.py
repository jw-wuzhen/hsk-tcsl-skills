#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成中文写作评估 HTML 报告。

用法：
    python3 generate_report_html.py --text "作文文本" --output report.html
    echo "作文文本" | python3 generate_report_html.py --output report.html
    python3 generate_report_html.py --input essay.txt --result result.json --output report.html

该脚本：
1. 读取作文文本
2. 调用 essay_assessor 进行评估（或使用已有的评估结果 JSON）
3. 调用 html_material 生成自包含 HTML 报告
4. 输出到指定文件
"""
import argparse
import json
import os
import sys

# 确保能 import 同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from assess_essay import generate_skill_result, load_hsk_words
from html_material import build_html_material


def main():
    parser = argparse.ArgumentParser(description="生成中文写作评估 HTML 报告")
    parser.add_argument("--text", type=str, default=None, help="作文文本（直接传入）")
    parser.add_argument("--input", type=str, default=None, help="从文件读取作文文本")
    parser.add_argument("--result", type=str, default=None, help="已有的评估结果 JSON 文件（不提供则自动评估）")
    parser.add_argument("--output", type=str, required=True, help="输出 HTML 文件路径")
    parser.add_argument("--hsk-level", type=str, default="HSK3", help="目标 HSK 等级")
    parser.add_argument("--task-type", type=str, default="HSK写作", help="写作任务类型")
    parser.add_argument("--native-language", type=str, default="英语", help="学习者母语")
    parser.add_argument("--title", type=str, default="中文写作评估报告", help="HTML 报告标题")
    args = parser.parse_args()

    # 获取作文文本
    if args.text:
        text = args.text
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        parser.error("请通过 --text、--input 或 stdin 提供作文文本")

    text = text.strip()
    if not text:
        parser.error("作文文本为空")

    # 获取评估结果
    if args.result:
        with open(args.result, "r", encoding="utf-8") as f:
            result = json.load(f)
    else:
        result = generate_skill_result(
            text,
            target_level=args.hsk_level,
            task_type=args.task_type,
            learner_native_language=args.native_language,
        )

    # 生成 HTML
    hsk_words = result.get("_hsk_words", [])
    # 如果结果里没有 hsk_words（从 JSON 读取时），重新加载
    if not hsk_words:
        hsk_words = load_hsk_words()

    issues = result.get("part1_grammar_errors", [])
    overall = result.get("part3_overall_evaluation", {})
    attribution = result.get("part2_attribution_report", [])
    reference_sources = result.get("reference_sources", None)
    html_content = build_html_material(text, hsk_words, issues, overall, attribution, reference_sources)

    # 写入文件
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML 报告已生成: {args.output}", file=sys.stderr)
    print(f"文件大小: {os.path.getsize(args.output)} 字节", file=sys.stderr)


if __name__ == "__main__":
    main()
