---
name: lark-knowledge-format
version: 6.4.3
description: "飞书文档排版美化：读取现有飞书文档，仅添加视觉格式（颜色/callout/标题样式），不修改任何文字内容，写回文档。触发词：排版、美化、格式化、重排。"
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
用户提供文档URL/token → 读取内容 → 分析结构 → 仅添加视觉格式（不改文字）→ 写回文档
```

## ⛔ 最高优先级约束：禁止修改文字

**原文文字内容必须原封不动保留，以下行为全部禁止：**
- ❌ 禁止删除任何句子、段落或词语
- ❌ 禁止改写、总结、压缩任何文字
- ❌ 禁止新增原文没有的句子或解释
- ✅ 只允许：在原文文字上叠加颜色标签、callout 包装、标题格式化

**自检方法**：排版后去掉所有 `<text>`/`<callout>` 标签，剩下的纯文字应与原文完全一致。

## 核心目标

将飞书文档美化为 **彩色增强版**（仅格式，不改内容）：
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

⚠️ **绝对禁止在正文写 `# 标题`（H1）**：
- 飞书文档的标题已在文档元数据层单独存储，正文若再写 `# xxx` 会显示两个标题
- ❌ 不许写：`# <text color="blue">文章标题</text>`
- ✅ 正文直接从第一个内容块开始（引言区块、Callout、或 `##` 二级标题）
- 若读取到的原文开头有 `# 标题`，**重写时必须删掉这一行**

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

9. ✅ **文字未被修改**：去掉所有格式标签后，纯文字内容与原文完全一致

### 3.6 表格降级规则

**⚠️ 飞书 `<lark-table>` 标签不稳定，一律降级为 Markdown 表格**：

```markdown
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| <text color="red">数据1</text> | <text color="blue">数据2</text> | <text color="green">数据3</text> |
```

### 3.7 教育类资料专项规则

**适用场景**：课堂实录、教学对话、课文解析、讲义等教育类文字资料。

**与通用规则的差异（仅这两点不同，其余完全沿用通用格式规范）**：

| 差异点 | 教育类规则 |
|--------|-----------|
| ❌ 禁止 Callout 高亮块 | 对话/讲课体裁不适合，改用颜色直接着色 |
| ✅ 段落强制分行 | 每段对话/每个内容行之间**必须有空行**，飞书才能正常换段 |

**其余规则完全不变**：颜色密度（每段 2-4 个着色词）、`##` 标题用 `<text color="blue">` 包裹、`<text background-color>` 背景高亮、文字语法——全部照通用规范执行。

**⚠️ 核心提醒：颜色密度不能因为是对话体裁就降低，每个师生发言段落都要有 2-4 个着色词。**

**教育类内容着色指引**：

| 着色对象 | 颜色 | 示例 |
|---------|------|------|
| 课文标题/篇名 | `red` | `<text color="red">十六年前的回忆</text>` |
| 人名/作者 | `blue` | `<text color="blue">李大钊</text>` |
| 年代/数字/时间 | `red` | `<text color="red">1927年</text>` |
| 写作手法/修辞 | `blue` | `<text color="blue">倒叙</text>`、`<text color="blue">首尾呼应</text>` |
| 生字词/重点词 | `orange` | `<text color="orange">避免</text>`、`<text color="orange">严峻</text>` |
| 核心结论/总结语 | `red` 或 `background-color="light-red"` | 教师点睛句 |
| 板书内容 | `background-color="light-yellow"` | `[板书：xxx]` |
| 积极感情/褒义词 | `green` | `<text color="green">坚贞不屈</text>` |
| 師/生 角色标识 | `blue`（师）/ 不着色（生，保持黑色即可） | `<text color="blue">师</text>` |

**示例**（高颜色密度对话）：
```
<text color="blue">师</text>：同学们，今天我们要学的是<text color="red">《十六年前的回忆》</text>，作者是<text color="blue">李星华</text>。

<text color="blue">师</text>：文章开头就写了<text color="red">1927年4月28日</text>，这是一种叫做<text color="blue">倒叙</text>的写法——先写<text color="orange">结局</text>，再回忆<text color="orange">经过</text>。

**生**：为什么要用倒叙？

<text color="blue">师</text>：因为这样写能<text color="green">制造悬念</text>，让读者从第一句话就想知道<text color="red">谁被害了</text>、<text color="red">为什么</text>。
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