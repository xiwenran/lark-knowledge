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

### 按资产形态展开章节

| 资产形态 | 成品页章节结构 | 视角提炼页 |
|---------|-------------|----------|
| 方法论 | 核心理念 / 运作原理 / 实操要点 / 常见误区 / 应用场景 | 每辅助专题独立提炼页 |
| SOP | 前提条件 / Step 1-N / 验证标准 / 注意事项 | 聚焦操作步骤 |
| 模板 | 使用说明 / 模板正文 / 填写示例 | 聚焦适用场景 |
| 技巧集 | 技巧列表（每条 Callout） | 聚焦核心技巧 |
| 案例包 | 背景与挑战 / 解决方案 / 结果与数据 / 可复制要素 | 每辅助专题一个视角提炼页 |

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
