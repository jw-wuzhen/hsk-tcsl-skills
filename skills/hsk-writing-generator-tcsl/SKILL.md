---
name: hsk-writing-generator-tcsl
description: "基于新版HSK大纲（2026年7月实施）的写作题目与范文生成器，面向国际中文学习者（TCSL）与教师。覆盖HSK1-6全部写作题型：HSK1-3基础书写练习、HSK4短文写作（≥80字）、HSK5看图作文（≥100字，四格图）+引语作文（≥200字）、HSK6应用文（≥150字）+议论文（≥300字）。任意话题均可处理：先在大纲话题树中定位，再按等级生成写作题目、构思引导问题、可用句型、参考关键词、参考范文（本级词汇撰写，生词★标注并附拼音+词性+释义+例句）、教师教学视图。当用户需要HSK写作练习题、布置写作作业、备考模拟练习、参考范文或教师备课材料时调用。 | An HSK writing task & model-essay generator built on the new HSK syllabus (effective July 2026) for international Chinese learners (TCSL) and teachers. Covers all HSK1-6 writing tasks; any topic is supported."
---

# HSK 写作题目生成器 — TCSL 版 v2.0

基于新版HSK考试大纲（2026年7月实施）的写作材料生成器，面向国际中文学习者与教师。

三大能力：
1. **写作题目生成**——任意话题、任意等级，生成题目+构思引导+句型+关键词
2. **参考范文**——话题命中范文库则推荐，未命中则按级控规则现场新写，生词★标注
3. **教师备课视图**——大纲依据、话题树位置、范文结构、评分要点、教学建议

## Language Rules

Target users: English-speaking Chinese learners (international students).
- 中文文本、拼音、中文释义：保持中文
- 语法/教学术语：英文（括号附中文），如 Subject (主语)
- 题目、引导问题、句型、关键词、范文正文：中文
- 解释、建议、提示、评分要点：英文（用户要求中文或 `feedback_language=zh` 时用中文）
- 询问等级："What is your HSK level?"

## 题型与字数速查

| 等级 | 题型 (exam_type) | 最少字数 | 题目特征 |
|------|------------------|----------|----------|
| HSK1-3 | 基础书写练习 `sentence_practice` | 写汉字/词语/1-3句话 | 抄写、填写基本信息、简单介绍 |
| HSK4 | 短文写作 `short_essay` | 80 | 介绍人/事/物，讲述一次经历 |
| HSK5 | 看图作文 `picture_story` | 100 | 根据四格图写完整故事 |
| HSK5 | 引语作文 `quote_essay` | 200 | 根据名言/俗语写，结合经历谈理解 |
| HSK6 | 应用文 `practical_writing` | 150 | 通知、启事、邀请信、邮件、说明书 |
| HSK6 | 议论文 `argumentative` | 300 | 对争议话题表达观点、论证 |

---

## Feature 1: 写作题目生成

**Trigger**: 写作题目、作文题、写作文、练习题、布置作业、出一个题、writing task、essay topic、practice、homework
**Input**: HSK level (required) + exam_type (optional) + topic (optional) + native_language (optional)

### Step 1: 确定 HSK 等级

**⚠️ 最重要：先扫描用户消息中的等级，找到就不要再问。**

扫描模式（不区分大小写）：
- "HSK" + 数字 1-6（如 HSK6、HSK 3、hsk4）
- "等级" + 数字 1-6（如 等级5）
- 数字 1-6 + "级"（如 6级）
- "level" + 数字 1-6（如 level3）

找到 → 直接使用，进入 Step 2。**绝不再问。**
没找到 → 问 "What is your HSK level?"

示例：
- "生成一个HSK5的看图作文" → 等级 HSK5 → 直接执行
- "HSK4短文写作，旅行话题" → 等级 HSK4、题型 short_essay、话题 旅行 → 直接执行
- "帮我出个作文题" → 没找到等级 → 先问等级

### Step 2: 确定题型

- 用户明确说了题型 → 使用
- 没说明 → 按该等级默认题型：HSK1-3 `sentence_practice`；HSK4 `short_essay`；HSK5 `picture_story`；HSK6 `argumentative`
- 用户指定的题型与该等级不符（如"HSK4的议论文"）→ 礼貌说明该等级可选题型，推荐最接近的一种，不要硬生成

### Step 3: 话题定位（任意话题都支持）

1. 读取 `<skill_root>/reference/topic_tree.md`，把用户话题定位到树上：等级 > 一级 > 二级 > 三级
2. 话题在树内 → 按原话题生成
3. **话题不在树内**（如"野外露营"、"国际贸易"）→ 不要报错！选择话题树中与该话题最接近的一支，题目围绕该支展开；在教师视图注明"话题已映射到：XX（原话题：XX）"。低等级学生遇到高等级话题（如 HSK4 被要求写"人工智能"）→ 改写为贴近该等级生活的场景（如"用手机学中文"）
4. 用户没给话题 → 从该等级话题树中选一个高频话题（或随机）

### Step 4: 组装题目

读取 `<skill_root>/reference/writing_guide.md` 第二节，按题型模板组装：
- 题目 = 题型提示语 + 字数要求 + 具体任务
- 参考关键词 5-8 个（本等级词汇）
- 构思引导问题 3-4 个（本等级句式：HSK1-2 "你什么时候……？"，HSK4-5 "你觉得……怎么样？"，HSK6 "有人认为……，你怎么看？"）
- 可用句型 2-3 条（本等级语法点）

### Step 5: 输出（学生视图）

按"输出模板 · 学生视图"输出。

> 若用户同时要参考范文/完整练习材料（常见默认需求，如"HSK4旅行作文"），继续执行 **Feature 2**：生成范文并按 Step 7 产出 HTML 学习页——这是本技能的稳定交付形态（文本视图 + HTML 文件）。只有用户明确"只要题目"时才停在 Step 5。

---

## Feature 2: 参考范文

**Trigger**: 范文、参考作文、例文、model essay、sample essay、example essay
**Input**: topic (optional) + HSK level (**required**)

### Step 1: 确定 HSK 等级

同 Feature 1 Step 1 的扫描规则：找到就不再问。

### Step 2: 确定题型

同 Feature 1 Step 2（范文要对应题型：看图作文配四格图故事，应用文配文体格式）。

### Step 3: 选择范文方式

**Mode A — 推荐范文库**：话题命中范文库 → 读取 `<skill_root>/reference/model_essays/<type>.md`（如 `hsk4.md`、`hsk5_picture.md`），按话题/引语/文体选最接近的一篇。

**Mode B — 现场新写**：话题未命中范文库、或用户明确要新内容 → 按以下规则现场写一篇：
1. 先读 `<skill_root>/reference/writing_guide.md` 第三、四节确定该等级写作能力与语法边界
2. 参照 `<skill_root>/reference/model_essays/<type>.md` 中同题型范文的结构与风格
3. 用本等级词汇书写（拿不准的词查 `hsk_lookup.py`，见 Step 5）
4. 按题型结构组织：短文=开头-主体-结尾；看图=四格图推进；引语=理解-经历-点题；应用文=文体格式（通知/启事有标题+正文+落款，邮件有称呼+正文+署名）；议论文=观点-理由-例子-结论。**范文必须：① 起一个贴合话题的标题；② 正文分成 3-4 个自然段**（每段一个中心意思），不要整篇写成一段。

### Step 4: 语法检查与修正

**输出前检查并修正所有语法错误：**
- 错别字、的/地/得混用、标点错误
- 残缺句、语序偏误、关联词残缺（虽然……**但是**……）
- 口语书面语混用、欧化句式（"被"字滥用、名词化堆叠）
- 成语/文言词与等级不符

修正后**只输出修正版**，不展示原始错误。

### Step 5: 级控检查与生词标注

1. 从范文中挑出 10-20 个最没把握的词（高级动词、形容词、抽象名词）以及所有准备标注的词
2. 运行查词脚本：
   ```bash
   python3 <skill_root>/scripts/hsk_lookup.py --words "词1,词2,..."
   ```
3. 处理规则（**生词 = 目标等级及以上词汇**；如用户指定 HSK5，则 HSK5/HSK6/HSK7-9 级词及词表查不到的词均为生词）：
   - 词的等级 < 学生等级 → 正常使用（已学词汇）
   - 词的等级 ≥ 学生等级，或词表查不到 → 视为**生词**：文中用 ★ 包起来（如 ★真是★），并在【生词表】给出 拼音 + 词性 + 释义 + 原文例句（词性在标注时给出，没有可留空；原文例句留空时脚本自动从范文提取）
   - 结构助词（了/呢/吗/吧/啊）和标点跳过
4. 句长检查：HSK1 ≤8字、HSK2 ≤14字、HSK3 ≤18字、HSK4 ≤22字、HSK5 ≤28字、HSK6 ≤35字。如不确定，可运行：
   ```bash
   python3 <skill_root>/scripts/text_stats.py --text "<范文>" --level hsk4
   ```

### Step 6: 输出（学生视图 + 教师视图）

按"输出模板"输出。范文正文必须达到题型字数要求（数汉字，不含标点）。

### Step 7: 生成 HTML 学习页（强制步骤，自动完成，禁止手工标注）

**⚠️ 不要手工给句子中的词加注——这会导致 token 溢出。一律用脚本生成。**
**⚠️ 不要自己写 HTML——把范文文本交给脚本，由脚本生成文件。**

1. 把**修正后的范文**保存到 `/mnt/user-data/workspace/essay_text.txt`，格式为：**第一行 = 标题**（贴合话题，不加书名号）；**其后每一行 = 一个自然段**（开头-主体-结尾，分 3-4 段，不要整篇挤成一段；不加"图1/图2"等标注；图序信息写在 teacher.json 的 `structure` 字段里）。渲染时标题自动居中、正文每段首行自动空两格，模拟日常作文书写格式。
2. 把重点词句（5-8 个，**必须是范文正文中实际出现的表达**）保存到 `/mnt/user-data/workspace/expr.json`，JSON 数组格式：
   ```json
   [{"expression":"真是","pinyin":"zhēn shì","hsk":7,"en_def":"really; indeed","explanation":"","example":"你真是个懂礼貌的好孩子。"}]
   ```
   **注意：`example` 填范文中包含该表达的原句（含省略号的表达如"虽然……但是……"也能自动匹配）；留空则脚本自动从范文提取。重点词句必须**实际出现在范文正文**，若范文没有该表达，学习页会给出提示，请勿收录范文外的词句。**
3. 把教师元数据保存到 `/mnt/user-data/workspace/teacher.json`（把输出模板"学生视图+教师视图"里的结构化信息填进去）：
   ```json
   {
     "exam_name":"看图作文","exam_type":"picture_story","topic":"公交让座",
     "level_label":"HSK 5","min_chars":100,"time_limit":"25分钟",
     "question":"根据下面四格漫画写一篇作文，不少于100字。",
     "guiding_questions":["图上都有谁？","发生了什么事？","结果怎么样？"],
     "patterns":["……的时候，……","虽然……但是……"],"connectors":["首先","然后","最后"],
     "keywords":["让座","老人","礼貌","帮助"],
     "requirements":["字数不少于100字","结构：开头-主体-结尾"],
     "teaching_info":[["等级","HSK 5（CEFR B1）"],["考试题型","看图作文（≥100字）"],["大纲写作能力","…"],["话题树位置","社会交往 > 公共交通 > 让座"]],
     "structure":"图1（车上人多找座）→ 图2（老奶奶上车没座）→ 图3（小明让座）→ 图4（大家点赞，小明开心）",
     "rubric":["内容完整（四图要素齐全）","语言准确（本级词汇语法）","结构清晰（起因-经过-结果）"],
     "teaching_tips":["先让学生看漫画编故事，再给范文","★生词先讲解再让学生读"],
     "exam_note":"HSK5 看图作文要求…",
     "glossary":[{"word":"真是","pinyin":"zhēn shì","pos":"adv.","meaning":"really; indeed","example":"你真是个懂礼貌的好孩子。"}],
     "out_of_syllabus_note":"生词 x 个已★标注，请先解释再使用"
   }
   ```
   **注意：缺字段没问题（脚本会跳过空卡片），但题目、题型、字数、结构、评分要点这些核心字段务必填。**
   **⚠️ 生词表一致性（必守）：`glossary` 只收范文中**实际出现**、且正文中已用 ★ 标注的词**，逐一对齐；严禁收录范文中没有的词（如示例中的"真是"必须出现在范文正文里）。
4. 运行脚本（脚本自动按 2026 词表分段、标注每个词的 HSK 等级与拼音、高亮重点词句，生成**学生练习版+教师备课版双视图、带打印/下载按钮**的自包含 HTML；**看图作文时嵌入四格漫画**）：
   ```bash
   python3 /mnt/skills/user/hsk-writing-generator-tcsl/v2.0.7/scripts/render_essay_html.py \
     --essay-file /mnt/user-data/workspace/essay_text.txt \
     --expressions-json /mnt/user-data/workspace/expr.json \
     --teacher-json /mnt/user-data/workspace/teacher.json \
     --output /mnt/user-data/outputs/essay_话题_HSKx.html \
     --hsk-level 5 --title "标题"
   ```
   看图作文**必须嵌入漫画**（三选一）：千问 panels（默认）`--comic-images comic_话题_p1.png,...,comic_话题_p4.png`；千问 single 图 `--comic-image /mnt/user-data/outputs/comic_话题.png`；本地保底 `--comic-svg /mnt/user-data/outputs/comic_话题.svg`
   脚本路径不可用时：把 `render_essay_html.py` 复制到 `/mnt/user-data/workspace/`，并把 `reference/` 下的 `hsk_vocab.json`、`char_pinyin.json` 一起复制为 `/mnt/user-data/workspace/reference/`（保持 scripts 与 reference 的上下级关系），从工作区运行。
5. 调用 `present_files(path="/mnt/user-data/outputs/essay_话题_HSKx.html")` 把 HTML 文件展示给用户。
6. HTML 生成失败时：文本视图照常输出，并注明"HTML 学习页暂不可用"。**绝不编造 HTML 内容，绝不展示原始报错信息。**

---

## Feature 3: 看图作文四格漫画（**必出图片**）

看图作文（picture_story）的核心特色是**四格漫画图片**——**任何情况下都必须产出一张图片交付，绝不能只输出文字画面描述**。**不依赖任何外部 API/密钥/外网。**

### Step 1: 设计四格故事（文本）

按话题设计四格故事：图1（遇到/开始）→ 图2-3（发展/冲突/帮助）→ 图4（结果）。每格填写：
- `scene` 场景（学校操场、公交车上、公园……）
- `props` 场景标志物（**必填，2-3 个可画的物体**，如"车窗、扶手、双排座椅"——让模型把场景画出来，避免只画人物特写）
- `characters` 人物（李明、同学们……）
- `look` 主角外貌（**四格共用同一描述**，如"穿红色短袖T恤、黑色短发、圆脸的男孩"——保证生成的人物四格一致）
- `action` 动作（**只写一个核心瞬间，一个动词短语，一眼能看懂**，如"小明指着靠窗的空座位，正要坐下"；**不要写一连串动作**——"走进车厢、穿过人群、找到座位、坐下"这种会被模型简化丢失）
- `mood` 情绪（开心/难过/着急……）
- `detail` 画面细节（可选，每格 1 个关键细节，如"膝盖擦破，坐在地上"）
- `dialogue` 台词（可选，1 句，短）

**连贯性要求**：四格必须围绕**同一主角**，情节因果连贯（图1起因→图2/3发展→图4结果）；动作描述要具体、可画出来（谁+做什么+关键细节），避免抽象词。

**场景人物结合要求**（看图作文的画面核心）：每格都要让读者**一眼看清"在哪里、谁、在做什么"**——场景占画面重要部分（画全景或中景，人物全身或大半身，不要人物特写/大头像），场景标志物清晰可辨（公交车要有车窗扶手、公园要有树和长椅、医院要有病床和吊瓶）。

把四格存为 `/mnt/user-data/workspace/panels.json`：
```json
[
  {"scene":"学校操场","props":"跑道、观众席、彩旗","characters":"李明、同学们","look":"穿红色短袖T恤、黑色短发、圆脸的男孩","action":"运动会上李明跑在最前面","mood":"开心","dialogue":"加油！","detail":"他回头看向身后"},
  {"scene":"操场跑道","props":"红色跑道、白线","characters":"李明","action":"李明不小心摔倒了","mood":"难过","detail":"膝盖擦破，坐在地上"},
  {"scene":"操场","props":"跑道、草坪","characters":"同学们","action":"两个同学赶紧跑过来把李明扶起来","mood":"关心","detail":"一人扶一边，表情担心"},
  {"scene":"终点","props":"终点线、彩带","characters":"李明、同学们","action":"大家一起手拉手跑向终点","mood":"开心","detail":"一起冲过终点线，阳光明媚"}
]
```

### Step 2: 生成四格漫画图片（三级路径，**至少产出一张**）

**路径①（首选）— 千问 API 生图（画质最好）**：运行包内脚本 `comic_gen.py`（纯标准库，调通义万相文生图）：
```bash
python3 /mnt/skills/user/hsk-writing-generator-tcsl/v2.0.7/scripts/comic_gen.py \
  --panels-json /mnt/user-data/workspace/panels.json \
  --output-dir /mnt/user-data/outputs --title "话题" --mode panels
```
- **`--mode panels`（默认推荐）**：逐格生成 4 张独立图——每格独立提示词、独立画布，**场景和动作最清晰**（看图作文的画面核心是"人物+场景结合"，panels 模式最能保证）；4 次调用，约 2-3 分钟
- `--mode single`：一次生成一张 2×2 四格漫画（快，但四格细节容易互相抢戏，场景保真度低于 panels；仅当时间紧张时使用）
- **脚本已内置连贯性提示词**：四格主角外貌/服装必须一致（自动读取 panels.json 的 `look` 字段）、每格一眼看清"在哪里、谁、在做什么"、场景占画面主体（全景/中景）、画面禁止出现文字（含标牌留白）。**不要修改脚本的提示词构造，直接调用即可。**
- 密钥解析链：技能包内 `api_key.txt`（推荐）→ 环境变量 `DASHSCOPE_API_KEY`/`QWEN_API_KEY` → `--api-key` 参数
- 脚本返回 `success: false`（无密钥/未开通/网络失败）→ **立即降级路径②**

**路径②（次选）— 平台图像生成工具**：若平台主模型有图像生成能力（如 image_gen/文生图工具），用它把四格画面描述生成为卡通四格漫画（画面中不出现文字）。

**路径③（保底，必成功）— 本地脚本**：运行包内 `comic_render.py`（零网络、零密钥）生成教学示意图风格的四格漫画 SVG：
```bash
python3 /mnt/skills/user/hsk-writing-generator-tcsl/v2.0.7/scripts/comic_render.py \
  --panels-json /mnt/user-data/workspace/panels.json \
  --output /mnt/user-data/outputs/comic_话题.svg --title "话题"
```

**规则**：按 ①→②→③ 依次尝试；②③失败（几乎不可能，③是纯本地）→ 才允许输出文字画面描述并注明"漫画生成失败"。**任何情况下至少交付一张图片，绝不只给文字。**

### Step 3: 交付（**漫画必须嵌入 HTML 学习页**）

1. **漫画图一律嵌入 HTML 学习页**（HTML 是主交付物，图在其中，不再"图是图、文是文"）：
   - 千问 `--mode panels`（默认）：加 `--comic-images comic_话题_p1.png,...,comic_话题_p4.png`（2×2 网格嵌入）
   - 千问 `--mode single`：加 `--comic-image /mnt/user-data/outputs/comic_话题.png`（整张 2×2 图嵌入）
   - 本地 SVG：加 `--comic-svg /mnt/user-data/outputs/comic_话题.svg`
2. 交付顺序：
   - 先用 `present_files(path="/mnt/user-data/outputs/essay_话题_HSKx.html")` 交付 HTML（图已嵌入）
   - 漫画 PNG 可再单独 `present_files` 一次（方便学生保存原图）
3. 范文必须覆盖四张图的情节推进（对照 Feature 2 Step 3 Mode B 第 4 条）

---

## 输出模板

### 学生视图

```text
## ✍️ HSK写作练习：<题型名>（HSKx）

### 题目
<题目全文，含字数要求>

【四格漫画】（看图作文时，**必须展示漫画图片**）
🖼️ 图片：comic_话题.svg — 从项目文件打开（已生成四格漫画）
图1：<画面描述>
图2：<画面描述>
图3：<画面描述>
图4：<画面描述>

### 💡 构思引导
1. <引导问题>
2. <引导问题>
3. <引导问题>

### 🔧 可用句型
- <句型1>
- <句型2>

### 🔑 参考关键词
<关键词1、关键词2、……>

### 📝 参考范文（约 xxx 字）
<标题居中；正文每段首行空两格（日常作文格式）；生词★标注>

【生词表】（★标记的词为本等级及以上词汇，请先解释再使用；含拼音、词性、释义、原文例句）
- ★真是★ 拼音：zhēn shì　词性：adv.　释义：really; indeed　例句：你真是个懂礼貌的好孩子。

### 📄 HTML 学习页
File: essay_话题_HSKx.html — 从项目文件打开（已自动按 HSK 等级标注拼音与释义，可打印/下载）
```

### 教师视图

```text
## 👨‍🏫 教师备课视图（HSKx · <题型名>）

【教学信息】
等级：HSKx（CEFR 对应，词汇量 x 词，书写字 x 字）
大纲写作能力：<writing_guide.md 第三节该等级原文>
话题树位置：<一级> > <二级> > <三级>（话题未命中时注明映射）
对应考试：<题型> ≥<字数>字

【参考范文】（约 xxx 字）
<标题 + 分段正文，格式同学生日常作文>

【范文结构】
<开头-主体-结尾 或 图1→图4 的推进说明>

【评分要点】
- <rubric 逐条>

【教学建议】
- <1-2 条，英文或中文按 feedback_language>

【级控检查】
- 词汇：目标等级以下词汇为主体，生词 x 个已★标注
- 语法：符合本级语法边界
- 字数：xxx 字（达标/未达标）

### 📄 HTML 学习页
File: essay_话题_HSKx.html — 从项目文件打开
```

---

## 通用规则（级控）

1. **词汇边界与生词定义**：**生词 = 目标等级及以上词汇**（如用户指定 HSK5，则 HSK5、HSK6、HSK7-9 级词汇及词表查不到的词均为生词；杜绝把更低等级词汇误收入生词表）。范文正文以目标等级**以下**词汇为主体书写（HSK5 范文尽量用 HSK1-4），不可避免用到生词时一律 ★ 标注并列入【生词表】；拿不准用 `hsk_lookup.py` 查，查不到即按生词处理（宁标勿漏）
2. **语法边界**：只用该等级及以下语法点（见 writing_guide.md 第四节）；HSK3 以下不用把字句/被字句，HSK4 以下不用"随着…的发展"类书面框架
3. **字数达标**：正文达到题型最少字数
4. **结构完整**：按题型结构组织

## Error Handling

- 输入为空或非中文：用英文请用户给中文
- 没找到等级：问 "What is your HSK level?"
- 脚本失败/词表缺失：不阻塞输出，范文照常给出（生词按"宁标勿漏"人工判断），并提示"词汇核查暂不可用"
- 话题不在话题树：映射到最接近的话题支，不报错（见 Feature 1 Step 3）
- 用户要求改写/润色已有作文：这是"作文批改"需求，本技能不覆盖，礼貌告知（或引导到其他技能）
- HTML 生成失败：文本视图照常输出，注明"HTML 学习页暂不可用"；绝不编造 HTML、绝不展示原始报错（见 Feature 2 Step 7）
- 绝不向用户展示原始报错信息
