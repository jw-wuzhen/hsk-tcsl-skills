# HSK 对话材料生成器 — TCSL 版 v2.0（提示词驱动架构）

基于新版HSK大纲（2026年7月实施）的对话材料生成器，面向国际中文学习者（TCSL）与教师。
三种材料：场景对话脚本、话题问题卡（热身/核心/拓展）、角色扮演任务卡（A/B角色）。

## 与 v1.x 的核心区别（为什么改成现在这样）

v1.x 是"代码驱动"：内容由 `main.py` 从固定题库（40 对话/24 卡组/24 任务）拼装，平台调用
`execution.handler` 执行；话题不在题库内会降级或跑题。在易思捷平台上表现为内容模板化、灵活度低。

v2.0 改为 **"提示词驱动"**（与 chinese-writing-tutor-tcsl-v3.9 同一架构）：
- `SKILL.md` 本身就是给平台主模型的**操作手册**：触发词、分步工作流、输出模板、错误处理
- **任意话题都能生成**：话题先在大纲话题树定位，树外话题映射到最接近分支，不再报错
- 参考数据（口语分级指南、话题树、40 篇对话+24 卡组+24 任务样例、2026 词表）作为生成**锚点**
- 生词由 `hsk_lookup.py` 按 2026 官方词表核查并★标注；句长/书面语由 `text_stats.py` 检查
- 场景对话默认交付 **HTML 学习页**（气泡双栏对话 + 遮句自练 + 生词悬停标注，`render_dialogue_html.py` 生成）；问题卡/角色扮演卡为 Markdown 文本；均无外部 API 依赖

## 目录结构

```
hsk-conversation-generator-tcsl/
├── manifest.yaml          # Skill 配置（平台读取；与 v3.9 相同格式，无 execution.handler）
├── SKILL.md               # 模型操作手册（核心）
├── reference/             # 参考数据（模型生成时查阅）
│   ├── speaking_guide.md      # 口语分级指南：等级参数/说能力/语法边界/问题分级/支架规则
│   ├── hsk_grading_standard.md
│   ├── hsk_guide.md           # 分级简化与降级替换指南
│   ├── topic_tree.md          # 大纲话题树（三级）
│   ├── hsk30_words.json       # HSK3.0 官方词表（GF0025-2021，查词级控用）
│   ├── model_dialogues/       # 40 篇参考对话（按等级合并）
│   ├── discussion_cards/      # 24 组参考问题卡（按等级合并）
│   └── roleplay_cards/        # 24 个参考角色扮演任务（按等级合并）
└── scripts/               # 轻量工具脚本（纯标准库）
    ├── hsk_lookup.py          # 查词：返回词的 HSK 等级
    ├── text_stats.py          # 句长/书面语标记检查
    └── render_dialogue_html.py  # 场景对话 HTML 学习页渲染（气泡双栏/遮句自练/生词悬停）
```

## 部署

1. 把整个 `hsk-conversation-generator-tcsl/` 目录打包为 `.zip`
2. 在易思捷平台上传（平台自动读取 `manifest.yaml`）
3. 用平台对话验证：

   - "HSK2问路对话材料"
   - "生成HSK4关于网上购物的讨论问题卡，5张"
   - "HSK5春节话题的角色扮演任务"
   - "HSK1自我介绍场景对话，要英文支架"
   - "Give me an HSK3 dialogue about seeing a doctor"

## 测试

本包无 `execution.handler`，直接以对话方式使用。脚本可单独验证：

```bash
python scripts/hsk_lookup.py --words "春联,旅行,老龄化"
python scripts/text_stats.py --text "对话台词" --level hsk3
python scripts/render_dialogue_html.py --dialogue-json /path/dialogue.json --output /path/dialogue.html
```

- 作者：EasyJet AI Team
- 分类：education（国际中文教学 / TCSL / HSK / 口语 / 对话 / 角色扮演）
