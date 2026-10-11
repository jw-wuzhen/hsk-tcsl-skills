---
name: hsk-conversation-generator-tcsl
description: "基于新版HSK大纲（2026年7月实施）的对话材料生成器，面向国际中文学习者（TCSL）与教师。生成三种口语教学材料：场景对话脚本、话题问题卡（热身/核心/拓展三级递进）、角色扮演任务卡（A/B角色+任务目标+语言要求+参考表达）。任意话题均可处理：先在大纲话题树中定位，再按等级语言边界生成；超纲词自动★标注并附拼音+母语翻译；HSK1-3可带英文支架。当用户需要HSK口语练习、对话教学材料、课堂讨论问题、角色扮演活动时调用。 | A dialogue-material generator built on the new HSK syllabus (effective July 2026) for international Chinese learners (TCSL) and teachers. Produces scene dialogue scripts, topic discussion cards, and role-play task cards for any topic at any level."
---

# HSK 对话材料生成器 — TCSL 版 v2.0

基于新版HSK考试大纲（2026年7月实施）的口语教学材料生成器，面向国际中文学习者与教师。

三种材料类型：
1. **场景对话脚本**（dialogue_script）——分级对话 + 关键词 + 超纲词注释 + 学后任务
2. **话题问题卡**（discussion_cards）——热身/核心/拓展三级递进，每卡带教师提示
3. **角色扮演任务卡**（roleplay_cards）——情景 + 角色A/B + 任务目标 + 语言要求 + 参考表达

## Language Rules

Target users: English-speaking Chinese learners (international students).
- 中文文本、拼音、中文释义：保持中文
- 语法/教学术语：英文（括号附中文），如 Topic (话题)
- 材料正文（对话台词、关键词、参考表达）：**纯中文，永不翻译**
- 指令性文本（题目、提示、任务要求、学后任务）：默认英文在上、中文在下（`scaffold_language=en` 且 HSK1-3 时）；`scaffold_language=zh` 时全中文
- 询问等级："What is your HSK level?"

## 三种材料速查

| 类型 (material_type) | 内容 | 适用 |
|----------------------|------|------|
| `dialogue_script` | 场景+人物+对话+关键词+学后任务 | 朗读、复述、替换练习 |
| `discussion_cards` | 6级递进问题卡（数量可调 1-6） | 课堂讨论、问答练习 |
| `roleplay_cards` | 情景+角色+任务+语言要求 | 情景表演、交际训练 |

---

## Feature 1: 场景对话脚本

**Trigger**: 对话、对话材料、场景对话、dialogue、conversation、口语材料
**Input**: HSK level (required) + topic (optional) + native_language (optional)

### Step 1: 确定 HSK 等级

**⚠️ 最重要：先扫描用户消息中的等级，找到就不要再问。**

扫描模式（不区分大小写）：
- "HSK" + 数字 1-6（如 HSK6、HSK 3、hsk4）
- "等级" + 数字 1-6（如 等级5）
- 数字 1-6 + "级"（如 2级）
- "level" + 数字 1-6（如 level3）

找到 → 直接使用，进入 Step 2。**绝不再问。**
没找到 → 问 "What is your HSK level?"

示例：
- "HSK2问路对话" → 等级 HSK2、话题 问路 → 直接执行
- "给我一个春节的角色扮演" → 等级没给 → 先问等级
- "HSK5关于人工智能的讨论问题，5张" → 等级 HSK5、类型 discussion_cards、话题 人工智能、数量 5 → 直接执行

### Step 2: 话题定位（任意话题都支持）

1. 读取 `<skill_root>/reference/topic_tree.md`，把话题定位到树上：等级 > 一级 > 二级 > 三级
2. 话题在树内 → 按原话题生成
3. **话题不在树内**（如"太空旅行"）→ 不要报错！选择话题树中最接近的一支（如"科技发展"），对话围绕该支展开；教师视图注明"话题已映射到：XX（原话题：XX）"
4. 用户没给话题 → 从该等级话题树中选一个高频话题（如 HSK1 自我介绍、HSK3 点餐、HSK5 环境保护）

### Step 3: 确定语言边界

读取 `<skill_root>/reference/speaking_guide.md` 第三、四节，确定该等级的：
- 语法边界（HSK1 主谓句/是字句/有字句；HSK3 起才用把字句、被字句；HSK5 起用书面表达）
- 句长边界（HSK1 每句 ≤8 字，HSK2 ≤14 字，HSK3 ≤18 字，HSK4 ≤22 字，HSK5 ≤28 字，HSK6 ≤35 字）
- 交际功能（打招呼、问路、点餐、看病、谈看法……）

### Step 4: 生成对话

1. 参照 `<skill_root>/reference/model_dialogues/<level>.md` 中同等级对话的风格：台词简短自然、贴近真实交际、两人对话 6-12 轮
2. 按话题定位的场景展开（场景 + 人物 2-3 人 + 交际功能）
3. 台词只用本等级词汇和语法；不可避免的超纲词先正常写出，Step 5 统一标注
4. 附学后任务（复述/表演/替换练习，HSK1-2 配英文）

### Step 5: 级控检查与超纲词标注

1. 从台词中挑出 10-20 个最没把握的词（高级名词、动词、形容词）
2. 运行查词脚本：
   ```bash
   python3 <skill_root>/scripts/hsk_lookup.py --words "词1,词2,..."
   ```
3. 处理规则：
   - 词的等级 ≤ 学生等级 → 正常使用
   - 词的等级 > 学生等级，或词表查不到 → **超纲词**：台词中用 ★ 包起来（如 ★春联★），并在【超纲词注释】块给出 拼音 + 母语翻译
   - 结构助词和标点跳过
4. 对话中不要堆超纲词：同一意思优先换本等级词（如"采购"→"买"）

### Step 6: 英文支架（仅 HSK1-3 且 scaffold_language=en）

- 只给**指令性文本**加英文：场景、人物说明、学后任务（中文在上、英文在下）
- **台词保持纯中文**，不翻译、不标注
- HSK1-2：指令中的难词 ★ 标注 + 英文释义

### Step 7: 输出

按"输出模板"输出学生视图 + 教师视图。

---

## Feature 2: 话题问题卡

**Trigger**: 问题卡、讨论问题、讨论卡、课堂讨论、discussion、question cards、talk about
**Input**: HSK level (required) + topic (optional) + count (optional, 1-6 张)

### Step 1-2: 确定等级与话题

同 Feature 1 Step 1-2。

### Step 3: 分级设问

读取 `<skill_root>/reference/speaking_guide.md` 第四节，按等级确定问题类型：
- HSK1 是非问答（你叫什么名字？你喜欢什么？）
- HSK2 加 为什么、打算、觉得
- HSK3 加 如果……就、比较、经历叙述
- HSK4 加 看法+理由、建议、评价
- HSK5 加 观点论证、对比分析
- HSK6 加 抽象议题、深层分析

参照 `<skill_root>/reference/discussion_cards/<level>.md` 中同等级卡组的问题风格。

### Step 4: 组装卡片

- 数量：默认 4 张（用户指定 1-6 张则按数量）；不足 6 张时按 warmup → core → extended 顺序截取
- 每张卡 = **warmup（热身）/ core（核心）/ extended（拓展）** + 问题 + **教师提示（答题框架）**——教师提示必须有，学生才有支架
- 问题只用本等级句式；难词照 Feature 1 Step 5 标注

### Step 5: 输出

按"输出模板 · 问题卡"输出。

---

## Feature 3: 角色扮演任务卡

**Trigger**: 角色扮演、角色扮演任务、role play、情景表演、分角色
**Input**: HSK level (required) + topic (optional)

### Step 1-2: 确定等级与话题

同 Feature 1 Step 1-2。

### Step 3: 组装任务卡

参照 `<skill_root>/reference/roleplay_cards/<level>.md` 中同等级任务卡的结构：
1. **情景**：一句话说清场景（谁、在哪、要做什么）
2. **角色A/B**：A 通常是学生自己，B 是对话对象；给身份和立场
3. **任务目标**：用一句话说清双方要达成的结果（如"互相认识：问名字、问国籍"、"各说3个理由，最后达成共识"）
4. **语言要求**：点名 2-4 个本等级句型/表达（HSK2 用"打算/因为…所以"，HSK4 用"不但…而且"，HSK6 用"在…的同时"）——这是教学价值所在
5. **参考表达**：3-6 个本等级短语
6. **表演时间**：HSK1-2 3-5 分钟，HSK3-4 5-8 分钟，HSK5-6 10-12 分钟

### Step 4: 输出

按"输出模板 · 角色扮演卡"输出。

---

## 输出模板

### 学生视图 · 场景对话

```text
【场景对话】
《<标题>》

【场景】<场景>（English below for HSK1-3 with scaffolding）
【人物】<人物1>、<人物2>

【对话】
  <人物1>：<台词>
  <人物2>：<台词>
  ……

【关键词】<关键词1>、<关键词2>、……

【学后任务】<任务>
（English below for HSK1-3 with scaffolding）

【超纲词注释】（★标记的词超过本等级词汇，请先解释再使用）
  ★春联★ 拼音：chūnlián　释义：Spring Festival couplets
```

### 学生视图 · 问题卡

```text
【话题问题卡】
话题：<话题>

卡1【热身】<问题>
卡2【核心】<问题>
卡3【核心】<问题>
卡4【拓展】<问题>
```

### 学生视图 · 角色扮演

```text
【角色扮演任务卡】
《<标题>》

【情景】<情景>
【角色A】<你：……>
【角色B】<对方：……>
【任务目标】<一句话目标>
【语言要求】
  · 用"<句型1>"
  · 用"<句型2>"
  · <补充要求>
【参考表达】<表达1> / <表达2> / <表达3>
【表演时间】<时长>
```

### 教师视图（三种材料通用）

```text
【教学信息】
等级：HSKx（CEFR 对应，词汇量 x 词，书写字 x 字）
大纲"说"能力要求：<speaking_guide.md 第二节该等级原文>
话题树位置：<一级> > <二级> > <三级>（话题未命中时注明映射）
交际功能：<功能>

【教学组织流程】
热身（5分钟）→ 核心活动（15分钟）→ 拓展/表演（10分钟）→ 总结

【评分要点】
- <按等级列 3-5 条：语音、词汇使用、句子完整、交际达成……>

【词汇核查】
- 超纲词 x 个（★标注并注释）：<词1>（HSKx）、<词2>（超纲）……
```

---

## 通用规则（级控）

1. **词汇边界**：台词/问题/参考表达只用该等级及以下词汇；拿不准用 `hsk_lookup.py` 查，查不到即按超纲处理（宁标勿漏）
2. **语法边界**：只用该等级及以下语法点（speaking_guide.md 第三节）；HSK1-2 不用把字句、被字句
3. **句长边界**：HSK1 每句 ≤8 字 → HSK6 ≤35 字，逐级放宽
4. **支架边界**：只支架指令性文本，学习目标文本（台词、关键词、参考表达）永不翻译
5. **话题边界**：话题先定位话题树；树外话题映射到最接近支，不报错

## Error Handling

- 输入为空或非中文：用英文请用户给中文
- 没找到等级：问 "What is your HSK level?"
- 脚本失败/词表缺失：不阻塞输出，材料照常给出（超纲词按"宁标勿漏"人工判断），并提示"词汇核查暂不可用"
- 话题不在话题树：映射到最接近话题支，不报错（见 Feature 1 Step 2）
- 用户要求其他技能范围（写作、语法分析等）：礼貌告知范围
- 绝不向用户展示原始报错信息
