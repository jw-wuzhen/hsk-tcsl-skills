# HSK 写作题目生成器 — TCSL 版 v2.0（提示词驱动架构）

基于新版HSK大纲（2026年7月实施）的写作题目与范文生成器，面向国际中文学习者（TCSL）与教师。

## 与 v1.x 的核心区别（为什么改成现在这样）

v1.x 是"代码驱动"：所有内容由 `main.py` 从固定题库拼装，平台调用 `execution.handler` 执行；
话题不在 56 篇范文库内会**直接报错**，四格图依赖外部绘图 API，输出默认是大段 HTML 字符串。
在易思捷平台上表现为：任意话题容易失败、内容模板化、图片 API 不稳定。

v2.0 改为 **"提示词驱动"**（与 chinese-writing-tutor-tcsl-v3.9 同一架构）：
- `SKILL.md` 本身就是给平台主模型的**操作手册**：触发词、分步工作流、输出模板、错误处理，模型按手册直接生成内容
- **任意话题都能生成**：话题先在大纲话题树定位，树外话题映射到最接近分支，不再报错
- 参考数据（写作指南、话题树、56 篇范文样例、2026 词表）作为模型生成的**锚点**，保证级控
- 查词/难度检查/HTML 渲染由轻量脚本完成（`hsk_lookup.py` / `text_stats.py` / `render_essay_html.py`），不再依赖外部 API
- **看图作文必出四格漫画图片**（本技能特色），三级路径保证：**①千问 API（通义万相）生图（首选，画质最好，纯标准库脚本 `comic_gen.py`）→ ②平台自带图像生成工具 → ③本地 `comic_render.py` 生成 SVG（零网络、零密钥、必成功）**。任何情况下至少有一张图片交付，并嵌入 HTML 学习页
- **稳定输出 HTML 学习页**（与 chinese-writing-tutor-tcsl-v3.9 同一交付方式）：SKILL.md 中 HTML 是强制步骤——范文文本交给 `render_essay_html.py` 生成自包含 HTML 文件，再经 `present_files` 交付；模型不手写 HTML、不手工标注（避免 token 溢出）。**HTML 为双视图教学素材：学生练习版（题目/漫画/构思引导/句型/关键词/写作要求）+ 教师备课版（教学信息/参考范文/范文结构/评分要点/教学建议/级控检查/考试说明），带打印/下载按钮，教师可直接下载使用。** 文本视图始终同时输出，HTML 失败时降级为纯文本并注明

## 目录结构

```
hsk-writing-generator-tcsl/
├── manifest.yaml          # Skill 配置（平台读取；与 v3.9 相同格式，无 execution.handler）
├── api_key.txt            # 千问 DashScope 密钥（随包部署，看图作文生图用）
├── SKILL.md               # 模型操作手册（核心）
├── reference/             # 参考数据（模型生成时查阅）
│   ├── writing_guide.md       # 写作分级指南：等级/题型/字数/结构/评分要点/语法边界
│   ├── hsk_grading_standard.md # 词汇量/语法/写作能力分级标准
│   ├── hsk_guide.md           # 分级简化与降级替换指南
│   ├── topic_tree.md          # 大纲话题树（三级）
│   ├── hsk_vocab.json         # 2026 版 HSK 分级词表（级控查词用）
│   ├── char_pinyin.json       # 汉字拼音映射（HTML 渲染用）
│   └── model_essays/          # 56 篇参考范文（按题型合并，含四格图/引语/结构/生词）
└── scripts/               # 轻量工具脚本（纯标准库）
    ├── hsk_lookup.py          # 查词：返回词的 HSK 等级（2026 大纲口径）
    ├── text_stats.py          # 句长/书面语标记检查（level check）
    ├── comic_gen.py           # 四格漫画生成（千问通义万相 API，首选，画质好）
    ├── comic_render.py        # 四格漫画 SVG 渲染（纯本地保底，必成功）
    └── render_essay_html.py   # HTML 教学素材渲染（学生练习版+教师备课版，按等级着色+拼音，可嵌入漫画，可打印/下载）
```

## 千问生图密钥配置（看图作文首选路径）

**`api_key.txt` 已随包附带**（放在技能包根目录，与 manifest.yaml 同级），脚本会自动读取。若密钥更换：直接编辑 `api_key.txt`（一行一个密钥，`#` 开头为注释）后重新打包上传即可。
也可用环境变量 `DASHSCOPE_API_KEY` / `QWEN_API_KEY`，或调用时传 `--api-key`（优先级：参数 > 环境变量 > 包内文件）。
> ⚠️ 密钥随包分发：请妥善保管 zip，不要公开分享；密钥泄露请到阿里云百炼控制台重置后更新该文件。

## 部署

1. 把整个 `hsk-writing-generator-tcsl/` 目录打包为 `.zip`
2. 在易思捷平台上传（平台自动读取 `manifest.yaml`）
3. 用平台对话验证：

   - "生成一个HSK4的短文写作题目，话题是旅行"
   - "HSK5看图作文，四格图，关于保护环境"
   - "HSK6议论文，人工智能会不会抢走人的工作？要范文和教师视图"
   - "HSK2基础书写练习，介绍一下你的家人"

## 测试

本包无 `execution.handler`，直接以对话方式使用。脚本可单独验证：

```bash
python scripts/hsk_lookup.py --words "外滩,坚持,旅行"
python scripts/text_stats.py --text "范文正文" --level hsk4
python scripts/comic_gen.py --panels-json panels.json --output-dir . --mode single   # 需要密钥；无密钥会返回降级提示
python scripts/comic_render.py --panel-1 "运动会上李明跑在最前面" --panel-2 "李明摔倒了" --panel-3 "同学们扶起他" --panel-4 "大家一起跑向终点" --output comic_运动会.svg --title "运动会"
python scripts/render_essay_html.py --essay-text "范文正文" --hsk-level 5 --title "标题" --teacher-json teacher.json --comic-svg comic_运动会.svg --output test.html
```

- 作者：EasyJet AI Team
- 分类：education（国际中文教学 / TCSL / HSK / 写作 / 备考）
