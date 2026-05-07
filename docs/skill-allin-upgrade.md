# All In 手绘笔记视觉系统 V2 升级 — Codex 施工说明书

> 本文档由 Sonnet 文本工人撰写，供 Codex 施工用。  
> 对应 roadmap P3-K2 / K3 / K4 / K5。  
> **只做代码改动，不改文档内容，不改 config.json，不改任何 .css 文件（K1 已完成）。**

---

## 1. 整体目标

把 E270 验证过的概念海报风格（V2 手绘高级概念海报）规范化进代码体系，同时修复 SKILL.md 承诺但未实现的 Codex 优先生图链路，以及将串行 7 分钟改为并发 2–3 分钟。商品拆解图（scripts/shared/gen_image.py）同步升级到 V2 规范，保证全套产品视觉一致。

**不改变的东西**：styles.css（K1 已完成）、飞书写入逻辑、VTT 翻译流程、config.json 字段、任何 SKILL.md 的触发词和工作流步骤描述以外的内容。

---

## 2. 改动清单（按文件分组）

### 2.1 scripts/allin/generate_sketchnote.py

**现状**：
- `STYLE_BASE` 常量：深灰线条 + 珊瑚橙/深青/琥珀黄三色（sketchnote 风格）
- `build_page_prompts()`：单一模板，所有页用同一 STYLE_BASE，提示词描述「卡片式」「气泡式」「流程式」等信息图布局
- `generate_image()`：直接 `OpenAI(api_key=..., base_url=...)` 调 API，无 Codex 路径
- 主流程 `main()`：`for page in pages` 串行逐张生成

**目标**：
- 双模板（cover_v2 / inner_v2）+ 配色矩阵
- Codex 优先生图 → API fallback
- 5 张并发生成

**关键改动**：

#### A. 新增配色矩阵常量

```python
# 四组配色（A/B 亮色系默认；C/D 深色系备选）
COLOR_PALETTES = {
    'A': {
        'name': '轻盈派（亮色默认）',
        'primary':   '#4A90E2',  # 粉蓝
        'accent':    '#F5C842',  # 暖黄
        'bg':        '#F8F4ED',  # 米白
        'ink':       '#2D2D2D',  # 深墨
        'secondary': '#A8C4E0',  # 浅粉蓝（辅助）
    },
    'B': {
        'name': '清新派（亮色备选）',
        'primary':   '#5DA68F',  # 薄荷青
        'accent':    '#E8B197',  # 杏粉
        'bg':        '#F8F4ED',  # 米白
        'ink':       '#2D2D2D',
        'secondary': '#B8D8CF',
    },
    'C': {
        'name': '东方庄重派（深色，重型题材）',
        'primary':   '#C73E2C',  # 朱红
        'accent':    '#C8A35F',  # 暖金（小面积）
        'bg':        '#F5F2EA',  # 米黄宣纸
        'ink':       '#1A1A1A',  # 墨黑
        'secondary': '#8B2018',  # 暗红
    },
    'D': {
        'name': '藏青现代派（深色，命运感题材）',
        'primary':   '#1B365D',  # 藏青
        'accent':    '#C8A35F',  # 暖金
        'bg':        '#F8F4ED',  # 米白
        'ink':       '#1A1A1A',
        'secondary': '#C73E2C',  # 朱砂红（印章）
    },
}
```

#### B. 新增 `pick_color_palette(record: dict) -> dict`

根据本期议题气质自动选色（主会话也可通过命令行参数 `--palette A/B/C/D` 覆盖）。

自动选择逻辑（按关键词匹配，都没命中则默认 A）：

```
深色 C/D 触发关键词（任一命中走深色）：
  债务、危机、战争、博弈、算力争夺、洗牌、破产、颠覆、威胁、争夺、入侵、垄断

中文标题含上述关键词 → 优先 C（朱红/宣纸）
五维综合评分 == 5 且含上述关键词 → 也走 C
五维综合评分 == 5 但无上述关键词 → 走 D（藏青）
其余情况 → 走 A（默认）
```

函数签名：`def pick_color_palette(record: dict, override: str = None) -> dict`  
`override` 为 `'A'/'B'/'C'/'D'` 时直接返回对应配色，忽略自动逻辑。

#### C. 重写 `build_page_prompts(record, analysis, palette: dict)` 为 V2 模板

**封面（cover_v2）提示词关键要素**：

1. 风格底座：`手绘高级概念海报。{palette['bg']}宣纸底色，{palette['ink']}手绘线条，{palette['primary']}主色，{palette['accent']}辅色。手绘水彩质感+剪纸拼贴+石版印刷颗粒感，对抗 AI 过于光滑的感觉。`
2. 巨型核心词（从中文标题提取 2–4 字核心词）：占画面 40–60% 面积，字形毛笔/书法/剪纸艺术化处理
3. 视觉隐喻：1–2 个微小角色或物体，演绎核心词词义（不要文字说明，靠图形传达）
4. 嵌入式封面信息（不分栏，散布在核心词留白处）：
   - 顶部小字：`ALL IN PODCAST 中文知识库`
   - 期号、日期、时长（分钟）、播放量（万）、主题分类
   - 副标题（中文标题全文，嵌入留白）
   - 三个核心议题印章（从 dim1 提取三个短语，印章风格，圆形或方形）
   - 四主播署名：`Jason · Chamath · Sacks · Friedberg`（小字横排）
   - 1–2 句诗性补白（从 dim1 提取 4–8 字短句，意象感强）
5. 竖版 3:4 比例
6. 严禁列表（写进提示词末尾）：`严禁：分栏拼接布局、人物群像照片式描绘、英文界面元素（buttons/labels等）、任何形式的页码（"第1页""P1""Page 1"等）、错别字。`

**内页（inner_v2）提示词关键要素**：

五个五维章节各自有专属隐喻母题，在提示词里显式指定：

| 章节 | 隐喻母题 | 说明 |
|------|---------|------|
| 核心议题（dim1+dim2） | 由议题气质动态生成（战场/木马/漩涡/阶梯等） | 主会话从 cn_title 关键词推导，写入提示词 |
| 市场判断（dim3） | 倒计时炸弹 / 钟摆 / 天秤 | 根据市场判断是否有紧迫感自动选 |
| 四人立场（dim4） | 四向罗盘 / 十字路口 | 固定母题，体现四方向分歧 |
| 国内启示（dim5） | 灯塔 / 种子萌芽 / 航向 | 固定母题，体现指引感 |

提示词结构（inner_v2）：

```
{风格底座，同封面}

章节大标题：{章节名}（{palette['primary']}色，毛笔字风格，占页面顶部 15-20% 高度）

核心隐喻母题：{母题描述，居中或全页展开，线描轮廓，不要填充色块}

三个要点（附着在母题图形上，不要做独立分栏卡片）：
  · {要点1} — 附着位置：{母题的左上/左侧/下方}
  · {要点2} — 附着位置：{中部}
  · {要点3} — 附着位置：{右下/底部}
每个要点：手绘图标（5mm 大小）+ {palette['accent']}色关键标签 + 说明文字（2–3 行）

底部：{金句或印章注解} + 系列标识「All In 中文笔记」（{palette['ink']}色小字）

竖版 3:4 比例。严禁：分栏卡片布局（3列grid等）、任何页码标识。
```

**函数签名变更**：

```python
def build_page_prompts(record: dict, analysis: dict, palette: dict) -> list[dict]:
    # 每个 dict 格式不变：{'page_num': int, 'title': str, 'prompt': str}
    ...
```

#### D. 新增 `generate_via_codex(prompt: str, page_num: int, output_path: Path) -> bool`

用 codex-companion task 派子代理生图：

```python
def generate_via_codex(prompt: str, page_num: int, output_path: Path) -> bool:
    """
    用 Codex 子代理生图。成功返回 True（图片已写到 output_path），失败返回 False。
    
    实现思路：
    1. 将 prompt 写到 /tmp/allin_img_prompt_{page_num}.txt
    2. 调 codex-companion task：
       "读取 /tmp/allin_img_prompt_{page_num}.txt 的提示词，
        用 gpt-image-1 或你可调用的图片生成模型生成图片，
        将图片保存到 {output_path}"
    3. 检查 output_path 是否存在且 size > 10KB，返回 True/False
    
    注意：codex-companion 的调用命令参考 SKILL.md Step 10 的现有写法。
    如果 codex-companion 不在 PATH，或调用超时（60s），返回 False 触发 fallback。
    """
    ...
```

#### E. 改写 `generate_image()` 为 Codex 优先 + API fallback

```python
def generate_image(prompt: str, page_num: int, output_path: Path,
                   api_key: str = None, api_base: str = None,
                   model: str = DEFAULT_MODEL, retry: int = 3) -> bytes | None:
    """
    Codex 优先：先尝试 generate_via_codex()。
    失败（返回 False）或 api_key 显式传入时：走 OpenAI API fallback。
    
    签名变更：
    - 原来接收 client: OpenAI 对象，现在接收 api_key / api_base 字符串（懒初始化）
    - 新增 output_path: Path，Codex 路径直接写文件，API 路径返回 bytes
    """
    # 1. 先尝试 Codex
    if not api_key:  # 没有配置 API key，只走 Codex
        success = generate_via_codex(prompt, page_num, output_path)
        return None if not success else output_path.read_bytes()
    
    # 2. 有 api_key：先试 Codex，失败再走 API
    if generate_via_codex(prompt, page_num, output_path):
        return output_path.read_bytes()
    
    # 3. API fallback（原有逻辑保留）
    client = OpenAI(api_key=api_key, base_url=api_base or DEFAULT_API_BASE)
    for attempt in range(retry):
        # ... 原有 API 调用逻辑不变 ...
        pass
```

#### F. 改主流程为并发

```python
# main() 中替换串行 for 循环为并发：
import threading

def _generate_one(page, output_dir, api_key, api_base, model, results):
    """单张图生成，结果写入 results[page['page_num']]"""
    ...

with threading.ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(_generate_one, page, output_dir, api_key, api_base, model, results): page
        for page in pages
    }
    for future in concurrent.futures.as_completed(futures):
        ...  # 收集结果，打印进度
```

asyncio 也可以，选更熟悉的方式。关键：5 张并发，统一在所有完成后按 page_num 排序输出。

---

### 2.2 scripts/allin/generate_pdf.py

**现状**：当 `analysis.json` 缺少 `annotations` 字段时，注释版和原稿版输出相同，用户无法感知。

**目标**：缺失时主动提示，而不是静默输出两份相同文件。

**关键改动**（≤10 行，最小修改）：

在读取 analysis.json 后，检测 `annotations` 字段：

```python
annotations = analysis.get('annotations', [])
if not annotations:
    print(
        "⚠️  注意：analysis.json 中未找到 annotations 字段。\n"
        "   注释版和原稿版将输出相同内容。\n"
        "   如需注释版，可从飞书页面回拉：\n"
        "   python3 scripts/allin/utils.py extract-analysis --record-id <ID>\n"
        "   然后重新运行本脚本。"
    )
```

不改生成逻辑，只加警告输出。

---

### 2.3 scripts/allin/utils.py

**现状**：无从飞书回拉 analysis.json 的功能。

**目标**：新增 `extract_analysis_from_wiki(record_id, doc_token)` 函数，从飞书页面的 Markdown 内容反向解析五维分析和金句，避免重跑 AI 分析浪费 token。

**函数签名和实现思路**：

```python
def extract_analysis_from_wiki(record_id: str, doc_token: str) -> dict:
    """
    从飞书知识库页面反向解析 analysis.json 结构。
    
    前置：doc_token 从 record 的「飞书页面 URL」字段解析，或由调用方传入。
    
    流程：
    1. 调用 lark-cli wiki get-content --doc-token <doc_token> 获取 Markdown
    2. 正则提取五维分析各章节（## 一、本期议题 ... ## 五、国内启示）
    3. 正则提取精华金句（> **英文** ... 中文 — 说话人）
    4. 返回 dict 结构与 analysis.json 一致：
       {
         'five_dim': '① 议题背景\n内容...\n② ...',
         'quotes': '> **EN** ...\n中文 — Jason',
         'annotations': []  # 注释需从逐字稿页面单独提取，此处返回空列表并提示
       }
    
    错误处理：
    - doc_token 无效或无权限：raise ValueError 并提示
    - 页面内容解析不到五维结构：返回空 dict 并 print 警告
    """
    ...
```

同时在 `main()` 里加 CLI 入口，支持 `python3 utils.py extract-analysis --record-id <ID>` 直接运行。

---

### 2.4 templates/allin-kami/styles.css

**状态**：K1 已完成（2026-05-07）。本次施工不改此文件。

字号体系作为参考锚点（Codex 不需要改，只需知道）：

| 元素 | 字号 |
|------|------|
| body 正文 | 18px |
| 章节标题 `.analysis-heading` | 22px |
| 子标题 `.analysis-sub` | 17px |
| 英文原文 `.en-para` | 16px |
| 中文翻译 `.zh-translation` | 16px |
| 注释 | 15px |
| 说话人标签 | 14px |
| 章节时间标 | 17px |
| 概览块 | 16.5px |
| 金句中文 | 17px |
| 金句英文 | 16px |
| 封面标题 | 38px |
| 页边距 | `@page { margin: 10mm 12mm }` |
| 内容 padding | `32px 20px` |

---

### 2.5 scripts/shared/gen_image.py（商品拆解 P3-H）

**现状**：旧 sketchnote 风格提示词（与 generate_sketchnote.py 原始风格相同）。生成 4 张图：封面 + 商业模式拆解 + 流量拆解 + 机会拆解。

**目标**：升级到 V2 双模板，与 All In 手绘笔记视觉语言一致。

**关键改动**：

1. **抽取共享模板逻辑**：将 `COLOR_PALETTES` 常量和 `pick_color_palette()` 函数移到独立文件 `scripts/shared/poster_template.py`，`generate_sketchnote.py` 和 `gen_image.py` 都从此文件 import。

2. **gen_image.py 的 4 张图模板**：
   - **封面图**：用 cover_v2 逻辑，核心词取商品/产品名（而非 All In 期号），印章改为「商业模式·流量转化·机会洞察」
   - **商业模式拆解图**：用 inner_v2，母题用「商业引擎/齿轮组合」，3 要点来自五维框架的①产品形态和③赛道竞争
   - **流量拆解图**：用 inner_v2，母题用「漏斗/转化链路」，3 要点来自②流量转化
   - **机会拆解图**：用 inner_v2，母题用「地图标记/蓝图」，3 要点来自⑤机会洞察

3. **配色选择**：商品拆解图默认用 A 色组（轻盈派），保持亮色系，与小红书商品内容调性匹配。如商品本身是高端/奢侈品类可改 D（藏青）。

4. **函数签名参考** `generate_sketchnote.py` 的 V2 版本，保持 API 一致。

---

### 2.6 skills/lark-knowledge-allin-transcript/SKILL.md

**不改触发词、工作流步骤编号、任何业务逻辑描述。**

只在以下两处追加内容：

**Step 9（PDF 生成）**：追加一段说明：
> 「字号已按手机阅读优化（K1，2026-05-07）：body 18px，封面标题 38px，页边距 10mm 12mm。在 iPhone fit-width 显示下正文约 6.5px，章节标题约 8px，具备基本可读性。」

**Step 10（手绘笔记生成）**：更新风格描述部分：
> - 将「Sketchnote 手绘速记风，黑色线条+天蓝色双色」改为「V2 手绘高级概念海报（cover_v2 + inner_v2 双模板），配色二元体系（亮色 A/B + 深色 C/D）」
> - 新增「Codex 优先生图链路」说明：默认调 Codex 子代理生图，配置 IMAGE_API_KEY 时走 API fallback

---

### 2.7 skills/lark-knowledge-upgrade/SKILL.md

**只改 Step 7（产品拆解笔记）中的视觉风格描述**，其余不动：

> 将「复用 All In 手绘笔记视觉风格（sketchnote 信息图）」改为「复用 All In 手绘笔记 V2 视觉风格（概念海报 cover_v2 + inner_v2，配色默认亮色 A 组），实现见 scripts/shared/gen_image.py」

---

## 3. 派遣建议

| 阶段 | 任务 | 模式 | 建议顺序 |
|------|------|------|---------|
| K2 | generate_sketchnote.py 重写（V2 模板） | 🅱️ 施工（方案已定） | 第 1 批 |
| K5 | gen_image.py + poster_template.py | 🅱️ 施工（方案已定） | 第 1 批（与 K2 并行，文件不冲突） |
| K3 | Codex 优先链路（generate_via_codex） | 🅰️ 自主 | 第 2 批（K2 完成后，在其基础上加） |
| K4 | 并发生成（ThreadPoolExecutor） | 🅰️ 自主 | 第 2 批（与 K3 并行，改不同函数） |
| 文档 | SKILL.md 两处追加 | Sonnet | 任意时机 |

**K2 和 K5 可以同一 Codex 任务同时做**（涉及文件不冲突），但 K3 依赖 K2 完成后的 `generate_image()` 函数签名，必须串行。

---

## 4. 验收清单（可机械检查）

### K2 验收
- [ ] `scripts/allin/generate_sketchnote.py` 中存在 `COLOR_PALETTES` 字典（含 A/B/C/D 四组）
- [ ] 存在 `pick_color_palette(record, override=None)` 函数
- [ ] `build_page_prompts()` 接受 `palette: dict` 第三个参数
- [ ] 封面提示词中包含「毛笔」或「书法」或「剪纸」（V2 风格标志词）
- [ ] 封面提示词中包含「严禁」段落（含「分栏」「页码」等禁止项）
- [ ] 内页提示词中不包含「卡片式」「气泡式」「流程式」（旧风格词，已替换）
- [ ] 内页提示词中包含「母题」或「附着」（V2 核心设计词）
- [ ] 命令行支持 `--palette A/B/C/D` 参数（覆盖自动选色）
- [ ] 用 E270 的 analysis.json 跑 `--prompts-only`，输出 5 张提示词，封面含「巨型核心词」描述，内页含对应母题描述

### K3 验收
- [ ] 存在 `generate_via_codex(prompt, page_num, output_path)` 函数
- [ ] `generate_image()` 函数：无 `IMAGE_API_KEY` 时只走 Codex 路径
- [ ] `generate_image()` 函数：有 `IMAGE_API_KEY` 时先走 Codex，失败后走 API
- [ ] `SKILL.md` Step 10 中包含「Codex 优先」描述

### K4 验收
- [ ] 主流程使用 `ThreadPoolExecutor` 或 `asyncio` 并发
- [ ] 5 张图并发发起，不是串行 for 循环
- [ ] 最终输出文件名按 page_num 排序（不按完成时间排序）
- [ ] 本地用 `--prompts-only` 跑，输出显示「并发生成」或类似字样

### K5 验收
- [ ] 存在 `scripts/shared/poster_template.py`，其中定义 `COLOR_PALETTES` 和 `pick_color_palette()`
- [ ] `generate_sketchnote.py` 和 `gen_image.py` 都从 `poster_template.py` import（不再各自定义）
- [ ] `gen_image.py` 封面提示词包含「毛笔」或「书法」或「剪纸」
- [ ] `gen_image.py` 的 3 张内容图提示词分别对应「商业引擎/齿轮」「漏斗/转化」「地图/蓝图」（或等效表达）
- [ ] `skills/lark-knowledge-upgrade/SKILL.md` Step 7 中含「V2」或「概念海报」字样

### generate_pdf.py 验收
- [ ] 当 `analysis.get('annotations', [])` 为空时，打印包含「⚠️」的警告信息
- [ ] 警告信息包含 `utils.py extract-analysis` 字样（回拉方法提示）

### utils.py 验收
- [ ] 存在 `extract_analysis_from_wiki(record_id, doc_token)` 函数
- [ ] 支持 CLI：`python3 scripts/allin/utils.py extract-analysis --record-id <ID>` 不报错（可以没有真实飞书连接，但 argparse 要能解析）

---

## 5. K6: 提示词宪法

### 5.1 设计哲学

**为什么要固化模板**

E270 已经验证了 cover_v2 和 inner_v2 两套 prompt 的视觉效果，用户认可。问题是这两套 prompt 散落在 `/tmp/gen_cover_v2.py` 和 `/tmp/gen_inner_v2.py` 里，属于一次性脚本，不在 Skill 体系内。换一个新会话，AI 就不知道这些 prompt 的存在，只能重新写——风格漂移、不可复用，每期都在做重复的提示词工程。

**模板骨架 vs 填空参数的边界**

| 类型 | 定义 | 例子 |
|------|------|------|
| 模板骨架 | 方法论、原则、禁止项——跨期不变 | 「统一视觉场，不分栏拼贴」「严禁：分栏拼接布局、人物群像」 |
| 填空参数 | 每期内容不同的具体信息 | `{episode}`、`{core_word}`、`{points}` |

原则：**模板骨架完整保留**，不因为「这期没用到」而删减；**填空参数最小化**，凡是能从飞书记录字段自动提取的，不要求主会话手工填写。

---

### 5.2 文件位置

```
scripts/shared/poster_template.py     # K6 新建，K2/K5 施工时从此文件 import
```

文件包含：
- `COVER_V2_TEMPLATE`：封面模板字符串常量（Python f-string）
- `INNER_V2_TEMPLATE`：内页模板字符串常量（Python f-string）
- `render_cover_prompt(params: dict) -> str`：封面 prompt 渲染函数
- `render_inner_prompt(params: dict) -> str`：内页 prompt 渲染函数

K2（`generate_sketchnote.py`）和 K5（`gen_image.py`）施工时，从此文件 import 模板，不再在各自文件里内联写 prompt 字符串。

---

### 5.3 封面模板（COVER_V2_TEMPLATE）

完整参数化模板（Python f-string，`{参数名}` 为填空位）：

```python
COVER_V2_TEMPLATE = """你是一位顶级海报艺术家，正在创作 All In Podcast 中文知识库的封面海报。
风格基底：手绘水彩 + 剪纸拼贴 + 东方艺术质感（参考国风/日系艺术海报传统），
而不是数字插画、商业插画或字效海报。整体气质要像一张**展览级艺术作品**，
有印刷品质的颗粒感、纸张纹理、笔触温度，让人愿意挂在墙上。

━━━━━ 一、深度词义转译 ━━━━━
核心词「{core_word}」在本期 All In Podcast {episode} 的语境中，
{context}
情绪气质：宏大转折、命运感、新王登基、旧秩序崩解、咽喉关口的争夺。

{core_word_symbolism}

━━━━━ 二、画面整体场域 ━━━━━
统一视觉场，不分栏拼贴。文字、图像、辅助信息、留白共生。
有自然阅读流向：先被巨型主标题击中 → 被主体隐喻吸引 → 自然看到角落补白信息。

━━━━━ 三、主标题系统 ━━━━━
巨大的中文主标题「{core_word}」是绝对主体，占画面 40-60% 面积。
**字形必须清晰、完整、可识别，不要出现错字、缺笔、变形**——
建议采用书法字、剪纸字、水墨字或宋体艺术化处理，但保证笔画完整。

━━━━━ 四、视觉隐喻（择其一最强者）━━━━━
建议核心隐喻方向：
{metaphor_options}

挑选最有命运感和戏剧张力的方向，保证一眼能读懂寓意。

━━━━━ 五、必要封面信息（嵌入式排版，不分栏）━━━━━
以下信息要自然嵌入画面，不形成独立信息栏：
- 顶部或侧栏小字：「ALL IN PODCAST 中文知识库」
- 期号 + 日期：「{episode} · {date}」
- 播放量 + 时长 + 主题：「{duration} · 播放量 {views} · {topic}」
- 副标题（可选嵌入下方留白处）：「{title}」
- 关键词条（如剪纸标签或印章效果）：「{sub_words}」
- 四位主播名：Jason · Chamath · Sacks · Friedberg（小字嵌入侧边或底部，像署名一样克制）

排布原则：所有这些信息要像贴在墙上的展签、印章、批注一样自然，
不能整齐对齐成 form 表单状，要错落有致、有节奏。

━━━━━ 六、辅助诗性补白（少量、嵌入式）━━━━━
在画面留白处放 1-2 句诗性短语（不要多）：
{aux_poetry}
位置可在角落、贴着主体、或主标题边缘。要像低语、批注、墨迹，
不要做成说明栏。可以用毛笔字或印章式排布。

━━━━━ 七、色彩逻辑（克制 3-4 色）━━━━━
推荐配色（本期选定色组 {palette}）：
{palette_description}

整体气质要"高级、克制、展览级、印刷品质感"。
不要俗艳拼色、不要数字渐变、不要商业插画风。

━━━━━ 八、风格质感 ━━━━━
强烈倾向：手绘水彩 + 剪纸拼贴 + 石版印刷 + 丝网印刷 + 纸张颗粒 + 笔触温度。
画面应有"被人手做出来"的痕迹，而非"AI 生成"的光滑感。
允许：水墨晕染、纸纤维肌理、印章压痕、剪纸边缘、轻微噪点、做旧感。

━━━━━ 九、严格禁止 ━━━━━
- 不要把信息分成多个独立的卡片/栏目
- 不要堆群像（最多 1-2 个微小人影/主体）
- 不要做单纯字体海报（必须有主体演绎和视觉转译）
- 不要出现错字、缺笔、变形字、英文界面元素、页码、版本号、版权声明
- 不要俗艳渐变、廉价模板感
{forbidden}

━━━━━ 输出 ━━━━━
竖版 3:4 比例。整张海报必须看起来像「策展级艺术作品」，
有意境、有情绪、有命运感，并且让观者一眼明白本期讨论的是什么。
"""
```

**各节说明**（哪些是骨架，哪些是占位符）：

| 节 | 不变骨架 | 填空参数 |
|----|---------|---------|
| 一、深度词义转译 | 情绪气质描述句式 | `{core_word}` `{episode}` `{context}` `{core_word_symbolism}` |
| 二、画面整体场域 | 全部（统一视觉场原则） | 无 |
| 三、主标题系统 | 全部（字形要求、面积要求） | `{core_word}` |
| 四、视觉隐喻 | 「择其一」指令 | `{metaphor_options}` |
| 五、必要封面信息 | 排布原则、四主播姓名 | `{episode}` `{date}` `{duration}` `{views}` `{topic}` `{title}` `{sub_words}` |
| 六、辅助诗性补白 | 位置和风格描述 | `{aux_poetry}` |
| 七、色彩逻辑 | 「高级克制展览级」描述 | `{palette}` `{palette_description}` |
| 八、风格质感 | 全部（质感方法论） | 无 |
| 九、严格禁止 | 通用五条禁止 | `{forbidden}`（各期追加的禁用元素） |
| 输出 | 全部（3:4 比例 + 策展级要求） | 无 |

---

### 5.4 内页模板（INNER_V2_TEMPLATE）

```python
INNER_V2_TEMPLATE = """你是一位顶级海报艺术家，正在创作 All In Podcast 中文知识库的**内页**。
风格基底：手绘水彩 + 剪纸拼贴 + 东方艺术质感（参考国风/日系艺术海报传统），
保留"词义转译+图文融合+意境"的概念海报基因，
同时拥抱"多模块+清晰阅读"的信息图功能。

整体气质：像一张被精心装裱过的展览说明册内页——
有阅读密度，但不堆砌；有信息层级，但不分栏割裂；
每个图标和文字都是从画面内部"长出来"的，而不是贴上去的。

━━━━━ 一、章节定位 ━━━━━
本页主题：「{page_title}」
核心隐喻词：「{core_keyword}」（贯穿全页的视觉母题）
副标题：「{page_subtitle}」

整张内页要围绕「{core_keyword}」这个核心隐喻展开——
{core_keyword} 的剪影、轮廓、阴影、痕迹，可以以装饰性方式贯穿画面，
作为整页的视觉母题，让 3 个要点都"附着"在这个母题上。
{cross_page_motif_hint}

━━━━━ 二、版面结构（统一场域，分而不割）━━━━━
顶部：巨型章节标题「{page_title}」（占约 15-20% 高度），
配合一个核心视觉母题（{core_keyword} 的水墨/剪纸式剪影）作为标题装饰。

中部主体区（约 65% 高度）：
3 个要点纵向排布或错落分布，每个要点是一个"小展位"——
有手绘图标、关键标签、说明文字，并且**自然嵌入到整体画面中**。
不是 3 个独立的卡片框，而是 3 个有机融合在主视觉中的视觉群落。
要点之间可以用手绘箭头、墨迹连线、或视觉过渡相连。

底部：核心金句或本期标识小字，作为整页的余韵与署名。

━━━━━ 三、要点内容（必须完整呈现）━━━━━
{points_text}

每个要点的"标签"要用稍大、稍醒目的字体表达（如毛笔字、剪纸字效），
"说明文字"用清晰但不抢戏的小字嵌入到图标边缘或下方，
留白要充足，不要把内容塞满。

━━━━━ 四、视觉一致性 ━━━━━
- 与封面海报使用相同的色彩语言（本期色组 {palette}，见 poster_template.py 配色矩阵）
- 手绘水彩+剪纸拼贴质感
- 字体和封面保持一致（毛笔/书法/宋体艺术化）
- 留白和呼吸感与封面呼应

━━━━━ 五、严禁 ━━━━━
- 不要做成 3 个矩形信息卡的拼接
- 不要堆图标（每个要点最多 1 个核心图标）
- 不要出现错字、缺笔、变形字
- 不要英文界面元素、页码、版本号
- 不要俗艳渐变、廉价模板感

━━━━━ 六、辅助文字 ━━━━━
允许在画面留白处加 1 句诗性短语（贯穿全页主题）：
{aux_poetry}
位置克制，像题跋或落款一样。

底部右下角小字：「All In 中文笔记」（系列标识）

━━━━━ 输出 ━━━━━
竖版 3:4 比例。要让翻页阅读这本"知识册"的人，每翻到一页都觉得：
画面有意境、信息有重量、阅读有节奏、视觉有惊喜。
"""
```

**各节说明**：

| 节 | 不变骨架 | 填空参数 |
|----|---------|---------|
| 一、章节定位 | 母题贯穿原则 | `{page_title}` `{core_keyword}` `{page_subtitle}` `{cross_page_motif_hint}` |
| 二、版面结构 | 全部（三段式结构原则） | `{page_title}` `{core_keyword}` |
| 三、要点内容 | 标签/说明字体描述 | `{points_text}`（由 `{points}` 数组渲染） |
| 四、视觉一致性 | 全部方法论 | `{palette}` |
| 五、严禁 | 全部（5 条禁止） | 无 |
| 六、辅助文字 | 位置和落款描述 | `{aux_poetry}` |
| 输出 | 全部 | 无 |

---

### 5.5 参数清单与提取来源

#### 封面参数

| 参数名 | 类型 | 来源 | 示例值 |
|--------|------|------|--------|
| `episode` | str | 飞书记录「期号」字段 | `"E270"` |
| `date` | str | 飞书记录「发布日期」字段 | `"2026-04-24"` |
| `duration` | str | 飞书记录「时长（分钟）」字段转换 | `"90分钟"` |
| `views` | str | 飞书记录「YouTube播放量」字段格式化 | `"44万"` |
| `topic` | str | 飞书记录「主题分类」字段 | `"科技&AI"` |
| `title` | str | 飞书记录「中文标题」字段 | `"SpaceX收购Cursor：算力入口重构产业链"` |
| `core_word` | str | 主会话从中文标题提取 2–4 字核心词 | `"算力入口"` |
| `sub_words` | str | 主会话从五维分析①提取三短语，用「·」连接 | `"特洛伊木马·债务炸弹·第四朵云"` |
| `context` | str | 主会话撰写，本期核心词的语境背景（1–2句） | `"讨论 SpaceX 申请收购 AI 编程工具 Cursor..."` |
| `core_word_symbolism` | str | 主会话撰写，核心词的象征性拆解（2–4句） | `"「算力」象征：庞大、坚硬、稀缺的基础设施..."` |
| `metaphor_options` | str | 主会话预设 3–4 个视觉隐喻方向（A/B/C/D格式） | `"A. 微小人影站在巨型「入口」字下方光中..."` |
| `palette` | str | 主会话根据议题气质选定（A/B/C/D） | `"D"` |
| `palette_description` | str | 由 `pick_palette()` 从 COLOR_PALETTES 生成 | `"藏青 #1B365D + 暖金 #C8A35F + 米白..."` |
| `aux_poetry` | str | 主会话撰写，诗性短语 1–2 句 | `"- 「工具是入口，算力是终局」\n- 「咽喉之争」"` |
| `forbidden` | str | 主会话追加，各期特定禁用元素（可为空） | `""` |

#### 内页参数

| 参数名 | 类型 | 来源 | 示例值 |
|--------|------|------|--------|
| `page_title` | str | 五维章节名（固定5个之一） | `"核心议题"` |
| `core_keyword` | str | 主会话为本页选定的隐喻词 | `"特洛伊木马"` |
| `page_subtitle` | str | 主会话撰写，本页核心行动描述 | `"SpaceX 用 Cursor 切入企业算力"` |
| `points` | list[dict] | 主会话从五维分析对应维度提取 | `[{"label":"工具是入口","text":"...","icon_hint":"..."}]` |
| `points_text` | str | 由 `render_inner_prompt()` 从 `points` 渲染 | （自动生成，不手填） |
| `palette` | str | 与封面同一色组 | `"D"` |
| `aux_poetry` | str | 主会话撰写，贯穿本页主题的短语 | `"木马入门，算力为王"` |
| `cross_page_motif_hint` | str | 主会话撰写，说明母题如何在3要点中贯穿 | `"木马的正面/侧面/阴影分别对应三个要点"` |

---

### 5.5b 字色/配色宪法（V3 纯原则版）

**位置**：`scripts/shared/poster_template.py`

V3 从「硬编码 ink / 4 组预设色板」升级为「对比度语义 + 情绪库 + AI 判断」。模板不再要求主流程选择 A/B/C/D，也不再通过 `pick_palette()` 强制套色；主流程只负责把内容语境交给模板，色彩由 prompt 内的原则约束和情绪映射库指导 AI 判断。

**5 条原则概述**：

1. 配色情绪映射：危机、算力、增长、医疗、能源、博弈等情绪分支给出软指导，AI 可按文化背景微调。
2. 配色克制：每张图最多 1 个主色、1-2 个强调色、1 个装饰色、1 个中性背景，合计不超过 4 色。
3. 字色对比度：所有可读文字与背景对比度必须 ≥ 4.5:1，按 WCAG AA 作为手机阅读基准。
4. 印章式标签：深色字 + 鲜色底，禁用鲜色字 + 浅色底。
5. 同期一致性：同一期 4 张内页 + 1 张封面共用同一组配色，不能每页换调色板。

**跨模板统一注入契约**：

`render_cover_prompt()` / `render_inner_prompt()` 自动合并三类常量：

```python
merged = {
    "color_principles": COLOR_PRINCIPLES,
    "emotion_hints": _format_emotion_hints(),
    "text_color_rules": TEXT_COLOR_RULES,
    **params,
}
```

`COVER_V2_TEMPLATE`、`INNER_V2_TEMPLATE` 和未来新模板都通过占位符接收这三段规则。修改色彩规则时，只改 `COLOR_PRINCIPLES`、`EMOTION_PALETTE_HINTS`、`TEXT_COLOR_RULES`，不在各模板里散写局部规则。

### 5.5c 未来加新模板的契约

任何新加的 prompt 模板（如 future social-share-card / weibo-thumbnail / xhs-cover / 商品拆解变体），必须遵守：

1. 模板字符串里同时加入 `{color_principles}`、`{emotion_hints}`、`{text_color_rules}` 三个占位符。
2. 对应 `render_xxx_prompt(params)` 函数必须 merge `COLOR_PRINCIPLES`、`_format_emotion_hints()`、`TEXT_COLOR_RULES` 三个常量。
3. 修改色彩规则只改对应常量，所有模板自动同步；不要在模板字符串或调用方里重新实现色板选择。

---

### 5.6 配色原则与情绪库

`scripts/shared/poster_template.py` 中的 `COLOR_PRINCIPLES` 是硬约束和软指导的总纲，覆盖情绪映射、配色克制、字色对比度、印章标签和同期一致性。

`EMOTION_PALETTE_HINTS` 是情绪到色调的参考库，不是强制预设色板。当前包含危机/破产、算力/AI/科技、增长/创新、医疗/教育、能源/自然、博弈/对抗、电商/引流/轻盈和默认分支。AI 根据内容语境从库中参考并自由判断，调用方不再传 `palette` 参数。

---

### 5.7 隐喻方向预设

主会话在生成封面 prompt 时，需要为 `metaphor_options` 参数提供 3–4 个具体的视觉隐喻方向。给定核心词，用以下框架推导：

**推导原则**：核心词 = 名词1（基础意象）+ 名词2（关系意象）。分别为每个名词找 2 个可视化物体，再找 1 个「两者组合」的叙事意象，共 3–4 个方向。

**已验证示例**：

| 核心词 | 隐喻方向 A | 隐喻方向 B | 隐喻方向 C | 隐喻方向 D |
|--------|-----------|-----------|-----------|-----------|
| 算力入口 | 微小人影站在巨型「入口」字下方光中，门内无限纵深 | 「算力」字底部是数据中心建筑群剪影，「入口」字内透出朱红色光 | 手绘特洛伊木马剪影从「算力」字内驶出，朝向远方城市 | 巨型字下方水墨晕染通道场景，一两个手绘小角色驻足前方 |
| 债务炸弹 | 倒计时器表盘被债务数字填满，引信即将引爆 | 裂缝从摩天大楼底部向上蔓延，「债务」字嵌入裂缝 | 手绘铁链缠绕着一枚老式炮弹，数字刻在链条上 | 巨型「炸弹」剪影内部是货币和利率数字的水墨晕染 |
| 第四朵云 | 三朵灰云稳定漂浮，一朵新云从地平线冉冉升起，体量更大 | 四朵云对应四个云厂商 logo（手绘轮廓），第四朵最亮 | 新云从旧有三云的缝隙中破出，有明确的方向感和上升张力 | 天空视角仰望，四朵云各有姿态，第四朵遮住了太阳 |

**主会话填写 `metaphor_options` 时的提示**：

```
为核心词「{core_word}」在本期语境（{context_brief}）下，提供 A/B/C/D 四个视觉隐喻方向：
A. 聚焦名词1的物化意象
B. 聚焦名词2的物化意象
C. 两者组合的叙事意象（最有命运感）
D. 抽象/留白型（适合水墨晕染）
```

---

### 5.8 验收标准（机械可检查）

- [ ] `scripts/shared/poster_template.py` 文件存在
- [ ] 文件中包含 `COVER_V2_TEMPLATE` 字符串常量
- [ ] 文件中包含 `INNER_V2_TEMPLATE` 字符串常量
- [ ] 文件中包含 `render_cover_prompt(params)` 函数（接受 dict，返回 str）
- [ ] 文件中包含 `render_inner_prompt(params)` 函数（接受 dict，返回 str）
- [ ] `generate_sketchnote.py`（K2完成后）从 `poster_template` import，不再内联定义模板
- [ ] `gen_image.py`（K5完成后）同上
- [ ] 模板字符串中包含「手绘水彩」「剪纸拼贴」「东方艺术质感」三个关键词（风格基底保留）
- [ ] 模板字符串中包含「严禁」段落（至少含「分栏」「页码」两个禁止项）
- [ ] 用 E270 数据填入所有参数，调用 `render_cover_prompt()` 输出 prompt，与 `/tmp/gen_cover_v2.py` 的 PROMPT 效果等价（方法论节不变，可变内容已参数化）
- [ ] E271 新一期套用模板，只填参数，无需任何 prompt 重写

---

## 6. 范围锁（CRITICAL，违反 = 派单失败）

1. 只做 P3-K2 / K3 / K4 / K5 对应的改动，不动 VTT 翻译、飞书写入、收件流程等任何其他代码
2. 读代码时如果发现以下情况，一律不改，写入「发现清单」返回：
   - 其他 bug / 可改进点（不属于本期验收）
   - 其他脚本的提示词或 API 调用（不在白名单文件里）
   - 既存的 TODO/FIXME 注释
3. 发现清单格式（在完成回报末尾附上）：
   ```
   ## 发现清单（本期未处理）
   - 文件:行号 — 一句话描述 — 建议归属期
   ```
4. 主会话按清单单独决策，不在本单处理
