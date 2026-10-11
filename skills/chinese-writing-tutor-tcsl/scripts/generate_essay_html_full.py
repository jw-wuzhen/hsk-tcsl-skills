1	#!/usr/bin/env python3
2	# -*- coding: utf-8 -*-
3	"""All-in-one script: read essay text + good expressions, generate annotated HTML.
4	
5	Usage:
6	    python3 generate_essay_html.py --essay-file essay.txt --expressions-json expr.json --output essay_旅行_HSK6.html --hsk-level 6
7	
8	Or pipe essay text:
9	    echo "essay text" | python3 generate_essay_html.py --expressions-json expr.json --output out.html --hsk-level 6
10	
11	The script:
12	1. Loads HSK vocabulary from CSV files (levels 1-6)
13	2. Segments essay text using longest-match against HSK vocab + common words
14	3. Annotates each word with pinyin, HSK level, English definition
15	4. Highlights good expressions
16	5. Generates a beautiful standalone HTML file
17	"""
18	import sys
19	import os
20	import re
21	import json
22	import argparse
23	import html as html_module
24	import unicodedata
25	
26	
27	def normalize_pinyin(py):
28	    """Ensure tone marks are precomposed (NFC), not separate combining characters."""
29	    if not py:
30	        return ""
31	    return unicodedata.normalize("NFC", py)
32	
33	# === HSK Vocabulary Loading ===
34	
35	HSK_COLORS = {
36	    1: "#e74c3c", 2: "#e67e22", 3: "#f39c12",
37	    4: "#27ae60", 5: "#2980b9", 6: "#8e44ad",
38	}
39	HSK_LIGHT_BG = {
40	    1: "#fef5f5", 2: "#fef9f3", 3: "#fefcf5",
41	    4: "#f3faf5", 5: "#f3f8fd", 6: "#f8f5fd",
42	}
43	HSK_LABELS = {1: "HSK 1", 2: "HSK 2", 3: "HSK 3", 4: "HSK 4", 5: "HSK 5", 6: "HSK 6"}
44	
45	
46	def load_hsk_vocab(vocab_dir):
47	    """Load all HSK vocabulary from CSV files. Returns dict: word -> {hsk, pinyin, en_def, pos}
48	    Also extracts individual character pinyin from multi-char words.
49	    """
50	    vocab = {}
51	    char_pinyin = {}  # char -> pinyin (for fallback)
52	
53	    for level in range(1, 7):
54	        csv_path = os.path.join(vocab_dir, f"HSK{level}.csv")
55	        if not os.path.exists(csv_path):
56	            continue
57	        with open(csv_path, encoding="utf-8-sig") as f:
58	            lines = f.readlines()
59	            if len(lines) < 2:
60	                continue
61	            header = lines[0].strip().split(",")
62	            idx_simplified = header.index("简体") if "简体" in header else 2
63	            idx_pinyin = header.index("拼音") if "拼音" in header else 4
64	            idx_en = header.index("英文释义") if "英文释义" in header else 8
65	            idx_pos = header.index("词性") if "词性" in header else 6
66	
67	            for line in lines[1:]:
68	                parts = line.strip().split(",")
69	                if len(parts) <= max(idx_simplified, idx_pinyin, idx_en, idx_pos):
70	                    continue
71	                word = parts[idx_simplified].strip()
72	                if not word:
73	                    continue
74	                pinyin_raw = parts[idx_pinyin].strip()
75	                pinyin_nfc = normalize_pinyin(pinyin_raw)
76	
77	                if word not in vocab:
78	                    vocab[word] = {
79	                        "hsk": level,
80	                        "pinyin": pinyin_nfc,
81	                        "en_def": parts[idx_en].strip() if parts[idx_en].strip() else "",
82	                        "pos": parts[idx_pos].strip() if idx_pos < len(parts) else "",
83	                    }
84	
85	                # Extract individual character pinyin from multi-char words
86	                syllables = pinyin_nfc.split()
87	                if len(syllables) == len(word) and len(word) > 1:
88	                    for ch, syl in zip(word, syllables):
89	                        if "\u4e00" <= ch <= "\u9fff" and ch not in char_pinyin:
90	                            char_pinyin[ch] = syl
91	                elif len(word) == 1 and pinyin_nfc:
92	                    if word not in char_pinyin:
93	                        char_pinyin[word] = pinyin_nfc
94	
95	    # Also load char_pinyin.json if it exists (pre-generated comprehensive mapping)
96	    char_pinyin_path = os.path.join(vocab_dir, "..", "char_pinyin.json")
97	    if os.path.exists(char_pinyin_path):
98	        with open(char_pinyin_path, encoding="utf-8") as f:
99	            extra = json.load(f)
100	            for ch, py in extra.items():
101	                py_nfc = normalize_pinyin(py)
102	                if ch not in char_pinyin:
103	                    char_pinyin[ch] = py_nfc
104	
105	    # Merge char_pinyin into vocab as single-char entries (don't override existing)
106	    for ch, py in char_pinyin.items():
107	        if ch not in vocab:
108	            vocab[ch] = {"hsk": 0, "pinyin": py, "en_def": "", "pos": ""}
109	
110	    return vocab
111	
112	
113	def segment_text(text, vocab):
114	    """Segment Chinese text using longest-match against HSK vocab.
115	    Returns list of (word, is_punctuation) tuples.
116	    """
117	    # Common function words and particles not always in HSK list
118	    common_words = {
119	        "的": {"hsk": 1, "pinyin": "de", "en_def": "structural particle", "pos": "part"},
120	        "了": {"hsk": 1, "pinyin": "le", "en_def": "completed action", "pos": "part"},
121	        "是": {"hsk": 1, "pinyin": "shì", "en_def": "is; to be", "pos": "v"},
122	        "在": {"hsk": 1, "pinyin": "zài", "en_def": "at; in; on", "pos": "prep"},
123	        "有": {"hsk": 1, "pinyin": "yǒu", "en_def": "to have", "pos": "v"},
124	        "不": {"hsk": 1, "pinyin": "bù", "en_def": "not", "pos": "adv"},
125	        "我": {"hsk": 1, "pinyin": "wǒ", "en_def": "I; me", "pos": "pron"},
126	        "你": {"hsk": 1, "pinyin": "nǐ", "en_def": "you", "pos": "pron"},
127	        "他": {"hsk": 1, "pinyin": "tā", "en_def": "he; him", "pos": "pron"},
128	        "她": {"hsk": 1, "pinyin": "tā", "en_def": "she; her", "pos": "pron"},
129	        "们": {"hsk": 1, "pinyin": "men", "en_def": "plural marker", "pos": "suffix"},
130	        "和": {"hsk": 1, "pinyin": "hé", "en_def": "and", "pos": "conj"},
131	        "就": {"hsk": 2, "pinyin": "jiù", "en_def": "then; just", "pos": "adv"},
132	        "都": {"hsk": 2, "pinyin": "dōu", "en_def": "all; both", "pos": "adv"},
133	        "也": {"hsk": 1, "pinyin": "yě", "en_def": "also; too", "pos": "adv"},
134	        "这": {"hsk": 1, "pinyin": "zhè", "en_def": "this", "pos": "pron"},
135	        "那": {"hsk": 1, "pinyin": "nà", "en_def": "that", "pos": "pron"},
136	        "要": {"hsk": 1, "pinyin": "yào", "en_def": "to want; to need", "pos": "v"},
137	        "会": {"hsk": 1, "pinyin": "huì", "en_def": "can; will", "pos": "v"},
138	        "能": {"hsk": 2, "pinyin": "néng", "en_def": "can; able to", "pos": "v"},
139	        "着": {"hsk": 2, "pinyin": "zhe", "en_def": "particle for ongoing action", "pos": "part"},
140	        "过": {"hsk": 2, "pinyin": "guò", "en_def": "particle for past experience", "pos": "part"},
141	        "把": {"hsk": 3, "pinyin": "bǎ", "en_def": "object marker", "pos": "prep"},
142	        "被": {"hsk": 3, "pinyin": "bèi", "en_def": "passive marker", "pos": "prep"},
143	        "让": {"hsk": 3, "pinyin": "ràng", "en_def": "to let; to allow", "pos": "v"},
144	        "给": {"hsk": 1, "pinyin": "gěi", "en_def": "to give; for", "pos": "v"},
145	        "对": {"hsk": 1, "pinyin": "duì", "en_def": "to; toward; correct", "pos": "prep"},
146	        "从": {"hsk": 2, "pinyin": "cóng", "en_def": "from", "pos": "prep"},
147	        "到": {"hsk": 1, "pinyin": "dào", "en_def": "to; until; arrive", "pos": "v"},
148	        "里": {"hsk": 1, "pinyin": "lǐ", "en_def": "in; inside", "pos": "n"},
149	        "上": {"hsk": 1, "pinyin": "shàng", "en_def": "on; above", "pos": "n"},
150	        "下": {"hsk": 1, "pinyin": "xià", "en_def": "down; below", "pos": "n"},
151	        "中": {"hsk": 2, "pinyin": "zhōng", "en_def": "in; among", "pos": "n"},
152	        "地": {"hsk": 2, "pinyin": "de", "en_def": "adverb marker", "pos": "part"},
153	        "得": {"hsk": 2, "pinyin": "de", "en_def": "complement marker", "pos": "part"},
154	        "又": {"hsk": 2, "pinyin": "yòu", "en_def": "again; also", "pos": "adv"},
155	        "还": {"hsk": 2, "pinyin": "hái", "en_def": "still; also", "pos": "adv"},
156	        "很": {"hsk": 1, "pinyin": "hěn", "en_def": "very", "pos": "adv"},
157	        "但": {"hsk": 3, "pinyin": "dàn", "en_def": "but; however", "pos": "conj"},
158	        "而": {"hsk": 3, "pinyin": "ér", "en_def": "and; but", "pos": "conj"},
159	        "与": {"hsk": 3, "pinyin": "yǔ", "en_def": "and; with", "pos": "conj"},
160	        "或": {"hsk": 3, "pinyin": "huò", "en_def": "or", "pos": "conj"},
161	        "已": {"hsk": 3, "pinyin": "yǐ", "en_def": "already", "pos": "adv"},
162	        "才": {"hsk": 3, "pinyin": "cái", "en_def": "just; only then", "pos": "adv"},
163	        "再": {"hsk": 2, "pinyin": "zài", "en_def": "again; once more", "pos": "adv"},
164	        "只": {"hsk": 2, "pinyin": "zhǐ", "en_def": "only; just", "pos": "adv"},
165	        "一": {"hsk": 1, "pinyin": "yī", "en_def": "one", "pos": "num"},
166	        "个": {"hsk": 1, "pinyin": "gè", "en_def": "measure word", "pos": "measure"},
167	        "人": {"hsk": 1, "pinyin": "rén", "en_def": "person; people", "pos": "n"},
168	        "大": {"hsk": 1, "pinyin": "dà", "en_def": "big; large", "pos": "a"},
169	        "小": {"hsk": 1, "pinyin": "xiǎo", "en_def": "small; little", "pos": "a"},
170	        "多": {"hsk": 1, "pinyin": "duō", "en_def": "many; much", "pos": "a"},
171	        "少": {"hsk": 1, "pinyin": "shǎo", "en_def": "few; less", "pos": "a"},
172	        "好": {"hsk": 1, "pinyin": "hǎo", "en_def": "good", "pos": "a"},
173	        "来": {"hsk": 1, "pinyin": "lái", "en_def": "to come", "pos": "v"},
174	        "去": {"hsk": 1, "pinyin": "qù", "en_def": "to go", "pos": "v"},
175	        "看": {"hsk": 1, "pinyin": "kàn", "en_def": "to see; to look", "pos": "v"},
176	        "说": {"hsk": 1, "pinyin": "shuō", "en_def": "to say; to speak", "pos": "v"},
177	        "做": {"hsk": 2, "pinyin": "zuò", "en_def": "to do; to make", "pos": "v"},
178	        "想": {"hsk": 1, "pinyin": "xiǎng", "en_def": "to think; to want", "pos": "v"},
179	        "它": {"hsk": 1, "pinyin": "tā", "en_def": "it", "pos": "pron"},
180	        "为": {"hsk": 2, "pinyin": "wèi", "en_def": "for; because of", "pos": "prep"},
181	        "所": {"hsk": 3, "pinyin": "suǒ", "en_def": "that which", "pos": "pron"},
182	        "以": {"hsk": 2, "pinyin": "yǐ", "en_def": "by means of; with", "pos": "prep"},
183	        "可": {"hsk": 2, "pinyin": "kě", "en_def": "can; may", "pos": "v"},
184	        "个": {"hsk": 1, "pinyin": "gè", "en_def": "general measure word", "pos": "measure"},
185	        "吧": {"hsk": 1, "pinyin": "ba", "en_def": "particle (suggestion)", "pos": "part"},
186	        "呢": {"hsk": 1, "pinyin": "ne", "en_def": "particle (question)", "pos": "part"},
187	        "啊": {"hsk": 2, "pinyin": "a", "en_def": "particle (emotion)", "pos": "part"},
188	        "吗": {"hsk": 1, "pinyin": "ma", "en_def": "particle (yes/no question)", "pos": "part"},
189	        # Common single chars that appear in compound words
190	        "美": {"hsk": 0, "pinyin": "měi", "en_def": "beautiful", "pos": "a"},
191	        "丽": {"hsk": 0, "pinyin": "lì", "en_def": "beautiful", "pos": "a"},
192	        "福": {"hsk": 0, "pinyin": "fú", "en_def": "fortune; blessing", "pos": "n"},
193	        "景": {"hsk": 0, "pinyin": "jǐng", "en_def": "scenery; view", "pos": "n"},
194	        "情": {"hsk": 0, "pinyin": "qíng", "en_def": "feeling; emotion", "pos": "n"},
195	        "事": {"hsk": 0, "pinyin": "shì", "en_def": "thing; matter", "pos": "n"},
196	        "物": {"hsk": 0, "pinyin": "wù", "en_def": "thing; object", "pos": "n"},
197	        "心": {"hsk": 1, "pinyin": "xīn", "en_def": "heart", "pos": "n"},
198	        "力": {"hsk": 1, "pinyin": "lì", "en_def": "power; force", "pos": "n"},
199	        "道": {"hsk": 2, "pinyin": "dào", "en_def": "way; road; to say", "pos": "n"},
200	        "理": {"hsk": 0, "pinyin": "lǐ", "en_def": "reason; logic", "pos": "n"},
201	        "明": {"hsk": 1, "pinyin": "míng", "en_def": "bright; clear", "pos": "a"},
202	        "天": {"hsk": 1, "pinyin": "tiān", "en_def": "sky; day", "pos": "n"},
203	        "地": {"hsk": 1, "pinyin": "dì", "en_def": "earth; ground", "pos": "n"},
204	        "日": {"hsk": 1, "pinyin": "rì", "en_def": "sun; day", "pos": "n"},
205	        "月": {"hsk": 1, "pinyin": "yuè", "en_def": "moon; month", "pos": "n"},
206	        "年": {"hsk": 1, "pinyin": "nián", "en_def": "year", "pos": "n"},
207	        "时": {"hsk": 1, "pinyin": "shí", "en_def": "time", "pos": "n"},
208	        "分": {"hsk": 1, "pinyin": "fēn", "en_def": "minute; to divide", "pos": "n"},
209	        "点": {"hsk": 1, "pinyin": "diǎn", "en_def": "point; o'clock", "pos": "n"},
210	        "话": {"hsk": 1, "pinyin": "huà", "en_def": "speech; words", "pos": "n"},
211	        "字": {"hsk": 1, "pinyin": "zì", "en_def": "character; word", "pos": "n"},
212	        "书": {"hsk": 1, "pinyin": "shū", "en_def": "book", "pos": "n"},
213	        "手": {"hsk": 1, "pinyin": "shǒu", "en_def": "hand", "pos": "n"},
214	        "目": {"hsk": 0, "pinyin": "mù", "en_def": "eye; item", "pos": "n"},
215	        "口": {"hsk": 1, "pinyin": "kǒu", "en_def": "mouth; entrance", "pos": "n"},
216	        "门": {"hsk": 1, "pinyin": "mén", "en_def": "door; gate", "pos": "n"},
217	        "路": {"hsk": 1, "pinyin": "lù", "en_def": "road; way", "pos": "n"},
218	        "头": {"hsk": 1, "pinyin": "tóu", "en_def": "head", "pos": "n"},
219	        "长": {"hsk": 1, "pinyin": "cháng", "en_def": "long", "pos": "a"},
220	        "高": {"hsk": 1, "pinyin": "gāo", "en_def": "tall; high", "pos": "a"},
221	        "低": {"hsk": 0, "pinyin": "dī", "en_def": "low", "pos": "a"},
222	        "快": {"hsk": 1, "pinyin": "kuài", "en_def": "fast; quick", "pos": "a"},
223	        "慢": {"hsk": 0, "pinyin": "màn", "en_def": "slow", "pos": "a"},
224	        "远": {"hsk": 2, "pinyin": "yuǎn", "en_def": "far", "pos": "a"},
225	        "近": {"hsk": 2, "pinyin": "jìn", "en_def": "near", "pos": "a"},
226	        "重": {"hsk": 2, "pinyin": "zhòng", "en_def": "heavy; important", "pos": "a"},
227	        "轻": {"hsk": 0, "pinyin": "qīng", "en_def": "light", "pos": "a"},
228	        "深": {"hsk": 2, "pinyin": "shēn", "en_def": "deep", "pos": "a"},
229	        "浅": {"hsk": 0, "pinyin": "qiǎn", "en_def": "shallow", "pos": "a"},
230	        "真": {"hsk": 1, "pinyin": "zhēn", "en_def": "true; real", "pos": "a"},
231	        "假": {"hsk": 0, "pinyin": "jiǎ", "en_def": "fake; false", "pos": "a"},
232	        "老": {"hsk": 1, "pinyin": "lǎo", "en_def": "old", "pos": "a"},
233	        "新": {"hsk": 1, "pinyin": "xīn", "en_def": "new", "pos": "a"},
234	        "早": {"hsk": 1, "pinyin": "zǎo", "en_def": "early", "pos": "a"},
235	        "晚": {"hsk": 1, "pinyin": "wǎn", "en_def": "late; evening", "pos": "a"},
236	        "前": {"hsk": 1, "pinyin": "qián", "en_def": "front; before", "pos": "n"},
237	        "后": {"hsk": 1, "pinyin": "hòu", "en_def": "back; after", "pos": "n"},
238	        "左": {"hsk": 1, "pinyin": "zuǒ", "en_def": "left", "pos": "n"},
239	        "右": {"hsk": 1, "pinyin": "yòu", "en_def": "right", "pos": "n"},
240	        "内": {"hsk": 2, "pinyin": "nèi", "en_def": "inside", "pos": "n"},
241	        "外": {"hsk": 1, "pinyin": "wài", "en_def": "outside", "pos": "n"},
242	        "东": {"hsk": 1, "pinyin": "dōng", "en_def": "east", "pos": "n"},
243	        "西": {"hsk": 1, "pinyin": "xī", "en_def": "west", "pos": "n"},
244	        "南": {"hsk": 1, "pinyin": "nán", "en_def": "south", "pos": "n"},
245	        "北": {"hsk": 1, "pinyin": "běi", "en_def": "north", "pos": "n"},
246	        "声": {"hsk": 1, "pinyin": "shēng", "en_def": "sound; voice", "pos": "n"},
247	        "色": {"hsk": 1, "pinyin": "sè", "en_def": "color", "pos": "n"},
248	        "光": {"hsk": 1, "pinyin": "guāng", "en_def": "light", "pos": "n"},
249	        "风": {"hsk": 1, "pinyin": "fēng", "en_def": "wind", "pos": "n"},
250	        "雨": {"hsk": 1, "pinyin": "yǔ", "en_def": "rain", "pos": "n"},
251	        "云": {"hsk": 1, "pinyin": "yún", "en_def": "cloud", "pos": "n"},
252	        "水": {"hsk": 1, "pinyin": "shuǐ", "en_def": "water", "pos": "n"},
253	        "火": {"hsk": 1, "pinyin": "huǒ", "en_def": "fire", "pos": "n"},
254	        "山": {"hsk": 1, "pinyin": "shān", "en_def": "mountain", "pos": "n"},
255	        "河": {"hsk": 1, "pinyin": "hé", "en_def": "river", "pos": "n"},
256	        "花": {"hsk": 1, "pinyin": "huā", "en_def": "flower", "pos": "n"},
257	        "草": {"hsk": 0, "pinyin": "cǎo", "en_def": "grass", "pos": "n"},
258	        "树": {"hsk": 1, "pinyin": "shù", "en_def": "tree", "pos": "n"},
259	        "叶": {"hsk": 0, "pinyin": "yè", "en_def": "leaf", "pos": "n"},
260	        "鸟": {"hsk": 1, "pinyin": "niǎo", "en_def": "bird", "pos": "n"},
261	        "鱼": {"hsk": 1, "pinyin": "yú", "en_def": "fish", "pos": "n"},
262	        "马": {"hsk": 1, "pinyin": "mǎ", "en_def": "horse", "pos": "n"},
263	        "牛": {"hsk": 0, "pinyin": "niú", "en_def": "cow; ox", "pos": "n"},
264	        "羊": {"hsk": 0, "pinyin": "yáng", "en_def": "sheep", "pos": "n"},
265	        "虫": {"hsk": 0, "pinyin": "chóng", "en_def": "insect; bug", "pos": "n"},
266	        "走": {"hsk": 1, "pinyin": "zǒu", "en_def": "to walk; to go", "pos": "v"},
267	        "跑": {"hsk": 0, "pinyin": "pǎo", "en_def": "to run", "pos": "v"},
268	        "飞": {"hsk": 1, "pinyin": "fēi", "en_def": "to fly", "pos": "v"},
269	        "吃": {"hsk": 1, "pinyin": "chī", "en_def": "to eat", "pos": "v"},
270	        "喝": {"hsk": 1, "pinyin": "hē", "en_def": "to drink", "pos": "v"},
271	        "住": {"hsk": 1, "pinyin": "zhù", "en_def": "to live; to stay", "pos": "v"},
272	        "用": {"hsk": 1, "pinyin": "yòng", "en_def": "to use", "pos": "v"},
273	        "爱": {"hsk": 1, "pinyin": "ài", "en_def": "to love", "pos": "v"},
274	        "怕": {"hsk": 0, "pinyin": "pà", "en_def": "to fear", "pos": "v"},
275	        "笑": {"hsk": 2, "pinyin": "xiào", "en_def": "to laugh; smile", "pos": "v"},
276	        "哭": {"hsk": 0, "pinyin": "kū", "en_def": "to cry", "pos": "v"},
277	        "听": {"hsk": 1, "pinyin": "tīng", "en_def": "to listen; hear", "pos": "v"},
278	        "写": {"hsk": 1, "pinyin": "xiě", "en_def": "to write", "pos": "v"},
279	        "读": {"hsk": 2, "pinyin": "dú", "en_def": "to read", "pos": "v"},
280	        "学": {"hsk": 1, "pinyin": "xué", "en_def": "to learn; study", "pos": "v"},
281	        "教": {"hsk": 2, "pinyin": "jiāo", "en_def": "to teach", "pos": "v"},
282	        "买": {"hsk": 1, "pinyin": "mǎi", "en_def": "to buy", "pos": "v"},
283	        "卖": {"hsk": 2, "pinyin": "mài", "en_def": "to sell", "pos": "v"},
284	        "开": {"hsk": 1, "pinyin": "kāi", "en_def": "to open", "pos": "v"},
285	        "关": {"hsk": 1, "pinyin": "guān", "en_def": "to close; shut", "pos": "v"},
286	        "坐": {"hsk": 1, "pinyin": "zuò", "en_def": "to sit", "pos": "v"},
287	        "站": {"hsk": 2, "pinyin": "zhàn", "en_def": "to stand", "pos": "v"},
288	        "死": {"hsk": 2, "pinyin": "sǐ", "en_def": "to die", "pos": "v"},
289	        "活": {"hsk": 2, "pinyin": "huó", "en_def": "to live; alive", "pos": "v"},
290	        "白": {"hsk": 1, "pinyin": "bái", "en_def": "white", "pos": "a"},
291	        "黑": {"hsk": 1, "pinyin": "hēi", "en_def": "black", "pos": "a"},
292	        "红": {"hsk": 2, "pinyin": "hóng", "en_def": "red", "pos": "a"},
293	        "绿": {"hsk": 0, "pinyin": "lǜ", "en_def": "green", "pos": "a"},
294	        "蓝": {"hsk": 0, "pinyin": "lán", "en_def": "blue", "pos": "a"},
295	        "黄": {"hsk": 1, "pinyin": "huáng", "en_def": "yellow", "pos": "a"},
296	        "金": {"hsk": 2, "pinyin": "jīn", "en_def": "gold", "pos": "n"},
297	        "银": {"hsk": 0, "pinyin": "yín", "en_def": "silver", "pos": "n"},
298	        "铁": {"hsk": 0, "pinyin": "tiě", "en_def": "iron", "pos": "n"},
299	        "石": {"hsk": 0, "pinyin": "shí", "en_def": "stone; rock", "pos": "n"},
300	        "土": {"hsk": 0, "pinyin": "tǔ", "en_def": "earth; soil", "pos": "n"},
301	        "田": {"hsk": 0, "pinyin": "tián", "en_def": "field; farmland", "pos": "n"},
302	        "林": {"hsk": 0, "pinyin": "lín", "en_def": "forest; woods", "pos": "n"},
303	        "木": {"hsk": 0, "pinyin": "mù", "en_def": "wood; tree", "pos": "n"},
304	        "足": {"hsk": 0, "pinyin": "zú", "en_def": "foot; enough", "pos": "n"},
305	        "身": {"hsk": 0, "pinyin": "shēn", "en_def": "body", "pos": "n"},
306	        "体": {"hsk": 1, "pinyin": "tǐ", "en_def": "body", "pos": "n"},
307	        "面": {"hsk": 1, "pinyin": "miàn", "en_def": "face; side", "pos": "n"},
308	        "首": {"hsk": 0, "pinyin": "shǒu", "en_def": "head; first", "pos": "n"},
309	        "半": {"hsk": 2, "pinyin": "bàn", "en_def": "half", "pos": "num"},
310	        "双": {"hsk": 0, "pinyin": "shuāng", "en_def": "pair; double", "pos": "num"},
311	        "万": {"hsk": 1, "pinyin": "wàn", "en_def": "ten thousand", "pos": "num"},
312	        "千": {"hsk": 1, "pinyin": "qiān", "en_def": "thousand", "pos": "num"},
313	        "百": {"hsk": 1, "pinyin": "bǎi", "en_def": "hundred", "pos": "num"},
314	        "十": {"hsk": 1, "pinyin": "shí", "en_def": "ten", "pos": "num"},
315	        "两": {"hsk": 1, "pinyin": "liǎng", "en_def": "two", "pos": "num"},
316	        "第": {"hsk": 2, "pinyin": "dì", "en_def": "number prefix", "pos": "prefix"},
317	        "次": {"hsk": 1, "pinyin": "cì", "en_def": "time; order", "pos": "measure"},
318	        "回": {"hsk": 1, "pinyin": "huí", "en_def": "to return; time", "pos": "v"},
319	        "位": {"hsk": 1, "pinyin": "wèi", "en_def": "seat; position", "pos": "measure"},
320	        "本": {"hsk": 1, "pinyin": "běn", "en_def": "book; measure word", "pos": "measure"},
321	        "只": {"hsk": 1, "pinyin": "zhǐ", "en_def": "only; measure word", "pos": "measure"},
322	        "些": {"hsk": 2, "pinyin": "xiē", "en_def": "some; a few", "pos": "measure"},
323	        "每": {"hsk": 2, "pinyin": "měi", "en_def": "every; each", "pos": "pron"},
324	        "各": {"hsk": 3, "pinyin": "gè", "en_def": "each; every", "pos": "pron"},
325	        "另": {"hsk": 0, "pinyin": "lìng", "en_def": "another; other", "pos": "pron"},
326	        "别": {"hsk": 2, "pinyin": "bié", "en_def": "other; don't", "pos": "pron"},
327	        "其": {"hsk": 3, "pinyin": "qí", "en_def": "its; that", "pos": "pron"},
328	        "此": {"hsk": 0, "pinyin": "cǐ", "en_def": "this", "pos": "pron"},
329	        "若": {"hsk": 0, "pinyin": "ruò", "en_def": "if; as if", "pos": "conj"},
330	        "故": {"hsk": 0, "pinyin": "gù", "en_def": "therefore; old", "pos": "conj"},
331	        "虽": {"hsk": 0, "pinyin": "suī", "en_def": "although", "pos": "conj"},
332	        "因": {"hsk": 3, "pinyin": "yīn", "en_def": "cause; because", "pos": "prep"},
333	        "由": {"hsk": 3, "pinyin": "yóu", "en_def": "from; by", "pos": "prep"},
334	        "让": {"hsk": 3, "pinyin": "ràng", "en_def": "to let; allow", "pos": "v"},
335	        "使": {"hsk": 3, "pinyin": "shǐ", "en_def": "to make; cause", "pos": "v"},
336	        "令": {"hsk": 0, "pinyin": "lìng", "en_def": "to make; cause", "pos": "v"},
337	        "成": {"hsk": 2, "pinyin": "chéng", "en_def": "to become; succeed", "pos": "v"},
338	        "化": {"hsk": 0, "pinyin": "huà", "en_def": "to change; transform", "pos": "v"},
339	        "动": {"hsk": 2, "pinyin": "dòng", "en_def": "to move", "pos": "v"},
340	        "静": {"hsk": 0, "pinyin": "jìng", "en_def": "quiet; still", "pos": "a"},
341	        "安": {"hsk": 0, "pinyin": "ān", "en_def": "safe; peaceful", "pos": "a"},
342	        "全": {"hsk": 2, "pinyin": "quán", "en_def": "all; complete", "pos": "a"},
343	        "保": {"hsk": 0, "pinyin": "bǎo", "en_def": "to protect; keep", "pos": "v"},
344	        "持": {"hsk": 0, "pinyin": "chí", "en_def": "to hold; maintain", "pos": "v"},
345	        "生": {"hsk": 1, "pinyin": "shēng", "en_def": "to be born; life", "pos": "v"},
346	        "死": {"hsk": 2, "pinyin": "sǐ", "en_def": "to die; death", "pos": "v"},
347	        "平": {"hsk": 0, "pinyin": "píng", "en_def": "flat; peaceful", "pos": "a"},
348	        "正": {"hsk": 1, "pinyin": "zhèng", "en_def": "correct; straight", "pos": "a"},
349	        "反": {"hsk": 2, "pinyin": "fǎn", "en_def": "reverse; opposite", "pos": "a"},
350	        "同": {"hsk": 2, "pinyin": "tóng", "en_def": "same; together", "pos": "a"},
351	        "异": {"hsk": 0, "pinyin": "yì", "en_def": "different; strange", "pos": "a"},
352	        "特": {"hsk": 0, "pinyin": "tè", "en_def": "special; particular", "pos": "a"},
353	        "奇": {"hsk": 0, "pinyin": "qí", "en_def": "strange; wonder", "pos": "a"},
354	        "怪": {"hsk": 0, "pinyin": "guài", "en_def": "strange; to blame", "pos": "a"},
355	        "意": {"hsk": 0, "pinyin": "yì", "en_def": "meaning; intention", "pos": "n"},
356	        "义": {"hsk": 0, "pinyin": "yì", "en_def": "meaning; justice", "pos": "n"},
357	        "思": {"hsk": 1, "pinyin": "sī", "en_def": "to think; thought", "pos": "v"},
358	        "念": {"hsk": 0, "pinyin": "niàn", "en_def": "to miss; read", "pos": "v"},
359	        "记": {"hsk": 2, "pinyin": "jì", "en_def": "to remember; record", "pos": "v"},
360	        "忘": {"hsk": 0, "pinyin": "wàng", "en_def": "to forget", "pos": "v"},
361	        "感": {"hsk": 0, "pinyin": "gǎn", "en_def": "to feel; sense", "pos": "v"},
362	        "觉": {"hsk": 1, "pinyin": "jué", "en_def": "to feel; wake", "pos": "v"},
363	        "知": {"hsk": 2, "pinyin": "zhī", "en_def": "to know", "pos": "v"},
364	        "识": {"hsk": 0, "pinyin": "shí", "en_def": "to know; knowledge", "pos": "v"},
365	        "信": {"hsk": 2, "pinyin": "xìn", "en_def": "letter; trust", "pos": "n"},
366	        "望": {"hsk": 0, "pinyin": "wàng", "en_def": "to look; hope", "pos": "v"},
367	        "期": {"hsk": 0, "pinyin": "qī", "en_def": "period; hope", "pos": "n"},
368	        "待": {"hsk": 0, "pinyin": "dài", "en_def": "to wait; treat", "pos": "v"},
369	        "自": {"hsk": 2, "pinyin": "zì", "en_def": "self; from", "pos": "pron"},
370	        "己": {"hsk": 1, "pinyin": "jǐ", "en_def": "self", "pos": "pron"},
371	        "相": {"hsk": 3, "pinyin": "xiāng", "en_def": "mutually", "pos": "adv"},
372	        "比": {"hsk": 2, "pinyin": "bǐ", "en_def": "to compare", "pos": "v"},
373	        "较": {"hsk": 0, "pinyin": "jiào", "en_def": "to compare; relatively", "pos": "v"},
374	        "最": {"hsk": 2, "pinyin": "zuì", "en_def": "most", "pos": "adv"},
375	        "更": {"hsk": 2, "pinyin": "gèng", "en_def": "more; even more", "pos": "adv"},
376	        "太": {"hsk": 1, "pinyin": "tài", "en_def": "too; very", "pos": "adv"},
377	        "极": {"hsk": 0, "pinyin": "jí", "en_def": "extremely", "pos": "adv"},
378	        "非": {"hsk": 3, "pinyin": "fēi", "en_def": "not; non-", "pos": "adv"},
379	        "常": {"hsk": 1, "pinyin": "cháng", "en_def": "often; constant", "pos": "adv"},
380	        "须": {"hsk": 0, "pinyin": "xū", "en_def": "must; need", "pos": "v"},
381	        "需": {"hsk": 0, "pinyin": "xū", "en_def": "to need; require", "pos": "v"},
382	        "应": {"hsk": 0, "pinyin": "yīng", "en_def": "should; respond", "pos": "v"},
383	        "当": {"hsk": 0, "pinyin": "dāng", "en_def": "should; to be", "pos": "v"},
384	        "肯": {"hsk": 0, "pinyin": "kěn", "en_def": "willing; to agree", "pos": "v"},
385	        "敢": {"hsk": 0, "pinyin": "gǎn", "en_def": "to dare", "pos": "v"},
386	        "或": {"hsk": 3, "pinyin": "huò", "en_def": "or; perhaps", "pos": "conj"},
387	        "者": {"hsk": 0, "pinyin": "zhě", "en_def": "person who...", "pos": "suffix"},
388	        "的": {"hsk": 1, "pinyin": "de", "en_def": "possessive particle", "pos": "part"},
389	        "确": {"hsk": 0, "pinyin": "què", "en_def": "indeed; true", "pos": "a"},
390	        "实": {"hsk": 2, "pinyin": "shí", "en_def": "real; solid", "pos": "a"},
391	        "行": {"hsk": 2, "pinyin": "xíng", "en_def": "to go; OK", "pos": "v"},
392	        "止": {"hsk": 0, "pinyin": "zhǐ", "en_def": "to stop", "pos": "v"},
393	        "起": {"hsk": 2, "pinyin": "qǐ", "en_def": "to rise; start", "pos": "v"},
394	        "落": {"hsk": 0, "pinyin": "luò", "en_def": "to fall; drop", "pos": "v"},
395	        "转": {"hsk": 2, "pinyin": "zhuǎn", "en_def": "to turn; change", "pos": "v"},
396	        "换": {"hsk": 0, "pinyin": "huàn", "en_def": "to change; exchange", "pos": "v"},
397	        "接": {"hsk": 2, "pinyin": "jiē", "en_def": "to receive; connect", "pos": "v"},
398	        "受": {"hsk": 2, "pinyin": "shòu", "en_def": "to receive; accept", "pos": "v"},
399	        "给": {"hsk": 1, "pinyin": "gěi", "en_def": "to give", "pos": "v"},
400	        "取": {"hsk": 0, "pinyin": "qǔ", "en_def": "to take; get", "pos": "v"},
401	        "放": {"hsk": 1, "pinyin": "fàng", "en_def": "to put; release", "pos": "v"},
402	        "带": {"hsk": 2, "pinyin": "dài", "en_def": "to bring; carry", "pos": "v"},
403	        "拉": {"hsk": 0, "pinyin": "lā", "en_def": "to pull", "pos": "v"},
404	        "推": {"hsk": 0, "pinyin": "tuī", "en_def": "to push", "pos": "v"},
405	        "打": {"hsk": 1, "pinyin": "dǎ", "en_def": "to hit; play", "pos": "v"},
406	        "找": {"hsk": 1, "pinyin": "zhǎo", "en_def": "to look for; find", "pos": "v"},
407	        "穿": {"hsk": 2, "pinyin": "chuān", "en_def": "to wear; pierce", "pos": "v"},
408	        "戴": {"hsk": 0, "pinyin": "dài", "en_def": "to wear (accessories)", "pos": "v"},
409	        "洗": {"hsk": 0, "pinyin": "xǐ", "en_def": "to wash", "pos": "v"},
410	        "照": {"hsk": 2, "pinyin": "zhào", "en_def": "to shine; photo", "pos": "v"},
411	        "算": {"hsk": 0, "pinyin": "suàn", "en_def": "to calculate; count", "pos": "v"},
412	        "数": {"hsk": 1, "pinyin": "shù", "en_def": "number; to count", "pos": "n"},
413	        "量": {"hsk": 2, "pinyin": "liàng", "en_def": "quantity; amount", "pos": "n"},
414	        "度": {"hsk": 0, "pinyin": "dù", "en_def": "degree; extent", "pos": "n"},
415	        "线": {"hsk": 0, "pinyin": "xiàn", "en_def": "line; thread", "pos": "n"},
416	        "面": {"hsk": 1, "pinyin": "miàn", "en_def": "face; surface", "pos": "n"},
417	        "点": {"hsk": 1, "pinyin": "diǎn", "en_def": "point; dot", "pos": "n"},
418	    }
419	
420	    # Merge common words into vocab (don't override existing HSK entries)
421	    for word, info in common_words.items():
422	        if word not in vocab:
423	            info["pinyin"] = normalize_pinyin(info.get("pinyin", ""))
424	            vocab[word] = info
425	
426	    # Punctuation pattern
427	    punct_pattern = re.compile(r'[，。！？、；：""''「」（）()【】《》〈〉…—·,.!?;:\' \t\n\r…]')
428	
429	    n = len(text)
430	    if n == 0:
431	        return []
432	
433	    # === Dictionary-scan segmentation ===
434	    # Strategy: iterate over every word in HSK vocab (longest first),
435	    # find all occurrences in text, mark those positions as claimed.
436	    # Then build segments from claimed (HSK words) + unclaimed (unknown text).
437	
438	    # Step 1: Only use words with hsk > 0 for claiming positions.
439	    # Sort by length (longest first) so longer words get priority.
440	    hsk_words = [(w, info) for w, info in vocab.items() if info.get("hsk", 0) > 0]
441	    hsk_words.sort(key=lambda x: len(x[0]), reverse=True)
442	
443	    # Step 2: For each HSK word, find all occurrences in text and claim positions
444	    claimed = [False] * n
445	    word_at = {}  # start_pos -> (word, end_pos)
446	
447	    for word, info in hsk_words:
448	        if not word:
449	            continue
450	        start = 0
451	        while True:
452	            idx = text.find(word, start)
453	            if idx == -1:
454	                break
455	            end = idx + len(word)
456	            # Only claim if none of these positions are already claimed
457	            if not any(claimed[i] for i in range(idx, end)):
458	                for i in range(idx, end):
459	                    claimed[i] = True
460	                word_at[idx] = (word, end)
461	            start = idx + 1
462	
463	    # Step 3: Build segments by scanning left to right
464	    segments = []
465	    i = 0
466	    while i < n:
467	        # Check punctuation first
468	        if punct_pattern.match(text[i]):
469	            j = i
470	            while j < n and punct_pattern.match(text[j]):
471	                j += 1
472	            segments.append((text[i:j], True))
473	            i = j
474	            continue
475	
476	        # Check if this position starts a claimed HSK word
477	        if i in word_at:
478	            word, end = word_at[i]
479	            segments.append((word, False))
480	            i = end
481	            continue
482	
483	        # Unclaimed character: collect consecutive unclaimed non-punctuation chars
484	        j = i + 1
485	        while j < n and not punct_pattern.match(text[j]) and not claimed[j]:
486	            j += 1
487	
488	        # The unclaimed run is text[i:j]
489	        # Split into 2-char groups (most Chinese words are 2 chars)
490	        # But check if any 2-char group is actually a common word
491	        unknown = text[i:j]
492	        k = 0
493	        while k < len(unknown):
494	            if k + 2 <= len(unknown):
495	                pair = unknown[k:k + 2]
496	                segments.append((pair, False))
497	                k += 2
498	            else:
499	                segments.append((unknown[k:k + 1], False))
500	                k += 1
501	        i = j
502	
503	    return segments
504	
505	
506	def esc(text):
507	    return html_module.escape(str(text), quote=False)
508	
509	
510	def render_word(word_text, vocab, highlight_words):
511	    """Render a single word as HTML with annotations."""
512	    if not word_text.strip():
513	        return word_text
514	
515	    info = vocab.get(word_text, {})
516	    hsk = info.get("hsk", 0)
517	    pinyin = normalize_pinyin(info.get("pinyin", ""))
518	    en_def = info.get("en_def", "")
519	
520	    # If word not in vocab or has no pinyin, build from individual chars
521	    if not pinyin:
522	        char_pinyins = []
523	        char_defs = []
524	        char_hsk_max = 0
525	        for ch in word_text:
526	            ch_info = vocab.get(ch, {})
527	            ch_hsk = ch_info.get("hsk", 0)
528	            if ch_hsk > 0:
529	                char_hsk_max = max(char_hsk_max, ch_hsk)
530	            ch_py = normalize_pinyin(ch_info.get("pinyin", ""))
531	            ch_def = ch_info.get("en_def", "")
532	            if ch_py:
533	                char_pinyins.append(ch_py)
534	            if ch_def:
535	                char_defs.append(ch_def)
536	        if char_pinyins:
537	            pinyin = " ".join(char_pinyins)
538	        if char_defs:
539	            en_def = "; ".join(char_defs)[:40]
540	        if char_hsk_max > 0:
541	            hsk = char_hsk_max
542	
543	    # Last resort: if still no pinyin, try each char individually
544	    if not pinyin:
545	        char_pinyins = []
546	        for ch in word_text:
547	            if "\u4e00" <= ch <= "\u9fff":
548	                ch_info = vocab.get(ch, {})
549	                ch_py = normalize_pinyin(ch_info.get("pinyin", ""))
550	                if ch_py:
551	                    char_pinyins.append(ch_py)
552	                else:
553	                    char_pinyins.append("")  # empty slot for unknown char
554	            else:
555	                char_pinyins.append("")
556	        pinyin = " ".join(char_pinyins) if any(char_pinyins) else ""
557	
558	    color = HSK_COLORS.get(hsk, "#aaa")
559	    light_bg = HSK_LIGHT_BG.get(hsk, "transparent")
560	    label = HSK_LABELS.get(hsk, "")
561	
562	    is_highlight = word_text in highlight_words
563	    highlight_cls = " hl" if is_highlight else ""
564	    hsk_cls = f" hsk{hsk}" if hsk > 0 else " nohsk"
565	
566	    text = esc(word_text)
567	    py = esc(pinyin) if pinyin else ""
568	
569	    # Build tooltip text: full English definition + HSK label
570	    tooltip_parts = []
571	    if en_def:
572	        tooltip_parts.append(esc(en_def))
573	    if hsk > 0:
574	        tooltip_parts.append(f"[{label}]")
575	    tooltip = " ".join(tooltip_parts)
576	
577	    parts = [f'<span class="w{hsk_cls}{highlight_cls}" style="--c:{color};--bg:{light_bg};" title="{tooltip}">']
578	    parts.append(f'<span class="py">{py}</span>')
579	    parts.append(f'<span class="cz">{text}</span>')
580	    if is_highlight:
581	        parts.append('<span class="star">★</span>')
582	    parts.append('</span>')
583	    return "".join(parts)
584	
585	
586	def render_punctuation(punct):
587	    """Render punctuation without annotations."""
588	    if not punct.strip():
589	        return ""
590	    return f'<span class="punct">{esc(punct)}</span>'
591	
592	
593	def extract_example_sentence(essay_text, expression):
594	    """Find the sentence in essay text that contains the expression."""
595	    if not expression or not expression.strip():
596	        return ""
597	    # Split essay into sentences by Chinese sentence-ending punctuation
598	    sentences = re.split(r'(?<=[。！？…\n])', essay_text)
599	    for sent in sentences:
600	        sent = sent.strip()
601	        if expression in sent and len(sent) > 5:
602	            return sent
603	    # Try splitting by commas too for shorter expressions
604	    clauses = re.split(r'(?<=[，；])', essay_text)
605	    for clause in clauses:
606	        clause = clause.strip()
607	        if expression in clause and len(clause) > 5:
608	            return clause
609	    return ""
610	
611	
612	def generate_html(essay_text, title, hsk_level, source_url, word_count, good_expressions, vocab):
613	    """Generate the complete HTML page."""
614	    # Build highlight set from good expressions
615	    highlight_words = set()
616	    for expr in good_expressions:
617	        expr_text = expr.get("expression", "")
618	        if expr_text:
619	            highlight_words.add(expr_text)
620	
621	    # Segment and render essay
622	    segments = segment_text(essay_text, vocab)
623	
624	    # Split into paragraphs by newlines or double punctuation
625	    paragraphs = []
626	    current_para = []
627	    for word, is_punct in segments:
628	        if word == "\n" or (is_punct and word.strip() == ""):
629	            if current_para:
630	                paragraphs.append(current_para)
631	                current_para = []
632	        else:
633	            current_para.append((word, is_punct))
634	    if current_para:
635	        paragraphs.append(current_para)
636	
637	    # If no paragraph breaks, try splitting by 。and！and？
638	    if len(paragraphs) <= 1:
639	        paragraphs = []
640	        current_para = []
641	        for word, is_punct in segments:
642	            current_para.append((word, is_punct))
643	            if is_punct and word.strip() in ("。", "！", "？", "!?", "..."):
644	                paragraphs.append(current_para)
645	                current_para = []
646	        if current_para:
647	            paragraphs.append(current_para)
648	
649	    essay_html_parts = []
650	    for para in paragraphs:
651	        parts = []
652	        for word, is_punct in para:
653	            if is_punct:
654	                parts.append(render_punctuation(word))
655	            else:
656	                parts.append(render_word(word, vocab, highlight_words))
657	        essay_html_parts.append('<p class="para">' + "".join(parts) + '</p>')
658	    essay_html = "\n".join(essay_html_parts)
659	
660	    # Render good expression cards
661	    expr_cards = []
662	    for expr in good_expressions:
663	        expression_raw = expr.get("expression", "")
664	        expression = esc(expression_raw)
665	        pinyin = esc(expr.get("pinyin", ""))
666	        hsk = expr.get("hsk", 0)
667	        en_def = esc(expr.get("en_def", ""))
668	        explanation = esc(expr.get("explanation", ""))
669	        example = expr.get("example", "")
670	        # Auto-extract example from essay if not provided
671	        if not example or not example.strip():
672	            example = extract_example_sentence(essay_text, expression_raw)
673	        example = esc(example)
674	        color = HSK_COLORS.get(hsk, "#555")
675	        label = HSK_LABELS.get(hsk, "")
676	        bg = HSK_LIGHT_BG.get(hsk, "#f9f9f9")
677	
678	        expr_cards.append(f'''
679	    <div class="ecard" style="--c:{color};--bg:{bg};">
680	      <div class="ecard-head">
681	        <span class="ecard-text">{expression}</span>
682	        <span class="ecard-py">{pinyin}</span>
683	        <span class="ecard-hsk" style="background:{color};">{label}</span>
684	      </div>
685	      <div class="ecard-en">{en_def}</div>
686	      <div class="ecard-exp">{explanation}</div>
687	      <div class="ecard-ex"><span class="ecard-ex-label">Example:</span> {example}</div>
688	    </div>''')
689	    expr_html = "\n".join(expr_cards)
690	
691	    level_label = HSK_LABELS.get(int(hsk_level), f"HSK {hsk_level}")
692	    level_color = HSK_COLORS.get(int(hsk_level), "#333")
693	
694	    legend_items = "".join(
695	        f'<span class="lg-item"><span class="lg-dot" style="background:{color};"></span>{HSK_LABELS[level]}</span>'
696	        for level, color in HSK_COLORS.items()
697	    )
698	
699	    title_esc = esc(title)
700	    source_esc = esc(source_url)
701	
702	    return f'''<!DOCTYPE html>
703	<html lang="zh-CN">
704	<head>
705	<meta charset="UTF-8">
706	<meta name="viewport" content="width=device-width, initial-scale=1.0">
707	<title>{title_esc} - Essay Display</title>
708	<style>
709	  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
710	  body {{
711	    font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif;
712	    background: linear-gradient(160deg, #667eea 0%, #764ba2 100%);
713	    min-height: 100vh;
714	    color: #2c3e50;
715	    padding: 0;
716	  }}
717	  .container {{ max-width: 920px; margin: 0 auto; padding: 36px 20px 60px; }}
718	  .header {{
719	    text-align: center; margin-bottom: 28px; padding: 36px 28px;
720	    background: white; border-radius: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.12);
721	  }}
722	  .header h1 {{ font-size: 30px; font-weight: 800; color: #1a1a2e; margin-bottom: 14px; letter-spacing: 3px; }}
723	  .meta {{ display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }}
724	  .badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 18px; border-radius: 24px; font-size: 14px; font-weight: 600; }}
725	  .badge-level {{ background: {level_color}; color: white; }}
726	  .badge-count {{ background: #f0f2f5; color: #555; }}
727	  .badge-source {{ background: #f0f2f5; color: #555; }}
728	  .badge-source a {{ color: inherit; text-decoration: none; }}
729	  .badge-source a:hover {{ text-decoration: underline; }}
730	  .legend {{
731	    display: flex; justify-content: center; gap: 14px; flex-wrap: wrap;
732	    margin-bottom: 24px; padding: 14px 24px; background: rgba(255,255,255,0.95);
733	    border-radius: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.08);
734	  }}
735	  .lg-item {{ display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; color: #444; }}
736	  .lg-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
737	  .essay {{
738	    background: white; border-radius: 20px; padding: 48px 40px;
739	    box-shadow: 0 8px 32px rgba(0,0,0,0.12); margin-bottom: 32px;
740	  }}
741	  .para {{ margin-bottom: 22px; text-align: justify; line-height: 1.5; }}
742	  .w {{
743	    display: inline-flex; flex-direction: column; align-items: center;
744	    vertical-align: top; margin: 0 1px 8px; padding: 4px 5px 3px;
745	    border-radius: 7px; position: relative; transition: all 0.2s ease;
746	    border-bottom: 3px solid var(--c, transparent); background: var(--bg, transparent);
747	  }}
748	  .w:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 10; }}
749	  .py {{
750	    font-size: 11px; font-weight: 500; color: var(--c, #999);
751	    font-family: "Georgia", "Times New Roman", serif; line-height: 1.1;
752	    margin-bottom: 2px; min-height: 13px; text-align: center;
753	  }}
754	  .cz {{ font-size: 20px; font-weight: 600; color: #1a1a2e; line-height: 1.3; text-align: center; }}
755	  .w.nohsk {{ border-bottom-color: transparent; background: transparent; }}
756	  .w.nohsk .py {{ color: #bbb; }}
757	  .w[title]:hover::after {{
758	    content: attr(title); position: absolute; bottom: calc(100% + 6px); left: 50%;
759	    transform: translateX(-50%); background: rgba(20,20,40,0.95); color: #fff;
760	    padding: 10px 18px; border-radius: 8px; font-size: 14px; font-weight: 400;
761	    font-style: normal; line-height: 1.6; white-space: normal; max-width: 800px;
762	    min-width: 200px; text-align: left; z-index: 100; pointer-events: none;
763	    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
764	  }}
765	  .w[title]:hover::before {{
766	    content: ""; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
767	    border: 5px solid transparent; border-top-color: rgba(20,20,40,0.95); z-index: 100;
768	  }}
769	  .w.hl {{
770	    background: linear-gradient(135deg, #fff8e1, #fff3c4);
771	    border-bottom-color: #ffc107; border-bottom-width: 4px;
772	    box-shadow: 0 2px 8px rgba(255,193,7,0.2);
773	  }}
774	  .w.hl .cz {{ color: #e65100; }}
775	  .star {{ position: absolute; top: -8px; right: -4px; font-size: 13px; color: #ff9800; text-shadow: 0 1px 2px rgba(255,152,0,0.3); }}
776	  .punct {{ font-size: 20px; color: #555; font-weight: 600; vertical-align: top; display: inline-block; margin: 0 1px; padding-top: 18px; }}
777	  .expr-sec {{ background: white; border-radius: 20px; padding: 40px; box-shadow: 0 8px 32px rgba(0,0,0,0.12); }}
778	  .expr-title {{ font-size: 24px; font-weight: 800; color: #1a1a2e; margin-bottom: 24px; padding-bottom: 14px; border-bottom: 3px solid #f0f2f5; }}
779	  .ecard {{ border-left: 5px solid var(--c, #ccc); background: var(--bg, #f9f9f9); border-radius: 10px; padding: 22px 26px; margin-bottom: 16px; transition: transform 0.2s, box-shadow 0.2s; }}
780	  .ecard:hover {{ transform: translateX(6px); box-shadow: 0 4px 16px rgba(0,0,0,0.1); }}
781	  .ecard-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }}
782	  .ecard-text {{ font-size: 22px; font-weight: 800; color: #1a1a2e; }}
783	  .ecard-py {{ font-size: 15px; color: #888; font-family: "Georgia", serif; }}
784	  .ecard-hsk {{ font-size: 12px; color: white; padding: 3px 12px; border-radius: 12px; font-weight: 700; }}
785	  .ecard-en {{ font-size: 15px; color: #555; font-style: italic; margin-bottom: 10px; }}
786	  .ecard-exp {{ font-size: 14px; color: #333; line-height: 1.8; margin-bottom: 10px; }}
787	  .ecard-ex {{ font-size: 14px; color: #555; background: rgba(0,0,0,0.04); padding: 10px 14px; border-radius: 8px; line-height: 1.7; }}
788	  .ecard-ex-label {{ font-weight: 700; color: #7f8c8d; }}
789	  .footer {{ text-align: center; padding: 24px; font-size: 14px; color: rgba(255,255,255,0.7); }}
790	  .footer a {{ color: rgba(255,255,255,0.9); text-decoration: none; }}
791	  .footer a:hover {{ text-decoration: underline; }}
792	  @media (max-width: 600px) {{
793	    .container {{ padding: 16px 10px 40px; }}
794	    .header {{ padding: 24px 16px; border-radius: 16px; }}
795	    .header h1 {{ font-size: 24px; }}
796	    .essay {{ padding: 24px 14px; border-radius: 16px; }}
797	    .w {{ padding: 3px 3px 2px; margin: 0 0px 6px; }}
798	    .py {{ font-size: 9px; min-height: 11px; }}
799	    .cz {{ font-size: 17px; }}
800	    .punct {{ font-size: 17px; padding-top: 15px; }}
801	    .expr-sec {{ padding: 24px 16px; border-radius: 16px; }}
802	    .ecard {{ padding: 16px 18px; }}
803	    .ecard-text {{ font-size: 18px; }}
804	  }}
805	</style>
806	</head>
807	<body>
808	<div class="container">
809	  <div class="header">
810	    <h1>{title_esc}</h1>
811	    <div class="meta">
812	      <span class="badge badge-level">{level_label}</span>
813	      <span class="badge badge-count">约 {word_count} 字</span>
814	      <span class="badge badge-source"><a href="{source_esc}" target="_blank">📍 zuowen.com</a></span>
815	    </div>
816	  </div>
817	  <div class="legend">
818	    {legend_items}
819	    <span class="lg-item"><span class="lg-dot" style="background:#ffc107;"></span>★ Good Expression</span>
820	  </div>
821	  <div class="essay">
822	{essay_html}
823	  </div>
824	  <div class="expr-sec">
825	    <div class="expr-title">★ Useful Expressions &amp; Key Sentences</div>
826	{expr_html}
827	  </div>
828	  <div class="footer">
829	    Generated by Chinese Writing Tutor · Source: <a href="{source_esc}" target="_blank">zuowen.com</a>
830	  </div>
831	</div>
832	</body>
833	</html>'''
834	
835	
836	def main():
837	    parser = argparse.ArgumentParser(description="Generate annotated HTML essay display")
838	    parser.add_argument("--essay-file", help="Path to text file containing essay")
839	    parser.add_argument("--essay-text", help="Essay text directly (alternative to --essay-file)")
840	    parser.add_argument("--expressions-json", help="JSON file with good expressions array")
841	    parser.add_argument("--output", default="/mnt/user-data/outputs/essay_display.html")
842	    parser.add_argument("--hsk-level", default="6", help="HSK level for header display")
843	    parser.add_argument("--title", default="Essay", help="Essay title")
844	    parser.add_argument("--source-url", default="", help="Source URL")
845	    parser.add_argument("--word-count", default="0", help="Word count")
846	    parser.add_argument("--vocab-dir", default="", help="Directory with HSK CSV files")
847	    args = parser.parse_args()
848	
849	    # Get essay text
850	    if args.essay_file:
851	        with open(args.essay_file, encoding="utf-8") as f:
852	            essay_text = f.read()
853	    elif args.essay_text:
854	        essay_text = args.essay_text
855	    else:
856	        # Read from stdin
857	        essay_text = sys.stdin.read()
858	
859	    # Get good expressions
860	    good_expressions = []
861	    if args.expressions_json and os.path.exists(args.expressions_json):
862	        with open(args.expressions_json, encoding="utf-8") as f:
863	            good_expressions = json.load(f)
864	
865	    # Find vocab directory
866	    vocab_dir = args.vocab_dir
867	    if not vocab_dir:
868	        # Try to find relative to this script
869	        script_dir = os.path.dirname(os.path.abspath(__file__))
870	        vocab_dir = os.path.join(script_dir, "..", "reference", "hsk_vocabulary")
871	        if not os.path.exists(vocab_dir):
872	            # Try workspace path
873	            vocab_dir = "/mnt/skills/user/chinese-writing-tutor-tcsl/v2.0.0/reference/hsk_vocabulary"
874	
875	    vocab = load_hsk_vocab(vocab_dir)
876	
877	    html_content = generate_html(
878	        essay_text=essay_text,
879	        title=args.title,
880	        hsk_level=args.hsk_level,
881	        source_url=args.source_url,
882	        word_count=args.word_count,
883	        good_expressions=good_expressions,
884	        vocab=vocab,
885	    )
886	
887	    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
888	    with open(args.output, "w", encoding="utf-8-sig") as f:
889	        f.write(html_content)
890	
891	    print(f"HTML_SAVED:{args.output}")
892	
893	
894	if __name__ == "__main__":
895	    main()
896	

[End of file.]