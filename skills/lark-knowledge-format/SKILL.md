---
name: lark-knowledge-format
version: 6.4.3
description: "飞书文档排版美化：读取现有飞书文档，按飞书正文排版规范（彩色增强版）重写后写回。触发词：排版、美化、格式化、重排。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# 飞书文档排版美化（彩色增强版 v6.4）

**CRITICAL — 开始前 MUST 先用 Read 工具读取：**
1. `../lark-shared/SKILL.md` — 认证、权限
2. `../lark-doc/SKILL.md` — 文档操作（**必须重点阅读** references/lark-doc-create.md 中的 Lark-flavored Markdown 完整格式规范）

## 工作流

```
用户提供文档URL/token → 读取内容 → 分析结构 → 按彩色增强版规范重写 → 写回文档
```

## 核心目标

将飞书文档美化为 **彩色增强版**：
- **颜色密度目标**：每段落 2-4 个着色词，每屏 3-5 处红色
- **视觉层次**：二级标题蓝色、关键词高亮、Grid 分栏展示
- **内容结构**：零列表（全 Callout 化）、多样 emoji、逻辑分块

**参考标准**：https://www.feishu.cn/wiki/STMFws3lIiSmWMktSY5cWVvtndf （KR-0002，自检时对照）

---

## Step 1: 获取文档内容

**1a. 解析输入**
- URL 中提取 node_token（`/wiki/` 或 `/docx/` 后的字符串）
- 直接提供 token 则使用

**1b. 读取文档**
```bash
lark-cli docs read $node_token
```

---

## Step 2: 文档类型判断

结构化内容（有章节层次）→ 直接按 Step 3 重写；流水账内容（纯文本堆砌、无标题分隔）→ 先提炼主题、重组结构，再按 Step 3 重写。

---

## Step 3: 彩色增强版重写规则

### 3.0 写回格式（重要）
⚠️ **绝对禁止在文档正文写 frontmatter**：
- ❌ 不许写：`---\nenable_insert_doc_link: false\n---`
- ✅ 直接写正文内容，无需任何元数据标识

### 3.1 颜色语法表

⚠️ **强制禁令（任何情况都不许出现）**：
- ❌ `<span style="...">...</span>` ← 飞书不识别，强制禁止
- ❌ `font` / `font-weight` / `background` 单独使用
- ✅ 一律使用飞书原生标签：`<text color>` 和 `<text background-color>`

**正确语法（必须有闭合标签）**：

| 效果 | 语法 | 使用场景 |
|------|------|---------|
| 红字 | `<text color="red">文字</text>` | **大量使用**：数字/时间节点/动作词/强调效果 |
| 蓝字 | `<text color="blue">文字</text>` | 概念词/方法论/工具名 |
| 绿字 | `<text color="green">文字</text>` | 积极结果/成功指标 |
| 橙字 | `<text color="orange">文字</text>` | 注意事项/中性数据 |
| 紫字 | `<text color="purple">文字</text>` | 特殊标识/分类标签 |
| 红底高亮 | `<text background-color="light-red">文字</text>` | 强结论/风险提醒 |
| 黄底高亮 | `<text background-color="light-yellow">文字</text>` | 重要概念/关键步骤 |
| 蓝底高亮 | `<text background-color="light-blue">文字</text>` | 方法论/框架思路 |
| 绿底高亮 | `<text background-color="light-green">文字</text>` | 积极结果/成功经验 |
| 组合高亮 | `<text color="red" background-color="light-red">文字</text>` | **超强调**（一个标签两属性） |

### 3.2 标题格式

**二级标题必须用 `<text color>` 包裹**：
- ❌ 错误：`## 一、项目本质 {color="blue"}`
- ✅ 正确：`## <text color="blue">一、项目本质</text>`

### 3.3 Grid 分栏结构

```html
<lark-grid cols="2">
<lark-grid-item>
<text color="blue">① 标题</text>
内容+颜色
</lark-grid-item>
<lark-grid-item>
<text color="blue">② 标题</text>
内容+颜色
</lark-grid-item>
</lark-grid>
```

### 3.4 Callout 高亮块

| emoji | 颜色 | 使用场景 | 比例 |
|-------|------|----------|------|
| 📌 | light-blue | 关键要点/方法论 | 5 |
| 💡 | light-yellow | 启发思考/技巧 | 3 |
| ✅ | light-green | 成功经验/正面结论 | 3 |
| ⚠️ | light-orange | 注意事项/风险提醒 | 2 |
| 🎯 | light-red | 核心目标/强结论 | 1 |

```html
<callout emoji="📌" background-color="light-blue">
<text color="blue">关键认知</text>：内容 <text color="red">重点词</text> 更多内容。
</callout>
```

### 3.5 写回前自检清单 ⚠️

**逐项检查（强制执行）**：

1. ✅ **`</text>` 闭合**：所有 `<text>` 必须有 `</text>`
   - ❌ 错误：`<text color="red">40%+，`
   - ✅ 正确：`<text color="red">40%+</text>，`

2. ✅ **无嵌套 `<text>` 标签**：颜色+背景用单标签两属性
   - ❌ 错误：`<text color="red"><text background-color="light-red">文字</text></text>`
   - ✅ 正确：`<text color="red" background-color="light-red">文字</text>`

3. ✅ **列表→Callout**：零列表，全部改为 Callout
   - ❌ 错误：`- 要点1` `- 要点2`
   - ✅ 正确：两个独立 Callout

4. ✅ **标题用 `<text color>` 包裹**：
   - ❌ 错误：`## 标题 {color="blue"}`
   - ✅ 正确：`## <text color="blue">标题</text>`

5. ✅ **每章节 ≥1 Callout**：增强视觉层次

6. ✅ **每句话自查：有没有颜色？** 目标每段 2-4 个着色词

7. ✅ **主文档标题有颜色或 Callout**：
   - ❌ 错误：`# 纯标题`
   - ✅ 正确：`# <text color="blue">标题</text>` 或下方加 Callout

8. ✅ **对照参考页**：检查颜色密度是否达到 KR-0002 标准

### 3.6 表格降级规则

**⚠️ 飞书 `<lark-table>` 标签不稳定，一律降级为 Markdown 表格**：

```markdown
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| <text color="red">数据1</text> | <text color="blue">数据2</text> | <text color="green">数据3</text> |
```

---

## Step 4: 写回文档

**4a. overwrite 写回**
```bash
lark-cli docs update $node_token --overwrite "重写后的完整内容"
```

**4b. 确认更新**
```bash
lark-cli docs read $node_token --limit 100
```

**最终检查**：写回成功后，确认文档在飞书中正确显示彩色效果。