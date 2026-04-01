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

## Step 4: 补全知识库索引表

确认所有页面底部已包含知识库索引表（见 Step 2 格式），链接须覆盖：主成品页、各视角提炼页、原始文档。

若创建时未写入，追加：
```bash
lark-cli docs +update --doc "<wiki_token>" --mode append --markdown "<索引表内容>"
```

---

## Step 5: 回填多维表格

```bash
lark-cli base +record-upsert \
  --base-token "NYJNbo94Pa1k3Ksa96Eci7lZnNf" \
  --table-id "tbl4PyKLq5O1O9ej" \
  --record-id "<record_id>" \
  --json '{
    "处理状态": "已升级",
    "知识库页面链接": "<主成品页URL>",
    "升级状态": "已完成"
  }'
```

---

## Step 6: 自动排版

对每个新建页面执行排版，参照 [`../lark-knowledge-format/SKILL.md`](../lark-knowledge-format/SKILL.md) 完整流程（fetch → 彩色增强版重写 → overwrite 写回）。

---

## 完成汇总

```
升级完成 ✅

<记录编号> | <标题> | 专题：<专题> | 评分：<分>
主成品页：<URL>
视角提炼页：<URL>（若有）
```

## 权限

`bitable:record`、`docx:document`、`wiki:node`
