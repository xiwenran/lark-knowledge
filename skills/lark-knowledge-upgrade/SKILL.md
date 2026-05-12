---
name: lark-knowledge-upgrade
version: 1.0.0
description: "知识库升级：将多维表格中的高价值记录升级为知识库页面，按资产形态生成结构化正文，自动排版美化。触发词：/升级"
---

# lark-knowledge-upgrade (v1.0.0)

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../lark-shared/SKILL.md`](../lark-shared/SKILL.md)**

## 功能定位

将多维表格中综合评分 ≥ 4 的记录升级为知识库页面，按资产形态生成结构化正文，自动排版美化。

**触发方式**：
- 手动触发：`/升级`，批量处理所有 处理状态=待升级 的记录
- 自动触发：由 `lark-knowledge-intake` Step 4 传入 record_id 调用（同一套流程）

**配置来源**：`~/.agents/skills/lark-knowledge-config/config.json`

---

## Step 1: 获取目标记录

**手动触发**：
```bash
lark-cli base +record-list \
  --base-token "NYJNbo94Pa1k3Ksa96Eci7lZnNf" \
  --table-id "tbl4PyKLq5O1O9ej"
```
筛选：处理状态 = 待升级 AND 综合评分 ≥ 4。如有多条，逐条处理。

**自动触发**：使用传入的 record_id 直接读取该条记录。

若原始内容是飞书文档，重新 fetch 获取最新内容：
```bash
lark-cli docs +fetch --doc "<原始链接>" --format markdown
```

---

## Step 2: 撰写正文

按资产形态选模板。内容来源：AI摘要 + 原始内容。

### 标题提炼规范（必须遵守）

知识库页面标题**基于原文标题改写**，不凭空发明。改写方向：更具体、更有结果感、让读者一眼知道能得到什么。

**改写公式**：`细分场景/工具 + 核心方法 + 具体结果/数字`

| 原文标题 | 改写示例 |
|---------|---------|
| 分享6个我觉得应该必装的Skills | 必装6个Claude Skills：前端设计/联网/记忆持久化，精准匹配工作流 |
| 我是如何做小红书的 | 小红书从0到1：AI编程+带货图文，30天540单5346元被动收入复盘 |

**规则**：
- ✅ 保留原文核心主题，不偏离内容
- ✅ 补充原文已有但标题未体现的具体数字/结果
- ✅ 加入场景/工具词让内容更具象
- ❌ 不加原文没有的数据或结论
- ❌ **正文开头禁止写 `# 标题`**：标题已通过 `--title` 参数设置为文档标题，正文重复写会导致标题显示两次

### 通用格式要求（所有资产形态强制遵守）

**成品页**结构：
```
> 📌 **[资产定位]** 一句话定位（关键数据用 <text color="red"> 标注）

<callout emoji="bulb" background-color="light-yellow">
**核心结论**：...
</callout>

---

## <text color="blue">一、[章节标题]</text>
[正文，含表格/Callout/Grid]

...（5-8 章节）...

---

## 知识库索引

<lark-table rows="N" cols="2" header-row="true" column-widths="350,350">
  <lark-tr><lark-td>文档</lark-td><lark-td>链接</lark-td></lark-tr>
  <lark-tr><lark-td>主成品页</lark-td><lark-td>[标题](主成品页URL)</lark-td></lark-tr>
  <lark-tr><lark-td>[专题]视角</lark-td><lark-td>[标题（专题视角）](URL)</lark-td></lark-tr>
  <lark-tr><lark-td>原始文档</lark-td><lark-td>[原始标题](原始URL)</lark-td></lark-tr>
</lark-table>
```

**关联页（视角提炼页）**头部固定：
```
> 📌 **提炼视角**：从[专题名]角度提取核心要点，适合...的读者参考。
```
比主成品页精简约 50%，聚焦该专题视角。结尾同样包含知识库索引表。

### 统一章节结构：商业洞察5维框架

**5维框架是整个知识库的底层分析逻辑，所有资产形态、所有专题的成品页和视角提炼页均使用此框架撰写正文。**

#### 主成品页章节结构（所有资产形态通用）

```
> 📌 **[资产定位]** 一句话定位（关键数据用 <text color="red"> 标注）

<callout emoji="bulb" background-color="light-yellow">
**核心结论**：[一句话提炼最重要的商业洞察]
</callout>

---

## <text color="blue">一、产品形态</text>
提供什么价值？层级（资料包/工具/系统/服务/方法论/内容）？交付方式？完成度如何？

## <text color="blue">二、流量与转化路径</text>
用户如何找到并信任它？内容→成交/应用路径？作者/创作者期待什么"回报"？

## <text color="blue">三、赛道与竞争格局</text>
聚焦哪个细分赛道？处于哪个阶段（蓝海/成长/红海）？竞争烈度与差异化优势？

## <text color="blue">四、操盘手画像</text>
谁在背后做/写？处于什么阶段（0→1 / 1→10 / 成熟）？核心能力倚仗？思维模式？

## <text color="blue">五、机会洞察</text>
我能拿走什么？可借鉴/复制要素？模式迁移机会？需求延伸机会？切入点与风险？

---

## 知识库索引
（标准索引表）
```

#### 视角提炼页章节结构

视角提炼页使用**相同的5维框架**，但每一章聚焦该专题的特定角度：

| 专题视角 | 各章聚焦方向 |
|---------|-----------|
| 小红书视角 | 从流量/内容/平台规则角度看每一维 |
| 虚拟资料产品视角 | 从产品设计/交付/定价角度看每一维 |
| AI编程视角 | 从技术/工具/自动化角度看每一维 |
| 小红书虚拟产品视角 | 从商品选品/竞品调研角度看每一维 |

视角提炼页比主成品页精简约 50%，每章提炼 2-3 个该视角下最关键的要点，不重复主成品页的全量内容。

---

## Step 3: 创建知识库页面

目录 token 从 config.json `wiki.directories` 读取（专题 + 资产形态对应子目录）。

```bash
# 主成品页（主专题目录）
lark-cli docs +create \
  --title "<标题>" \
  --wiki-node "<config wiki_directories[主专题][资产形态目录]>" \
  --markdown "<完整正文内容>"

# 视角提炼页（辅助专题目录，案例包必建；其他资产形态按专题归属数量决定）
lark-cli docs +create \
  --title "<标题>（<辅助专题>视角）" \
  --wiki-node "<config wiki_directories[辅助专题][资产形态目录]>" \
  --markdown "<该专题视角提炼内容>"
```

记录所有新建页面的 wiki token，供后续步骤使用。

---

## Step 3.5: 交叉引用补全

### 3.5a — 查询同专题已升级记录

```bash
lark-cli base +record-list \
  --base-token "NYJNbo94Pa1k3Ksa96Eci7lZnNf" \
  --table-id "tbl4PyKLq5O1O9ej"
```

筛选：`处理状态 = 已升级` AND `专题归属 包含 <当前主专题>` AND `record_id ≠ 当前记录`。
取 [标题]、[关键词标签]、[资产形态]、[知识库页面链接] 字段。

### 3.5b — LLM 识别相关词条（最多 5 个）

将当前记录的 [关键词标签] + [AI摘要] 与候选记录逐一对比，选取相关度最高的 **2–5 条**。

判断标准（按优先级）：
1. 关键词标签有 ≥2 个交集
2. 主题领域相同（同一方法论的不同视角、同一场景的不同工具）
3. 资产形态互补（案例包 ↔ 方法论、SOP ↔ 模板）

若无符合条件的相关词条（知识库首条、完全独立主题）→ **跳过 3.5c 和 3.5d**，完成汇总注明"暂无相关词条"。

### 3.5c — 在新主成品页追加相关词条表格

仅操作**主成品页**（视角提炼页不操作）：

```bash
lark-cli docs +update --doc "<主成品页wiki_token>" --mode append --markdown "
## 相关词条

| 词条 | 专题 | 资产形态 |
|-----|------|---------|
| [标题A](URL_A) | 专题A | 资产形态A |
| [标题B](URL_B) | 专题B | 资产形态B |
"
```

### 3.5d — 反向链接：更新现有相关页面

对 3.5b 中每个相关词条页面，逐一处理：

1. `lark-cli docs +fetch --doc "<页面wiki_token>" --format markdown`
2. 检查是否已有 `## 相关词条` 表格：
   - **有** → `+update --mode append` 追加新行：`| [新页面标题](新页面URL) | 专题 | 资产形态 |`
   - **没有** → `+update --mode append` 追加含表头的完整相关词条表格

⚠️ 每个页面独立处理，失败时记录 `⚠️ 反向链接失败：<标题>`，不中断主流程。

---

## Step 4: 补全知识库索引表

确认所有页面底部已包含知识库索引表（见 Step 2 格式），链接须覆盖：主成品页、各视角提炼页、原始文档。

若创建时未写入，追加：
```bash
lark-cli docs +update --doc "<wiki_token>" --mode append --markdown "<索引表内容>"
```

---

## Step 5: 回填多维表格

> ⚠️ select 字段必须用数组格式，否则 lark-cli 静默失败、字段不更新

```bash
lark-cli base +record-upsert \
  --base-token "NYJNbo94Pa1k3Ksa96Eci7lZnNf" \
  --table-id "tbl4PyKLq5O1O9ej" \
  --record-id "<record_id>" \
  --json '{
    "处理状态": ["已升级"],
    "知识库页面链接": "<主成品页URL>",
    "升级状态": ["已完成"]
  }'
```

**执行后验证**：确认返回 `"updated": true`；若为 `false` 或报错，重试一次后告知用户。

---

## Step 6: 自动排版

对每个新建页面执行排版，参照 [`../lark-knowledge-format/SKILL.md`](../lark-knowledge-format/SKILL.md) 完整流程（fetch → 彩色增强版重写 → overwrite 写回）。

---

## Step 7: 生成拆解笔记（可选）

**触发条件**：用户说「生成拆解笔记」或「生成手绘笔记」，针对刚升级的页面生成小红书发布用的手绘拆解图。

**⚠️ 内容定位**：这是「产品拆解分析 + 实操经验分享」，不是「商品推荐」。用方法论洞察视角，避免推荐/种草/安利措辞。每页以一个反常识洞察开头，让读者产生"原来如此"的认知增量。

### 7a — 选题与故事线设计

从主成品页的五维分析中，提取最值得深挖的 1–2 个洞察点。每个洞察点将独立生成一组图片（封面 + N 张内页）。

选题标准——每个洞察点必须回答"读者看完后什么发生了变化"，至少命中一种：
- **认知刷新**：改变读者对某件事的理解方式（"原来不是A，是B"）
- **判断框架**：给读者一个可反复使用的判断标准
- **行动抓手**：读者看完能马上检查/验证/行动的具体方法

❌ 不合格的选题："这个产品卖了4000单"（只是事实）
✅ 合格的选题："9块9卖的不是PPT，是省掉的3小时——你做虚拟产品也应该这样定位"（认知刷新+行动抓手）

为选中的洞察点设计 `story_plan`（JSON 格式），写入 analysis 数据传给 `gen_image.py`：

```json
{
  "story_plan": {
    "angle": "定价逻辑背后的时间换算",
    "cover_title": "9块9卖的不是PPT，是省掉的3小时",
    "pages": [
      {
        "title": "用户买的不是资料，是确定感",
        "highlight": "大部分人觉得虚拟资料卖的是内容——错了。买家花的不是9块9买50页PPT，是买今晚不用加班做课件。",
        "sections": [
          { "label": "核心卖点", "content": "标题写的是'直接用，不用改'——6个字就是核心卖点" },
          { "label": "定价逻辑", "content": "9.9不是终点价，是进门价：阶梯设计 9.9→29.9→79.9" },
          { "label": "对你的启发", "content": "你卖的到底是内容，还是用这个内容能省下的时间？" }
        ]
      },
      {
        "title": "阶梯定价的认知锚点怎么设",
        "highlight": "低到不用决策的价格——看到就买，不用想。",
        "sections": [
          { "label": "进门价", "content": "9.9是不用犹豫的价格，买了之后看到29.9进阶版自然升级" },
          { "label": "信任阶梯", "content": "每一级的转化都建立在上一级的信任上" }
        ]
      },
      {
        "title": "对你做产品意味着什么",
        "highlight": "这个案例最值得学的不是教师PPT怎么卖，而是3个通用设计原则。",
        "sections": [
          { "label": "可复用原则", "content": "卖省的时间、效率对比图替代内容堆砌、差评是最好的选品工具" },
          { "label": "风险提醒", "content": "9.9定价容易引发价格战，唯一壁垒是品牌信任感" }
        ]
      }
    ]
  }
}
```

**字段说明**：`pages` 每项必须包含 `title`（页面标题）、`highlight`（页面顶部的认知冲突金句）、`sections`（内容分区，每个含 `label` 和 `content`）。`gen_image.py` 依赖这三个字段生成内页。

### 7b — 读取页面内容

从刚创建的主成品页（或用户指定的页面）fetch 完整正文：

```bash
lark-cli docs +fetch --doc "<wiki_token>" --format markdown
```

从正文中提取认知驱动的关键素材：
- **核心卖点洞察**：这个产品真正卖的是什么（不是表面的内容/资料，而是背后的时间/效率/安全感）
- **定价逻辑**：为什么定这个价，阶梯设计怎么做
- **流量来源**：搜索 vs 推荐，为什么选这个路径
- **可复用经验**：哪些设计原则可以迁移到其他品类

### 7c — 组装图片提示词

**封面**：用 `scripts/cover-generator/generate.py breakdown` 脚本生成（深墨绿+翡翠绿模板），输入标题+期号即可。不走 gpt-image-2。

**内页视觉风格基底**（内页共用，复用 V2 sketchnote 模板）：

> 使用 `scripts/shared/poster_template.py` 的 `inner_v2` 模板。商品拆解默认使用亮色组配色（`pick_palette({"forced_palette": "A"})`），保持轻盈感。

**前置要求**：analysis 数据必须包含 `story_plan` 字段（由 Step 7a 生成）。`gen_image.py` 从 `analysis.story_plan` 读取 `pages` 列表，页数和标题由 AI 决定，围绕 7a 选定的洞察点展开。没有 story_plan 时脚本会报错。

**每张内页必须有的 3 个元素**：① 一句认知冲突金句（放页面顶部）② 支撑数据/案例/类比 ③ "对你意味什么"的落脚

**提示词组装原则**：
- 从页面实际内容中提取具体数字和结论，不要用泛化描述
- 每张图文字内容控制在 60–100 字以内（图片生成模型对长文本支持有限）
- 用「拆解/分析/洞察/观察」等中性词，禁止「推荐/种草/必买/安利」

### 7d — 调用图片生成（Codex 优先 → API fallback）

**优先方式：派 Codex 生成**

Codex 内置 gpt-image-2 图片生成能力，不消耗用户 API 额度。逐张派发：

```
目标：用 gpt-image-2 生成一张手绘拆解笔记图片
提示词：<风格基底 + 该页内容提示词>
尺寸：1024x1536
保存路径：/tmp/sketchnote_<记录编号>_0N_<主题>.png
```

通过 `codex:codex-rescue` 派发，每张图一个任务，带 `--write`。

**Fallback：Codex 失败时走 API**

若 Codex 报错（额度不足 / 超时 / 生成失败），改用共享图片生成工具。先用 `--prompts-only` 预览 4 张 V2 模板提示词，再按需生成：

```bash
python3 ~/lark-knowledge/scripts/shared/gen_image.py \
  --record-id "<记录编号>" \
  --prompts-only

python3 ~/lark-knowledge/scripts/shared/gen_image.py \
  --record-id "<记录编号>" \
  --output-dir "/tmp" \
  --size "1024x1536"
```

生成完成后汇报路径（封面 SVG + N 张内页 sketchnote），由用户确认质量后自行发布到小红书。页数由 story_plan 决定。

### 7e — 上传到飞书（可选）

若用户要求存档，将图片上传到飞书云盘并追加到页面底部：

```bash
lark-cli drive +upload --file "/tmp/sketchnote_<记录编号>_01_封面.png"
# 获取 file_token 后追加到页面
lark-cli docs +update --doc "<wiki_token>" --mode append \
  --markdown "## 拆解笔记\n\n（图片已上传至飞书云盘）"
```

---

## 完成汇总

```
页面创建完成 ✅  交叉引用完成 ✅  表格回填完成 ✅  排版完成 ✅

<记录编号> | <标题> | 专题：<专题> | 评分：<分>
主成品页：<URL>
视角提炼页：<URL>（若有）
相关词条：<标题A>、<标题B>（若有；若无则显示"暂无相关词条"）
反向链接已更新：<标题A>、<标题B>（若有警告则列出）
```

> 若任一步骤失败，对应 ✅ 改为 ❌ 并说明原因，不得跳过或假装成功。

## 权限

`bitable:record`、`docx:document`、`wiki:node`
