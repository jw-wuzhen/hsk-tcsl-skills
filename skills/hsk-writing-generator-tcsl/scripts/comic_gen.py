#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看图作文四格漫画生成器 —— 千问（DashScope 通义万相）文生图 API（纯标准库）。

看图作文的**可选增强**图片路径（需配置密钥）：用千问文生图生成高质量卡通四格漫画。
主流程不依赖本脚本（默认走平台图像生成工具 → 本地 comic_render.py SVG 保底）。
密钥解析链（依次尝试第一个可用的）：
  1. 调用参数 --api-key
  2. 环境变量 DASHSCOPE_API_KEY / QWEN_API_KEY
  3. 技能包根目录 api_key.txt（推荐，随包部署，把密钥写进去）
  4. 用户主目录 ~/.dashscope_api_key / ~/.config/dashscope/api_key

两种模式：
  --mode single   一次生成一张 2x2 四格漫画（默认，1 次调用，快）
  --mode panels   逐格生成 4 张独立图片（4 次调用，每张画质更好）

失败/无密钥/无网络时：脚本输出明确的错误 JSON，主模型应**立即降级**——
  先试平台自带图像生成工具，再试本地 comic_render.py（必成功）。
绝不阻塞输出。

用法:
  python3 comic_gen.py --panels-json /mnt/user-data/workspace/panels.json \
      --output-dir /mnt/user-data/outputs --title "助人为乐" --mode single
  python3 comic_gen.py --panels-json panels.json --mode panels \
      --api-key sk-xxxx

panels.json 格式（同 comic_render.py，字段见 SKILL.md Feature 3 Step 1）:
[
  {"scene":"学校操场","props":"跑道、观众席","characters":"李明、同学们","look":"穿红色短袖T恤、黑色短发、圆脸的男孩",
   "action":"运动会上李明跑在最前面","mood":"开心","dialogue":"加油！","detail":"他回头看向身后"},
  {"scene":"操场跑道","props":"红色跑道","characters":"李明","action":"李明不小心摔倒了","mood":"难过","detail":"膝盖擦破，坐在地上"},
  {"scene":"操场","props":"跑道、草坪","characters":"同学们","action":"同学们把李明扶起来","mood":"关心","detail":"两个同学一人扶一边"},
  {"scene":"终点","props":"终点线","characters":"李明、同学们","action":"大家一起跑向终点","mood":"开心","detail":"手拉手冲过终点线"}
]
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = os.environ.get("QWEN_API_BASE", "https://dashscope.aliyuncs.com")
MODEL = os.environ.get("QWEN_IMG_MODEL", "wanx2.1-t2i-turbo")
SIZE = "1024*1024"
STYLE = "扁平卡通插画，儿童绘本风格，色彩明快，线条简洁，画面干净，适合HSK中文教学。画面中不要出现任何文字、字母或数字；车厢、街道、商店等场景里的标牌一律留白或模糊处理，不要画有字的标识牌。"


def _valid_key(v):
    v = (v or "").strip()
    if not v or v.startswith("#"):
        return False
    if "在此粘贴" in v or "xxxx" in v.lower() or "your_key" in v.lower() or "sk-xxx" in v.lower():
        return False
    return True


def resolve_api_key(explicit=""):
    if explicit and explicit.strip():
        return explicit.strip()
    for env in ("DASHSCOPE_API_KEY", "QWEN_API_KEY", "DASHSCOPE_AGENT_API_KEY"):
        if os.environ.get(env, "").strip():
            return os.environ.get(env).strip()
    # 技能包根目录 api_key.txt（脚本上级目录）
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("api_key.txt", "dashscope_api_key.txt", "qwen_api_key.txt"):
        path = os.path.join(pkg_dir, name)
        try:
            if os.path.exists(path):
                lines = [ln.strip() for ln in open(path, encoding="utf-8").read().splitlines() if _valid_key(ln)]
                if lines:
                    return lines[0]
        except Exception:
            continue
    for path in (os.path.expanduser("~/.dashscope_api_key"),
                 os.path.expanduser("~/.config/dashscope/api_key")):
        try:
            if os.path.exists(path):
                lines = [ln.strip() for ln in open(path, encoding="utf-8").read().splitlines() if _valid_key(ln)]
                if lines:
                    return lines[0]
        except Exception:
            continue
    return ""


def _request_json(url, method="GET", payload=None, headers=None, timeout=60):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gen_one(api_key, prompt, retries=2):
    """生成一张图，返回 {"success":True,"image":bytes} 或 {"success":False,"error":...}"""
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    submit_url = "%s/api/v1/services/aigc/text2image/image-synthesis" % BASE_URL
    payload = {"model": MODEL, "input": {"prompt": prompt}, "parameters": {"size": SIZE, "n": 1}}
    for attempt in range(retries + 1):
        try:
            data = _request_json(submit_url, "POST", payload, headers, timeout=60)
            task_id = (data.get("output", {}) or {}).get("task_id", "")
            if not task_id:
                msg = data.get("message") or data.get("code") or "未返回任务ID"
                if attempt < retries:
                    time.sleep(3)
                    continue
                return {"success": False, "error": "提交失败：%s" % msg}
            deadline = time.time() + 180
            last = ""
            while time.time() < deadline:
                q = _request_json("%s/api/v1/tasks/%s" % (BASE_URL, task_id), "GET",
                                  headers={"Authorization": "Bearer " + api_key}, timeout=30)
                out = q.get("output", {}) or {}
                last = out.get("task_status", "")
                if last == "SUCCEEDED":
                    results = out.get("results", []) or []
                    if not results:
                        return {"success": False, "error": "生成成功但无结果URL"}
                    img_url = results[0].get("url", "")
                    with urllib.request.urlopen(img_url, timeout=60) as resp:
                        img = resp.read()
                    if img:
                        return {"success": True, "image": img}
                    return {"success": False, "error": "图片下载失败"}
                if last in ("FAILED", "CANCELED"):
                    msg = out.get("message", "") or q.get("message", "") or last
                    if attempt < retries:
                        time.sleep(3)
                        break
                    return {"success": False, "error": "生成失败：%s" % msg}
                time.sleep(4)
            if attempt < retries:
                continue
            return {"success": False, "error": "生成超时（最后状态：%s）" % last}
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            if "AccessDenied" in body or "Unpurchased" in body or "not enabled" in body:
                return {"success": False, "error": "千问模型未开通：请在阿里云百炼控制台开通通义万相文生图模型（如 wanx2.1-t2i-turbo）后重试。"}
            if attempt < retries:
                time.sleep(3)
                continue
            return {"success": False, "error": "API 请求失败（HTTP %d）：%s" % (e.code, body)}
        except Exception as e:
            if attempt < retries:
                time.sleep(3)
                continue
            return {"success": False, "error": "请求异常：%s" % str(e)}
    return {"success": False, "error": "重试后仍失败"}


def first_look(panels):
    """取主角外貌描述（四格共用，保证人物一致）；没有则返回空串"""
    for p in panels:
        if (p.get("look") or "").strip():
            return p["look"].strip()
    return ""


def build_prompt(panel, with_people=True, look=""):
    parts = []
    if look:
        parts.append("主角外貌与其余画格完全一致：%s" % look)
    if panel.get("scene"):
        props = panel.get("props") or ""
        parts.append(panel["scene"] + ("，有%s" % props if props else ""))
    if panel.get("action"):
        parts.append(panel["action"])
    elif panel.get("characters") and with_people:
        parts.append("人物：%s" % panel["characters"])
    if panel.get("mood"):
        parts.append("情绪：%s" % panel["mood"])
    if panel.get("detail"):
        parts.append("细节：%s" % panel["detail"])
    return "，".join(parts) + "。" + STYLE


def build_single_prompt(panels):
    """2×2 单图四格：叙事句写法——场景融入动作句（谁+在什么场景+做什么），
    强连贯（同一主角、因果推进），场景占画面主体，禁止文字。"""
    look = first_look(panels)
    lines = [
        "四格漫画，2×2 布局，四个画格按左上（图1）、右上（图2）、左下（图3）、右下（图4）排列。",
    ]
    if look:
        lines.append("四格中的主角是同一个人，在每一格中都必须保持完全一致的外貌、发型和服装：%s。" % look)
    else:
        lines.append("四格中的主角是同一个人，在每一格中必须保持相同的外貌、发型和服装。")
    lines.append("这是同一个故事的连续四格漫画：图1交代起因，图2、图3推动情节，图4是结果，情节因果连贯。")
    lines.append("每格要画成全景或中景，让读者一眼看清人物在什么环境里做什么事；场景元素要清晰可辨（如公交车车窗、扶手、座椅）；人物画全身或大半身，不要特写；四格之间用清晰分隔线隔开。")
    for i, p in enumerate(panels[:4], 1):
        scene = p.get("scene") or ""
        props = p.get("props") or ""
        action = p.get("action") or ""
        mood = p.get("mood") or ""
        detail = p.get("detail") or ""
        bits = []
        if scene:
            bits.append(scene + ("，有%s" % props if props else ""))
        if action:
            bits.append(action)
        if mood:
            bits.append("情绪：" + mood)
        if detail:
            bits.append("细节：" + detail)
        lines.append("图%d：%s。" % (i, "；".join(bits)))
    lines.append("画面要求：卡通儿童绘本风格，色彩明快，线条简洁；画面中不要出现任何文字、字母、数字或对话框；车厢、街道、商店等场景里的标牌一律留白或模糊处理，不要画有字的标识牌。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="四格漫画生成器（千问通义万相 API）")
    ap.add_argument("--panels-json", required=True, help="四格故事 JSON 路径（同 comic_render.py 格式）")
    ap.add_argument("--output-dir", default="/mnt/user-data/outputs", help="图片输出目录")
    ap.add_argument("--title", default="看图作文", help="漫画标题（用于文件名）")
    ap.add_argument("--mode", choices=["single", "panels"], default="single", help="single=一张2x2四格（默认）；panels=四张独立图")
    ap.add_argument("--api-key", default="", help="千问 DashScope API 密钥（可选，自动解析链兜底）")
    args = ap.parse_args()

    with open(args.panels_json, encoding="utf-8") as f:
        panels = json.load(f)
    if not isinstance(panels, list) or len(panels) < 4:
        print(json.dumps({"success": False, "error": "panels JSON 必须是至少4格数组"}, ensure_ascii=False))
        sys.exit(1)
    panels = panels[:4]

    api_key = resolve_api_key(args.api_key)
    if not api_key:
        print(json.dumps({"success": False, "error": "未找到千问 API 密钥。请任选一种：①把密钥写入技能包内 api_key.txt（推荐）；②设置环境变量 DASHSCOPE_API_KEY；③调用时传 --api-key。"}, ensure_ascii=False))
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    safe_title = re_safe(args.title)
    paths = []

    if args.mode == "single":
        r = gen_one(api_key, build_single_prompt(panels))
        if not r["success"]:
            print(json.dumps(r, ensure_ascii=False))
            sys.exit(1)
        out = os.path.join(args.output_dir, "comic_%s.png" % safe_title)
        with open(out, "wb") as f:
            f.write(r["image"])
        print(json.dumps({"success": True, "paths": [out], "mode": "single"}, ensure_ascii=False))
    else:
        look = first_look(panels)
        for i, p in enumerate(panels, 1):
            r = gen_one(api_key, build_prompt(p, look=look))
            if not r["success"]:
                print(json.dumps({"success": False, "error": "第%d格生成失败：%s" % (i, r["error"]), "completed": paths}, ensure_ascii=False))
                sys.exit(1)
            out = os.path.join(args.output_dir, "comic_%s_p%d.png" % (safe_title, i))
            with open(out, "wb") as f:
                f.write(r["image"])
            paths.append(out)
        print(json.dumps({"success": True, "paths": paths, "mode": "panels"}, ensure_ascii=False))


def re_safe(t):
    import re
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", t or "看图作文")


if __name__ == "__main__":
    main()
