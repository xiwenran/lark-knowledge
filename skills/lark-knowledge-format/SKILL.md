---
name: lark-knowledge-format
version: 6.3.0
description: "飞书文档排版美化：读取现有飞书文档，按飞书正文排版规范（彩色增强版）重写后写回。触发词：排版、美化、格式化、重排。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# 飞书文档排版美化（彩色增强版 v6）

**CRITICAL — 开始前 MUST 先用 Read 工具读取：**
1. `../lark-shared/SKILL.md` — 认证、权限
2. `../lark-doc/SKILL.md` — 文档操作（**必须重点阅读** references/lark-doc-create.md 中的 Lark-flavored Markdown 完整格式规范）

## 工作流

```
用户提供文档URL/token → 读取内容 → 分析结构 → 按彩色增强版规范重写 → 写回文档
```

### Step 1: 读取文档

```bash
lark-cli docs +fetch --doc "<url_or_token>" --format markdown
```

### Step 2: 分析内容结构

识别：文档类型（方法论/SOP/模板/技巧集/案例包）、核心内容块（标题/正文/列表/重点/警告）、适合用分栏/表格的部分。

### Step 3: 按彩色增强版规范重写

> **核心目标**：整体风格采用"知识型长文 + 小红书资料感 + 内容海报化表达"。**每句话至少2-4个关键词着色**，重点句用 `<text color+background>` 组合强强调。效果参考：https://www.feishu.cn/wiki/STMFws3lIiSmWMktSY5cWVvtndf

#### 3.0 写回格式（重要）

> ⚠️ **写回文档时禁止包含 YAML frontmatter！**
> `---enable_insert_doc_link: false---` 这类 frontmatter 如果写在正文里会成为可见文本。
> 正确做法：**直接写正文内容，不要用 `---` 包裹任何内容**。

#### 3.1 稳定语法速查表

> 🚫 **CRITICAL — 严禁使用标准 HTML 样式标签！**
> 飞书只识别自己的专属标签语法，以下写法**全部无效，会直接显示为原始文本**：
> - ❌ `<span style="color: red;">` → 飞书不识别
> - ❌ `<span style="background-color: yellow;">` → 飞书不识别
> - ❌ `<font color="red">` → 飞书不识别
> - ❌ `<b style="color:red">` → 飞书不识别
>
> **只能用飞书专属标签：**
> - ✅ `<text color="red">关键词</text>`
> - ✅ `<text background-color="light-yellow">关键词</text>`
> - ✅ `<text color="red" background-color="light-red">关键词</text>`

> ⚠️ **CRITICAL：`<text>` 标签必须闭合！每个 `<text ...>` 都必须有对应的 `</text>`，否则颜色不渲染。不可嵌套 `<text>` 标签。**

| 能力 | 正确语法示例 | 状态 |
|------|------------|------|
| 文字颜色 | `<text color="red">关键词</text>` | ✅ 稳定，适用于**正文/Callout/Grid栏/表格单元格** |
| 背景高亮 | `<text background-color="light-yellow">关键词</text>` | ✅ 稳定，适用于**正文/Callout/Grid栏/表格单元格** |
| 颜色+背景同时用 | `<text color="red" background-color="light-red">关键词</text>` | ✅ 单标签写两个属性，**不可嵌套两个`<text>`** |
| Callout 背景色 | `background-color="light-red/light-blue/light-green/light-yellow/light-orange/light-purple"` | ✅ 稳定 |
| 标题颜色 | `## <text color="blue">一、标题</text>` | ✅ 稳定，**必须用 `<text>` 标签包裹标题文字**，不可用 `{color="..."}` 属性 |
| Grid 分栏 | `<grid cols="2"><column>...</column><column>...</column></grid>` | ✅ 稳定，栏内颜色使用与正文完全一致 |
| 分割线 | `---` | ✅ 稳定 |
| Markdown 表格 | `\| 列1 \| 列2 \|` | ✅ 稳定，表格内颜色使用与正文完全一致 |
| 加粗/下划线 | `**加粗**` / `<u>下划线</u>` | ✅ 稳定 |
| 有序/无序列表 | `- ` / `1. ` | ⚠️ **最低优先级，优先用 Callout 替代，尽量少用** |

**可用颜色值：**
- 文字色：`red` / `blue` / `green` / `orange` / `yellow` / `purple` / `gray`
- 背景色：`light-red` / `light-blue` / `light-green` / `light-yellow` / `light-orange` / `light-purple` / `red` / `blue` / `green`

#### 3.2 标题统一规则

- **文档主标题**：大字号、加粗、黑色，作为全页唯一最高视觉中心
- **二级章节标题**：统一使用 `<text color="blue">...</text>` 包裹标题文字，保证全篇结构统一，格式如下：

```markdown
## <text color="blue">一、项目本质</text>
## <text color="blue">二、市场判断</text>
## <text color="blue">三、实操流程</text>
## <text color="blue">四、核心结论</text>
```

- 二级标题可固定加同风格 emoji，但全篇统一逻辑：
  - 📌 定位 — 💡 核心结论 — ✅ 建议 — ⚠️ 注意 — ❌ 误区 — 📊 数据 — 🔧 工具 — 🚀 总结
- **三级小标题**：默认黑色加粗，不频繁换色，避免全篇色彩失控

#### 3.3 正文排版规则

- 正文采用**单栏左对齐**，自上而下连续阅读
- 每段控制在 1–3 句，**避免大段密集文字**
- 段间保持明显留白，重点句、转折句、结论句前后留白加大
- 正文必须形成"**普通正文 → 彩色重点句 → Callout → 表格/分栏**"的混合节奏
- 不能全篇都是纯段落，每屏都要有视觉抓手

#### 3.4 色彩使用总原则

**推荐配色角色分工：**

| 颜色 | 文字色用途 | 背景色用途 |
|------|-----------|-----------|
| `red` | **大量使用**：强结论、核心数字、时间节点、动作关键词、强调效果的短语（如"更高付费率"、"3天内"、"无需从零设计"、"效果显著"）| 风险、痛点、最强警示 |
| `blue` | 核心概念、方法名、平台名、工具名 | 定义、方法、关键知识点 |
| `green` | 机会点、建议、正向结果、建议动作 | 机会点、建议、增长点 |
| `purple` | 收益、适用对象、补充亮点 | 收益、亮点、加分项 |
| `orange` | 提醒、注意点、次强调（不如红色醒目时用） | 通用高亮 |
| `gray` | 补充说明、对比项中的劣势方、次要信息 | — |

**使用原则：**
- `red` 是主力颜色，全篇用量最多，不要吝啬
- 同一屏内主色不超过 3-4 种，避免杂乱
- 颜色优先服务信息层级，不只是装饰
- 单段内文字颜色最多 2–3 种，不可七彩混排

**颜色密度目标（重要）：**
- 每个正文段落：**至少 2-4 个**关键词着色，不能整段纯黑字
- 每个 Callout 内部：**至少 2-3 处**文字颜色或背景高亮
- 每个 Grid 栏内：**至少 1-2 个**着色词
- 每个表格单元格：数据列 / 强调列**必须**着色，普通说明列可不着色
- 整页红色词出现频率：**每屏至少 3-5 处**红色

#### 3.5 行内文字颜色规则

**适用于：正文段落 / Callout 内部 / Grid 栏内 / 表格单元格内**

- 用于突出**关键词、关键短句、结论句中的核心部分**
- `red` 是主力颜色，用途宽泛，以下都可以用红色：
  - 核心数字（付费率、收益、人数、天数）
  - 时间节点（"3天内"、"1天"、"5篇"）
  - 强调动作（"边做边迭代"、"重点打磨"、"无需从零设计"）
  - 强调效果（"效果显著"、"成交转化更快"、"更高付费率"）
  - 最重要的结论句片段
- 句子里需要"跳出来"的部分优先用组合：
  - `red + background-color="light-red"`：最强强调
  - `blue + background-color="light-blue"`：方法/工具定义
  - `green + background-color="light-green"`：建议/正向结果
  - `orange + background-color="light-yellow"`：提醒/注意
  - `purple + background-color="light-purple"`：收益/亮点

#### 3.6 行内背景色规则

**适用于：正文段落 / Callout 内部 / Grid 栏内 / 表格单元格内**

- 背景高亮优先用于**高亮短语、关键词、极短重点句**，不用于整大段
- 推荐背景色：
  - `light-yellow`：通用高亮，最常用
  - `light-red`：风险、痛点、强警示
  - `light-green`：机会点、建议、增长点
  - `light-blue`：定义、方法、关键知识点
  - `light-purple`：收益、亮点、加分项
- 深色背景（`red/blue/green`）仅**少量使用**，制造强视觉停顿，不可频繁出现

#### 3.7 重点句排版规则

- **核心结论、金句、判断句必须单独成段**，不要埋在正文里
- 重点句优先使用以下组合：
  - 彩色文字 + 背景高亮
  - 必要时加粗
  - 必要时加下划线

**推荐句级强调组合（单标签写两个属性）：**

| 类型 | 正确写法示例 |
|------|------------|
| 强结论 | `<text color="red" background-color="light-red">核心结论</text>` |
| 方法定义 | `<text color="blue" background-color="light-blue">方法名</text>` |
| 建议动作 | `<text color="green" background-color="light-green">建议内容</text>` |
| 警示提醒 | `<text color="orange" background-color="light-yellow">注意事项</text>` |
| 收益总结 | `<text color="purple" background-color="light-purple">收益描述</text>` |

> ⚠️ 禁止写成 `<text color="red"><text background-color="light-red">文字</text></text>`（嵌套写法），必须用单标签两个属性。

#### 3.8 Callout 使用规则

**每个章节至少 1 个 Callout，重点章节可 2–3 个。**

**5 类固定类型（高频使用）：**

```html
<!-- 📌 定位 → light-blue -->
<callout emoji="📌" background-color="light-blue">
**定位**：本页解决的问题/适用场景/前置条件
</callout>

<!-- 💡 核心结论 → light-yellow -->
<callout emoji="💡" background-color="light-yellow">
**结论**：一句话核心结论
</callout>

<!-- ✅ 建议 → light-green -->
<callout emoji="✅" background-color="light-green">
**建议**：具体可执行的方法或行动
</callout>

<!-- ⚠️ 注意 → light-orange -->
<callout emoji="⚠️" background-color="light-orange">
**注意**：需要特别关注的事项或边界条件
</callout>

<!-- ❌ 误区 → light-red -->
<callout emoji="❌" background-color="light-red">
**误区**：常见错误做法及正确替代
</callout>
```

**Callout 内部颜色使用规则与正文完全一致，均适用 3.5 / 3.6 的颜色语法和配色原则。**

#### 3.9 分栏与表格规则

**并列/对比信息优先用 Grid 分栏，栏内颜色使用规则与正文完全一致（适用 3.5 / 3.6）：**

```html
<grid cols="2">
<column>

**痛点**

<text background-color="light-red">核心痛点描述</text>

</column>
<column>

**解法**

<text color="green">解决方案描述</text>

</column>
</grid>
```

**对比/数据优先用 Markdown 表格：**

```markdown
| 维度 | 错误做法 | 正确做法 |
|------|---------|---------|
| 心态 | 追求完美 | 快速验证 |
| 执行 | 等工具完善 | 边做边迭代 |
```

**分栏适合场景：**
- 痛点 vs 解法
- 错误做法 vs 正确做法
- 低价产品 vs 高价产品
- 阶段1 vs 阶段2

**表格适合场景：**
- 数据汇总
- 用户分层
- 产品结构
- 对比分析

**表格内颜色使用规则与正文完全一致（适用 3.5 / 3.6），局部单元格可使用文字颜色和背景高亮做强调。**

#### 3.10 页面节奏规则

**每个章节建议包含以下至少 3 种元素：**
- 彩色标题（二级）
- 彩色重点句（文字颜色/背景高亮）
- Callout
- 列表（少量）
- 分割线
- 表格
- 分栏

**节奏原则：**
- 连续两屏不得都只有纯正文
- 每屏都要有视觉抓手，让读者快速扫到重点
- 分割线每 2–3 段必须插入一次，打断节奏

#### 3.11 花哨度控制

**目标是"丰富、有设计感、明显比普通文档更抓眼"，不是"杂乱炫技"。**

花哨主要靠：
- 色彩层次（Callout 背景 + 文字颜色 + 背景高亮）
- 结构变化（分栏 vs 表格 vs 正文）
- 重点句跳出（彩色 + 背景组合）

**不是靠：**
- 无节制混色、满屏高亮
- 整页多色标题
- 整屏都是强调

**一句话原则：看起来丰富，但读起来仍然顺。**

### Step 3.5: 写回前强制自检（⚠️ 必须执行，不可跳过）

在写回文档之前，逐条检查生成的 Markdown：

**自检清单：**

- [ ] **每一个 `<text` 开标签，都有对应的 `</text>` 闭合标签**
  - ❌ 错误：`<text color="red">40%+，是典型的高价值蓝海赛道。`
  - ✅ 正确：`<text color="red">40%+</text>，是典型的高价值蓝海赛道。`
- [ ] **没有嵌套的 `<text>` 标签**（颜色+背景必须写在同一个标签的两个属性里）
  - ❌ 错误：`<text color="red"><text background-color="light-red">关键词</text></text>`
  - ✅ 正确：`<text color="red" background-color="light-red">关键词</text>`
- [ ] **列表（`- ` 或 `1. `）已尽量替换为 Callout 或 Grid 分栏**，残留列表不超过 2 处
- [ ] **二级标题全部用 `<text color="blue">一、标题</text>` 包裹**（禁止 `{color="..."}` 属性，不生效）
- [ ] **每个章节至少有 1 个 Callout**
- [ ] **正文每句话至少 2-4 个关键词着色**（数字/时间词/动作词/结论词优先用红色或红+黄底组合）
  - 自问："这句话里有颜色吗？" → 没有则补上 `<text color="red">关键词</text>`
  - 纯黑字句子每页不超过 1 处
- [ ] **主文档标题（首行）也要有颜色或 Callout 包裹**
  - ❌ 错误：`# AI编程+小红书帮我创造了5000/月的被动收入案例包`
  - ✅ 正确：`# <text color="blue">AI编程+小红书帮我创造了5000/月的被动收入</text>案例包`

> ⚠️ **如果自检发现未闭合的 `<text>` 标签，必须修复后再写回，否则颜色全部不渲染，直接变成原始标签文本显示在页面上。**
>
> **对比标准页面检查**：https://www.feishu.cn/wiki/STMFws3lIiSmWMktSY5cWVvtndf — 打开对照，自检是否达到该页面的颜色密度。

### Step 4: 写回文档

```bash
# 小范围更新（推荐）
lark-cli docs +update \
  --doc "<url_or_token>" \
  --mode insert_after \
  --selection-with-ellipsis "上一段内容开头...下一段内容结尾" \
  --markdown "<新内容>"

# 整页重建（仅确认需要时使用）
lark-cli docs +update \
  --doc "<url_or_token>" \
  --mode overwrite \
  --markdown "<完整内容>"
```

### Step 5: 输出确认

汇报：使用的排版元素（标题颜色/Callout数量/文字颜色+背景高亮/分栏/表格）、文档链接、排版前后主要变化。

## 权限

`docs:doc:readonly`、`docs:doc`、`wiki:node:readonly`
