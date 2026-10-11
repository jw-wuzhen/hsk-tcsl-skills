#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四格漫画 SVG 渲染器（纯标准库，零网络、零密钥，必成功）。

看图作文的四格漫画示意生成器：根据四格故事 JSON，绘制 2x2 四格漫画 SVG。
每格 = 场景插图（天空/地面 + 按关键词匹配的场景元素 + 简单人物动作）
       + 底部图注（图N + 简短动作描述）。
画面风格为扁平卡通风教学示意图；SVG 可直接在浏览器打开、可打印，
也可被 render_essay_html.py 嵌入 HTML 学习页。

用法:
  python3 comic_render.py --panels-json /mnt/user-data/workspace/panels.json \
      --output /mnt/user-data/outputs/comic_话题.svg --title "助人为乐"
  python3 comic_render.py --panel-1 "..." --panel-2 "..." --panel-3 "..." --panel-4 "..."

panels.json 格式（每格字段均可选）:
[
  {"scene":"学校操场","characters":"李明、同学们","action":"运动会上李明跑在最前面","mood":"开心","dialogue":"加油！"},
  {"scene":"操场跑道","characters":"李明","action":"李明不小心摔倒了","mood":"难过"},
  {"scene":"操场","characters":"同学们","action":"同学们扶起李明","mood":"关心"},
  {"scene":"终点","characters":"李明、同学们","action":"大家一起跑向终点","mood":"开心"}
]
"""
import argparse
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------- 配色
SKY = ["#bfe3f7", "#a8d8f0", "#d6ecf8", "#f7e8c9"]       # 白天/傍晚/阴天/晚上
GRASS = "#8fce7f"
GROUND = "#e8dcc0"
INK = "#2c3e50"
SKIN = ["#f6c99b", "#eab98a", "#d9a06f", "#f2cfa8"]
CLOTH = ["#5dade2", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#3498db"]
PANEL_W, PANEL_H = 480, 400
CAP_H = 46


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def rgb_hex(c, alpha=1.0):
    c = c.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    if alpha >= 1.0:
        return "#%02x%02x%02x" % (r, g, b)
    return "rgba(%d,%d,%d,%.2f)" % (r, g, b, alpha)


# ---------------------------------------------------------------- 场景元素
def has(txt, *kws):
    return any(k in txt for k in kws)


def draw_scene(sb, panel, px, py, text):
    """在面板 (px,py) 处绘制场景背景与元素"""
    is_night = has(text, "晚上", "夜里", "夜晚", "夜间", "月光")
    is_rain = has(text, "下雨", "雨天", "雨", "大雨", "小雨", "暴雨")
    is_dusk = has(text, "傍晚", "黄昏", "夕阳")
    sky = "#1f2d4d" if is_night else ("#8fa8c8" if is_rain else ("#f7c98a" if is_dusk else "#bfe3f7"))
    # 天空
    sb.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
              % (px, py, PANEL_W, PANEL_H - CAP_H, sky))
    # 地面
    if has(text, "海", "游泳", "河边", "湖", "河边") and not has(text, "海边城市", "海上"):
        sb.append('<path d="M%d %d Q %d %d %d %d L %d %d Z" fill="#5dade2"/>'
                  % (px, py + PANEL_H - CAP_H - 60, px + PANEL_W / 2, py + PANEL_H - CAP_H - 120,
                     px + PANEL_W, py + PANEL_H - CAP_H - 60, px + PANEL_W, py + PANEL_H - CAP_H))
        sb.append('<path d="M%d %d L %d %d L %d %d Z" fill="#f2e6c9"/>'
                  % (px, py + PANEL_H - CAP_H, px + PANEL_W, py + PANEL_H - CAP_H,
                     px + PANEL_W, py + PANEL_H - CAP_H - 40))
    else:
        sb.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                  % (px, py + PANEL_H - CAP_H - 70, PANEL_W, 70, GRASS))
        sb.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                  % (px, py + PANEL_H - CAP_H - 10, PANEL_W, 10, GROUND))
    # 太阳 / 月亮 / 云 / 雨
    if is_night:
        sb.append('<circle cx="%d" cy="%d" r="26" fill="#f5e6a8"/>' % (px + 380, py + 70))
        sb.append('<circle cx="%d" cy="%d" r="22" fill="#1f2d4d"/>' % (px + 386, py + 64))
        for i in range(3):
            sx = px + 60 + i * 60
            sb.append('<circle cx="%d" cy="%d" r="3" fill="#fff"/>' % (sx, py + 50 + (i % 2) * 25))
    else:
        if has(text, "太阳", "晴天", "天气好", "阳光"):
            sb.append('<circle cx="%d" cy="%d" r="28" fill="#f9d71c"/>' % (px + 390, py + 62))
            for a in range(8):
                import math
                ang = a * math.pi / 4
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#f9d71c" stroke-width="4"/>'
                          % (px + 390 + 34 * math.cos(ang), py + 62 + 34 * math.sin(ang),
                             px + 390 + 42 * math.cos(ang), py + 62 + 42 * math.sin(ang)))
    # 云
    for cx, cy, s in ((px + 90, py + 70, 1), (px + 240, py + 45, 0.7)):
        c = "#d9d9d9" if is_rain else "#ffffff"
        sb.append('<circle cx="%d" cy="%d" r="%d" fill="%s"/>' % (cx, cy, int(20 * s), c))
        sb.append('<circle cx="%d" cy="%d" r="%d" fill="%s"/>' % (cx + 22 * s, cy + 4, int(16 * s), c))
        sb.append('<circle cx="%d" cy="%d" r="%d" fill="%s"/>' % (cx - 22 * s, cy + 6, int(14 * s), c))
    # 雨
    if is_rain:
        for i in range(26):
            rx = px + 20 + i * 18
            ry = py + 90 + (i * 7) % 150
            sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#5d9bd4" stroke-width="2"/>'
                      % (rx, ry, rx - 4, ry + 18))
    # 山
    if has(text, "山", "乡村", "乡下", "爬山", "郊外"):
        sb.append('<path d="M%d %d L %d %d L %d %d Z" fill="#a0c4a0"/>'
                  % (px + 40, py + PANEL_H - CAP_H - 70, px + 130, py + PANEL_H - CAP_H - 180,
                     px + 220, py + PANEL_H - CAP_H - 70))
        sb.append('<path d="M%d %d L %d %d L %d %d Z" fill="#bcd6b2"/>'
                  % (px + 170, py + PANEL_H - CAP_H - 70, px + 280, py + PANEL_H - CAP_H - 140,
                     px + 390, py + PANEL_H - CAP_H - 70))
    # 树
    if has(text, "树", "公园", "春天", "秋天", "风景", "郊外", "路边", "花园", "大自然"):
        for tx, ts in ((px + 70, 1.0), (px + 250, 0.8), (px + 400, 1.1)):
            sb.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="#8b5a2b"/>'
                      % (tx - 6 * ts, py + PANEL_H - CAP_H - 100 * ts, 12 * ts, 100 * ts))
            sb.append('<circle cx="%d" cy="%d" r="%d" fill="#4caf50"/>'
                      % (tx, py + PANEL_H - CAP_H - 120 * ts, int(34 * ts)))
            sb.append('<circle cx="%d" cy="%d" r="%d" fill="#66bb6a"/>'
                      % (tx - 16 * ts, py + PANEL_H - CAP_H - 135 * ts, int(22 * ts)))
    # 花
    if has(text, "花", "花园", "春天", "公园", "风景"):
        for fx in range(px + 60, px + PANEL_W, 60):
            fy = py + PANEL_H - CAP_H - 52
            sb.append('<circle cx="%d" cy="%d" r="7" fill="#e91e63"/>' % (fx, fy))
            sb.append('<circle cx="%d" cy="%d" r="3" fill="#fff"/>' % (fx, fy))
            sb.append('<rect x="%d" y="%d" width="3" height="14" fill="#4caf50"/>' % (fx - 1, fy + 6))
    # 房子
    if has(text, "家", "房子", "回家", "家门口", "家里", "宿舍", "小区", "村"):
        hx = px + 330
        hy = py + PANEL_H - CAP_H - 150
        sb.append('<rect x="%d" y="%d" width="110" height="80" fill="#f2b8c6" rx="4"/>' % (hx, hy))
        sb.append('<path d="M%d %d L %d %d L %d %d Z" fill="#c0392b"/>'
                  % (hx - 8, hy, hx + 55, hy - 48, hx + 118, hy))
        sb.append('<rect x="%d" y="%d" width="22" height="34" fill="#8b5a2b" rx="2"/>' % (hx + 46, hy + 46))
        sb.append('<rect x="%d" y="%d" width="18" height="18" fill="#aed6f1"/>' % (hx + 14, hy + 16))
        sb.append('<rect x="%d" y="%d" width="18" height="18" fill="#aed6f1"/>' % (hx + 78, hy + 16))
    # 学校 / 教学楼
    if has(text, "学校", "教学楼", "教室", "操场", "上学", "上课", "同学", "老师", "图书馆"):
        bx = px + 60
        by = py + PANEL_H - CAP_H - 150
        sb.append('<rect x="%d" y="%d" width="150" height="80" fill="#f0b27a" rx="4"/>' % (bx, by))
        for i in range(3):
            for j in range(2):
                sb.append('<rect x="%d" y="%d" width="22" height="18" fill="#aed6f1"/>'
                          % (bx + 18 + i * 44, by + 16 + j * 32))
        sb.append('<rect x="%d" y="%d" width="26" height="36" fill="#8b5a2b" rx="2"/>' % (bx + 62, by + 44))
        sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#6b4f2a" stroke-width="3"/>'
                  % (bx + 75, by, bx + 75, by - 30))
        sb.append('<polygon points="%d,%d %d,%d %d,%d" fill="#e74c3c"/>'
                  % (bx + 75, by - 30, bx + 92, by - 20, bx + 75, by - 10))
    # 跑道（操场）
    if has(text, "操场", "跑道", "运动会", "跑步", "比赛", "运动", "足球", "篮球", "体育"):
        ry = py + PANEL_H - CAP_H - 40
        sb.append('<rect x="%d" y="%d" width="%d" height="30" fill="#e67e22" rx="6"/>'
                  % (px + 30, ry, PANEL_W - 60))
        for i in range(6):
            sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#fff" stroke-width="2" stroke-dasharray="14 10"/>'
                      % (px + 36 + i * 76, ry + 15, px + 36 + i * 76 + 40, ry + 15))
        sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#fff" stroke-width="3"/>'
                  % (px + 30, ry + 3, px + PANEL_W - 30, ry + 3))
    # 医院
    if has(text, "医院", "看病", "生病", "受伤", "急救"):
        hx = px + 300
        hy = py + PANEL_H - CAP_H - 130
        sb.append('<rect x="%d" y="%d" width="130" height="70" fill="#f5f5f5" rx="4"/>' % (hx, hy))
        sb.append('<rect x="%d" y="%d" width="130" height="70" fill="none" stroke="#c0392b" stroke-width="4" rx="4"/>' % (hx, hy))
        sb.append('<rect x="%d" y="%d" width="20" height="14" fill="#c0392b"/>' % (hx + 26, hy + 28))
        sb.append('<rect x="%d" y="%d" width="20" height="14" fill="#c0392b"/>' % (hx + 66, hy + 28))
        sb.append('<rect x="%d" y="%d" width="14" height="20" fill="#c0392b"/>' % (hx + 34, hy + 25))
        sb.append('<rect x="%d" y="%d" width="14" height="20" fill="#c0392b"/>' % (hx + 74, hy + 25))
        sb.append('<rect x="%d" y="%d" width="18" height="24" fill="#8b5a2b" rx="2"/>' % (hx + 92, hy + 46))
    # 商店
    if has(text, "商店", "超市", "购物", "商场", "买", "店", "水果店", "书店", "市场"):
        sx = px + 40
        sy = py + PANEL_H - CAP_H - 140
        sb.append('<rect x="%d" y="%d" width="150" height="80" fill="#aed6f1" rx="4"/>' % (sx, sy))
        sb.append('<rect x="%d" y="%d" width="150" height="18" fill="#e74c3c" rx="2"/>' % (sx, sy - 8))
        for i in range(3):
            sb.append('<rect x="%d" y="%d" width="36" height="42" fill="#aed6f1" rx="2"/>' % (sx + 12 + i * 44, sy + 20))
            sb.append('<rect x="%d" y="%d" width="18" height="18" fill="#e74c3c" rx="2"/>' % (sx + 21 + i * 44, sy + 32))
        sb.append('<rect x="%d" y="%d" width="20" height="30" fill="#8b5a2b" rx="2"/>' % (sx + 66, sy + 50))
    # 车 / 公交
    if has(text, "公共汽车", "公交", "公交车", "车", "汽车", "出租车", "大巴", "地铁"):
        cx, cy = px + 200, py + PANEL_H - CAP_H - 90
        sb.append('<rect x="%d" y="%d" width="180" height="58" rx="12" fill="#f39c12"/>' % (cx, cy))
        for i in range(4):
            sb.append('<rect x="%d" y="%d" width="30" height="24" fill="#aed6f1" rx="3"/>' % (cx + 16 + i * 40, cy + 8))
        for wx in (cx + 40, cx + 120):
            sb.append('<circle cx="%d" cy="%d" r="13" fill="#2c3e50"/>' % (wx, cy + 58))
            sb.append('<circle cx="%d" cy="%d" r="6" fill="#95a5a6"/>' % (wx, cy + 58))
        sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#5b7fa6" stroke-width="8"/>'
                  % (cx, cy + 58, cx, cy + 120))
        sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#5b7fa6" stroke-width="8"/>'
                  % (cx + 180, cy + 58, cx + 180, cy + 120))
    # 餐桌 / 食物
    if has(text, "饭", "餐厅", "饭店", "吃", "饭馆", "食堂", "蛋糕", "早餐", "午饭", "晚饭", "聚餐"):
        tx, ty = px + 220, py + PANEL_H - CAP_H - 60
        sb.append('<rect x="%d" y="%d" width="130" height="12" fill="#8b5a2b" rx="4"/>' % (tx, ty))
        sb.append('<rect x="%d" y="%d" width="14" height="34" fill="#6b4f2a"/>' % (tx + 10, ty + 12))
        sb.append('<rect x="%d" y="%d" width="14" height="34" fill="#6b4f2a"/>' % (tx + 106, ty + 12))
        for i in range(3):
            sb.append('<circle cx="%d" cy="%d" r="11" fill="#f5f5f5" stroke="#ddd" stroke-width="2"/>'
                      % (tx + 24 + i * 34, ty - 8))
            sb.append('<circle cx="%d" cy="%d" r="5" fill="#e74c3c"/>' % (tx + 24 + i * 34, ty - 8))
    # 电话
    if has(text, "电话", "打电话", "手机", "手机"):
        px_ = px + 100
        py_ = py + 60
        sb.append('<rect x="%d" y="%d" width="26" height="44" rx="6" fill="#34495e"/>' % (px_, py_))
        sb.append('<rect x="%d" y="%d" width="18" height="30" rx="3" fill="#aed6f1"/>' % (px_ + 4, py_ + 5))


# ---------------------------------------------------------------- 人物
def draw_people(sb, panel, px, py, text, characters, action):
    """在面板底部绘制 1-3 个简单人物，动作按关键词匹配"""
    names = [n.strip() for n in re.split(r"[、，,和与及]", characters or "") if n.strip()]
    n = min(max(len(names), 1), 3)
    cx = px + PANEL_W / 2
    ground = py + PANEL_H - CAP_H - 12
    is_fall = has(action, "摔倒", "跌倒", "倒下", "摔")
    is_run = has(action, "跑", "追赶", "冲刺", "奔跑")
    is_help = has(action, "扶", "帮助", "帮忙", "救", "拉")
    is_wave = has(action, "打招呼", "挥手", "再见", "问好", "欢迎")
    is_old = has(action, "老人", "老爷爷", "老奶奶")
    is_cry = has(action, "哭", "难过", "伤心", "哭")
    is_laugh = has(action, "笑", "开心", "高兴", "鼓掌")

    positions = [cx, cx - 95, cx + 95]
    for i in range(n):
        x = positions[i]
        y = ground
        c = CLOTH[(panel + i) % len(CLOTH)]
        skin = SKIN[(panel + i) % len(SKIN)]
        if is_fall and i == 0:
            # 摔倒：躺在地上
            sb.append('<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="%s"/>'
                      % (x, y - 18, 15, 13, skin))
            sb.append('<rect x="%d" y="%d" width="34" height="12" rx="5" fill="%s"/>' % (x - 17, y - 8, c))
            sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                      % (x + 12, y - 16, x + 34, y - 24, c))
            sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                      % (x - 14, y - 14, x - 34, y - 20, c))
            sb.append('<circle cx="%d" cy="%d" r="3" fill="#fff"/>' % (x - 6, y - 20))
            sb.append('<circle cx="%d" cy="%d" r="3" fill="#fff"/>' % (x + 6, y - 20))
            sb.append('<circle cx="%d" cy="%d" r="2" fill="#2c3e50"/>' % (x - 4, y - 20))
            sb.append('<circle cx="%d" cy="%d" r="2" fill="#2c3e50"/>' % (x + 4, y - 20))
        else:
            # 站立 / 跑 / 挥手
            if is_run:
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                          % (x, y - 8, x + 8, y - 26, c))
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                          % (x, y - 8, x - 8, y + 10, c))
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                          % (x, y - 8, x + 14, y + 10, c))
            else:
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                          % (x, y - 8, x, y - 26, c))
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                          % (x, y - 8, x - 10, y + 10, c))
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                          % (x, y - 8, x + 10, y + 10, c))
            # 手臂
            arm_up = is_wave and i == 0
            sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                      % (x - 10, y - 34, x - 22, y - 22, c))
            if arm_up:
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                          % (x + 10, y - 34, x + 22, y - 52, c))
            else:
                sb.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="5"/>'
                          % (x + 10, y - 34, x + 22, y - 22, c))
            # 身体
            sb.append('<rect x="%d" y="%d" width="26" height="34" rx="7" fill="%s"/>' % (x - 13, y - 46, c))
            # 头
            sb.append('<circle cx="%d" cy="%d" r="15" fill="%s"/>' % (x, y - 64, skin))
            sb.append('<path d="M%d %d Q %d %d %d %d" stroke="#5b3a1e" stroke-width="4" fill="none"/>'
                      % (x - 13, y - 70, x, y - 82, x + 13, y - 70))
            # 脸
            sb.append('<circle cx="%d" cy="%d" r="2.4" fill="#2c3e50"/>' % (x - 6, y - 66))
            sb.append('<circle cx="%d" cy="%d" r="2.4" fill="#2c3e50"/>' % (x + 6, y - 66))
            mouth = '<path d="M%d %d Q %d %d %d %d" stroke="#2c3e50" stroke-width="2.4" fill="none"/>' \
                % (x - 6, y - 57, x, y - 52, x + 6, y - 57)
            if is_cry:
                mouth = '<path d="M%d %d Q %d %d %d %d" stroke="#2c3e50" stroke-width="2.4" fill="none"/>' \
                    % (x - 6, y - 52, x, y - 58, x + 6, y - 52)
            sb.append(mouth)


def draw_dialogue(sb, panel, px, py, dialogue):
    """在面板中画对话框气泡（对话可选，不传则不画）"""
    if not dialogue:
        return
    txt = str(dialogue)[:18]
    bw = max(70, 20 + len(txt) * 15)
    bx = px + PANEL_W - bw - 24
    by = py + 30
    sb.append('<rect x="%d" y="%d" width="%d" height="34" rx="16" fill="#ffffff" stroke="#7f8c8d" stroke-width="1.5"/>'
              % (bx, by, bw))
    sb.append('<path d="M%d %d L %d %d L %d %d Z" fill="#ffffff" stroke="#7f8c8d" stroke-width="1.5"/>'
              % (bx + 20, by + 30, bx + 30, by + 46, bx + 44, by + 30))
    sb.append('<text x="%d" y="%d" font-size="14" fill="#2c3e50">%s</text>'
              % (bx + 14, by + 22, esc(txt)))


# ---------------------------------------------------------------- 主渲染
def render_svg(panels, title):
    """渲染 2x2 四格漫画 SVG 字符串"""
    W = 2 * PANEL_W + 3 * 18
    H = 2 * (PANEL_H + CAP_H) + 96
    sb = []
    sb.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
              % (W, H, W, H))
    sb.append('<rect width="%d" height="%d" fill="#fbf7f0"/>' % (W, H))
    sb.append('<text x="%d" y="46" text-anchor="middle" font-size="26" font-weight="bold" fill="#2c3e50">四格漫画：%s</text>'
              % (W / 2, esc(title or "看图作文")))
    for i, p in enumerate(panels[:4]):
        col, row = i % 2, i // 2
        px = 18 + col * (PANEL_W + 18)
        py = 70 + row * (PANEL_H + CAP_H + 18)
        # 面板底
        sb.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="#ffffff" stroke="#d5c8b4" stroke-width="2"/>'
                  % (px, py, PANEL_W, PANEL_H + CAP_H))
        # 场景
        scene_text = "%s %s %s" % (p.get("scene", ""), p.get("action", ""), p.get("mood", ""))
        draw_scene(sb, i, px, py, scene_text)
        # 人物
        draw_people(sb, i, px, py, scene_text, p.get("characters", ""), p.get("action", ""))
        # 对话框（可选）
        draw_dialogue(sb, i, px, py, p.get("dialogue", ""))
        # 图注
        cap = "图%d　%s" % (i + 1, p.get("action", ""))
        sb.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#f4ead9" rx="6"/>'
                  % (px + 8, py + PANEL_H - CAP_H + 6, PANEL_W - 16, CAP_H - 12))
        sb.append('<text x="%d" y="%d" font-size="15" fill="#5b4636">%s</text>'
                  % (px + 18, py + PANEL_H - CAP_H + 26, esc(cap)))
    sb.append('</svg>')
    return "\n".join(sb)


def main():
    ap = argparse.ArgumentParser(description="四格漫画 SVG 渲染器（纯标准库）")
    ap.add_argument("--panels-json", default=None, help="四格故事 JSON 文件路径")
    ap.add_argument("--panel-1", "--panel-2", "--panel-3", "--panel-4", dest="panels", action="append", default=[],
                    help="四格画面描述（不传 JSON 时依次用 4 次）")
    ap.add_argument("--output", required=True, help="输出 SVG 路径，如 /mnt/user-data/outputs/comic_助人为乐.svg")
    ap.add_argument("--title", default="看图作文", help="漫画标题")
    args = ap.parse_args()

    if args.panels_json:
        with open(args.panels_json, encoding="utf-8") as f:
            panels = json.load(f)
        if not isinstance(panels, list) or not panels:
            print(json.dumps({"error": "panels JSON 必须是四格数组"}, ensure_ascii=False))
            sys.exit(1)
    elif len(args.panels) >= 1:
        panels = [{"action": t} for t in args.panels[:4]]
        while len(panels) < 4:
            panels.append({"action": ""})
    else:
        print(json.dumps({"error": "缺少输入：用 --panels-json 或 --panel-1..4"}, ensure_ascii=False))
        sys.exit(1)

    svg = render_svg(panels, args.title)
    out = args.output
    if not out.lower().endswith(".svg"):
        out += ".svg"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(json.dumps({"success": True, "path": out, "panels": len(panels)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
