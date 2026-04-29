---
name: lark-knowledge-format
version: 6.5.0
description: "飞书文档排版美化：读取现有飞书文档，仅添加视觉格式（颜色/callout/标题样式），不修改任何文字内容，写回文档。触发词：排版、美化、格式化、重排。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# 飞书文档排版美化（彩色增强版 v6.5）

## 使用模式（两种并存，互不干扰）

本 skill 按「规则层 + 执行层」分层设计，支持两种使用方式：

### 模式 1：处理已有飞书文档（完整执行流程）

**适用场景**：用户提供飞书文档 URL/token，希望原地润色。比如 lark-knowledge 项目、飞书知识库项目。

**流程**：Read 本 skill → fetch 飞书文档 → 加 `<text color>` 标签 → write 回飞书。完整走 Step 1-4。

### 模式 2：被其他流程引用规则（规则层复用）

**适用场景**：其他 skill 在**生成 markdown 的阶段**就想按飞书排版规范写带色内容，避免"先写纯稿再回头上色"的二次往返。比如 teacher-script 在生成逐字稿时就直接带色上传。

**流程**：其他 skill 的子代理 Read 本文件的下列段落，按规则生成带色 markdown，**不调用** fetch/write：
- 「着色词类别清单」
- 「背景色使用清单」及「背景色应用场景表」
- 「Step 3.7 教育类专项规则」（如果是教育类内容）

**规则层单向引用，不影响模式 1**。其他 skill 只读规则不执行 I/O；模式 1 仍然按完整流程跑。两种模式之间无共享状态。

**规则升级自动同步**：其他 skill 复用时是 Read 本文件，不是复制规则到自己的 prompt。本 skill 规则升级后，所有复用方**自动同步**新规则，无需逐个更新。

---

**CRITICAL — 开始前 MUST 先用 Read 工具读取**（模式 1 必读，模式 2 按需）：
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
- **字色密度目标**：**每一句 ≥4 个着色词，上不封顶，宁多勿少**；每屏 ≥5 处红色
- **背景色密度目标**：**每章节 ≥3 处背景色高亮**（定义/术语/结论/金句/板书）；整篇文档背景色覆盖 ≥ 字色密度的 1/5
- **核心原则**：**可以多，不能少**——着色只嫌少不嫌多，字色 + 背景色双管齐下
- **视觉层次**：二级标题蓝色、关键词高亮、Grid 分栏展示
- **内容结构**：零列表（重要结论用 Callout，普通要点改为背景色着色段落）、多样 emoji、逻辑分块

**参考标准**：https://www.feishu.cn/wiki/STMFws3lIiSmWMktSY5cWVvtndf （KR-0002，自检时对照）

## 着色词类别清单（通用，适用所有文档类型）

**原则**：以下所有类别的词都**应当着色**。遇到任何一类词，默认都加颜色；只有纯粹的连接虚词（"的、了、吗、呢"等）可以不着色。

| 类别 | 示例 | 推荐颜色 |
|------|------|---------|
| **名词-专名** | 人名、地名、书名、机构名、作品名 | `blue` / `purple` |
| **名词-概念** | 方法论、术语、流派、理论 | `blue` |
| **数字/时间/日期** | 1927年、十六年、第四声、40% | `red` |
| **强动作动词** | 烧掉、昏倒、冲进、抓住、砸碎、拔掉 | `red` |
| **普通动词** | 发现、记住、想想、看看 | `orange` |
| **形容词-褒义** | 慈祥、坚贞、从容、沉着、伟大 | `green` |
| **形容词-贬义/严峻** | 残忍、粗暴、凶残、紧张、严峻、可怕 | `red` |
| **形容词-中性** | 含糊、平静、乱蓬蓬 | `orange` |
| **语气词/强调副词** | 竟然、突然、一下子、根本、完全、永远、绝对、一定、最 | `red` |
| **疑问词** | 为什么、怎么、哪能、难道、是不是 | `orange` |
| **时间副词** | 马上、立刻、顿时、终于、依然、仍旧、一直 | `orange` |
| **情感强调词** | 念念不忘、一字不吐、毫不畏惧、无私无畏 | `red` + `background-color="light-yellow"` |
| **关联词/逻辑词** | 但是、然而、因为、所以、虽然、即使 | `orange`（选择性） |
| **写作手法/修辞** | 倒叙、对比、首尾呼应、语言描写 | `blue` |
| **核心结论句** | 教师点睛句、总结句 | `red` + `background-color="light-red"` |
| **板书/批注** | `[板书：xxx]` | `background-color="light-yellow"` |

**⚠️ 关键提醒**：
- 见到上表任何一类词，**默认先加颜色**，而不是默认不加
- **宁可一句话里 6-8 个着色词，也不要只有 1-2 个**
- 适当加入"可有可无"的着色也没问题——**多了无害，少了失效**
- 如果一句话读下来没有任何颜色，说明漏着色了，必须补

## 背景色使用清单（通用，与字色同等重要）

**原则**：背景色比纯字色**视觉权重更高**，适合"点睛之笔"。不要只用字色，背景色要**大胆使用、成片铺开**。

**飞书支持的背景色**（全部可用）：
`light-red` / `light-orange` / `light-yellow` / `light-green` / `light-blue` / `light-purple` / `grey`

### 背景色应用场景表

| 背景色 | 使用场景 | 示例语法 |
|-------|---------|------|
| **light-yellow**（最常用） | 术语/定义/核心概念/关键金句 | `<text background-color="light-yellow">倒叙</text>`、`<text background-color="light-yellow">时间顺序</text>` |
| **light-red** | 强结论/震撼事实/强烈转折 | `<text background-color="light-red">被害</text>`、`<text background-color="light-red">一字不吐</text>` |
| **light-blue** | 板书/框架/方法论名称 | `<text background-color="light-blue">[板书：xxx]</text>` |
| **light-green** | 褒扬/精神品质/成功结论 | `<text background-color="light-green">从容就义</text>`、`<text background-color="light-green">坚贞不屈</text>` |
| **light-orange** | 注意事项/警示/重点提示 | `<text background-color="light-orange">注意</text>`、`<text background-color="light-orange">危险逼近</text>` |
| **light-purple** | 特殊标识/引用金句/诗句 | `<text background-color="light-purple">铁肩担道义，妙手著文章</text>` |
| **grey** | 次要说明/括号备注 | `<text background-color="grey">[停顿]</text>`、`<text background-color="grey">[环视全班]</text>` |

### 背景色使用密度要求

- **每章节 ≥3 处背景色**，短章节至少 2 处，长章节 5-8 处
- **术语首次出现必须背景色**：如"倒叙""首尾呼应""对比""时间顺序"第一次被讲到时,必须加 `light-yellow` 背景
- **金句名言必须背景色**：诗句、名言、口号、核心总结句,一律加背景(配合红字)
- **板书全部背景色**：`[板书：xxx]` 一律加 `light-blue` 或 `light-yellow`
- **强转折/强结论必须背景色**：如"但是没有走""一字都没透露"这种戏剧性转折

### 字色 vs 背景色选择原则

- **字色** = 常规着色,覆盖面广,用于日常关键词
- **背景色** = 高权重高亮,**每章节必须至少 3 处**,用于定义/结论/金句
- **字色 + 背景色组合** = 超强调,`<text color="red" background-color="light-yellow">` 用于核心金句
- **原则**：字色铺底,背景色点睛。光有字色 → 稀;光有背景色 → 乱;**两者搭配才是彩色增强版的精髓**

### 为什么颜色会偏稀？（根因诊断，历史教训）

过往产出常出现颜色密度不足，根因如下，写本规则时已针对性修复：

1. **目标值定得太低**：原来写"每段 2-4 个着色词"，模型会照最低值执行 → **现改为"每句 ≥4,上不封顶"**
2. **着色类别过窄**：原来只列了名词/专名/数字，漏掉动词、形容词、语气词、疑问词、副词等口语高频词 → **现补充完整类别清单,覆盖所有实词**
3. **缺少"宁多勿少"原则**：没明确告诉模型可以多着色，模型会默认保守 → **现明确"可以多,不能少;多了无害,少了失效"**
4. **自检清单是"上限暗示"**：原来写"目标每段 2-4 个"被当成上限 → **现改为"强制计数 ≥4,少了必须补"**
5. **示例密度本身就低**：抄示例会复制稀疏风格 → **现示例每句 4-8 个着色词,动词/形容词/语气词全染色**

---

## Step 1: 获取文档内容

**1a. 解析输入**
- URL 中提取 node_token（`/wiki/` 或 `/docx/` 后的字符串）
- 直接提供 token 则使用

**1b. 读取文档**
```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
lark-cli docs +fetch --doc $node_token
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

### 3.1 颜色语法速查（何时用哪种颜色请查上方清单）

> **⚠️ 使用场景指引的权威位置**：
> - **字色该用哪种** → 看上方 **"着色词类别清单"**（15 类词 → 颜色映射）
> - **背景色该用哪种** → 看上方 **"背景色使用清单"**（7 种背景色 → 场景映射）
> - **本节（3.1）仅作语法速查**：列出所有合法的 `<text>` 标签形式,不重复场景指引

⚠️ **强制禁令（任何情况都不许出现）**：
- ❌ `<span style="...">...</span>` ← 飞书不识别，强制禁止
- ❌ `<text style="color:red">` / `<text style="background-color:...">` ← `style=` 属性飞书不识别
- ❌ `font` / `font-weight` / `background` 单独使用
- ✅ 一律使用飞书原生标签属性：`<text color="...">` 和 `<text background-color="...">`

**合法的字色标签（5 种）**：

| 语法 |
|------|
| `<text color="red">文字</text>` |
| `<text color="blue">文字</text>` |
| `<text color="green">文字</text>` |
| `<text color="orange">文字</text>` |
| `<text color="purple">文字</text>` |

**合法的背景色标签（7 种，与 3.0 背景色清单完全对齐）**：

| 语法 |
|------|
| `<text background-color="light-red">文字</text>` |
| `<text background-color="light-orange">文字</text>` |
| `<text background-color="light-yellow">文字</text>` |
| `<text background-color="light-green">文字</text>` |
| `<text background-color="light-blue">文字</text>` |
| `<text background-color="light-purple">文字</text>` |
| `<text background-color="grey">文字</text>` |

**字色 + 背景色组合语法（超强调，单标签两属性）**：

```
<text color="red" background-color="light-yellow">核心金句</text>
<text color="red" background-color="light-red">强结论</text>
<text color="green" background-color="light-green">褒扬</text>
```

⚠️ **禁止嵌套**：`<text color="red"><text background-color="light-red">...</text></text>` 是错的,必须写成单标签两属性。

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

**⚠️ Callout 克制原则（2026-04-27 新增）**：
Callout 的视觉价值来自稀缺性——一节里只有 1 个 Callout，它就是视觉锚点；连续堆叠 3 个以上，就和普通段落没有区别，反而比背景色着色段落更难读。

**使用上限**：每章节最多 2 个 Callout（留给最重要的结论/关键警示）。  
**其他要点**：改用背景色着色段落（`<text background-color="light-yellow">` 等），不用 Callout。  
**连续限制**：连续超过 2 个 Callout 时，必须插入至少一个普通着色段落打断。

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

3. ✅ **列表→背景色段落为主，重要结论才用 Callout**：零列表，每章节最多 2 个 Callout（**教育类例外**：一律改为分行段落，不用 Callout）
   - ❌ 错误：`- 要点1` `- 要点2`（保留列表符号）
   - ❌ 错误：4-5 个要点全都变成 4-5 个连续 Callout（Callout 堆叠失去区分度）
   - ✅ 正确（通用）：普通要点 → 着色段落；最重要的 1-2 个结论 → Callout
   - ✅ 正确（教育类）：全部改为分行着色段落，段落间空行，禁用 Callout

4. ✅ **标题用 `<text color>` 包裹**：
   - ❌ 错误：`## 标题 {color="blue"}`
   - ✅ 正确：`## <text color="blue">标题</text>`

5. ✅ **Callout 克制使用**：每章节 ≤2 个，全文连续 Callout 超过 2 个时必须插入着色段落打断（**教育类例外**：一律禁用 Callout）

6. ✅ **每句话强制计数：着色词 ≥4 个**（宁多勿少）
   - 写完每段后，逐句数一下着色词数量
   - 少于 4 个 → 回头补充，按"着色词类别清单"从动词/形容词/语气词/副词里挑
   - **原则**：可以多，不能少；多了无害，少了失效

6b. ✅ **每章节强制计数：背景色 ≥3 处**（字色 + 背景色双管齐下）
   - 写完每章节后，数一下带 `background-color` 的标签数量
   - 少于 3 处 → 回头加背景色，按"背景色应用场景表"挑:术语/结论/金句/板书
   - **原则**：不能只靠字色，背景色才是视觉爆点;字色铺底、背景色点睛

7. ✅ **正文首屏有强视觉锚点**（替代 H1）：
   - 3.0 已禁止正文写 `# H1`（飞书标题已在元数据层）
   - 所以正文必须以**引言 Callout 或强着色段落**作为视觉开场（教育类则以高密度着色的 `##` 二级标题 + 首段开场）
   - ❌ 错误：原文开头的 `# 纯标题` 未删除
   - ✅ 正确：删掉 H1，直接用 Callout / 高亮段落 / 彩色 H2 开场

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

**其余规则完全不变**：颜色密度（**每句 ≥4 个着色词，宁多勿少**）、`##` 标题用 `<text color="blue">` 包裹、`<text background-color>` 背景高亮、文字语法——全部照通用规范执行，参照"着色词类别清单"全类别覆盖。

**⚠️ 核心提醒：颜色密度不能因为是对话体裁就降低，反而因为对话口语化、动词/语气词/疑问词密集，更应该大量着色。每句师生发言都要 ≥4 个着色词，能多不能少。**

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

**示例**（高颜色密度对话——**每句 ≥4 个着色词**）：
```
<text color="blue">师</text>：<text color="orange">同学们</text>，<text color="red">今天</text>咱们要学的是<text color="red">《十六年前的回忆》</text>，作者是<text color="blue">李星华</text>，她的父亲就是<text color="blue">李大钊</text>。

<text color="blue">师</text>：文章<text color="orange">一开头</text>就写了<text color="red">1927年4月28日</text>，这是一种叫做<text color="blue">倒叙</text>的写法——<text color="orange">先</text>写<text color="red">结局</text>，<text color="orange">再</text>回忆<text color="red">经过</text>，<text color="red">一下子</text>就把读者<text color="green">抓住</text>了。

**生**：<text color="orange">为什么</text>要用<text color="blue">倒叙</text>？<text color="orange">直接</text>按顺序写<text color="red">不行</text>吗？

<text color="blue">师</text>：问得<text color="green">好</text>！因为这样写<text color="red">能</text><text color="green">制造悬念</text>，让读者从<text color="red">第一句</text>话就<text color="red">迫切</text>想知道<text color="red">谁被害了</text>、<text color="red">为什么</text>、<text color="red">怎么</text>被害的。这就是<text color="blue">倒叙</text>的<text color="red">力量</text>。
```

**密度对比**：
- ❌ **稀疏（错误）**：一句话只有 1-2 个着色词,读起来跟黑白稿差不多
- ✅ **饱满（正确）**：一句话 4-8 个着色词,**动词、形容词、语气词、时间副词、疑问词全部染色**,视觉上"花枝招展"才对

### 3.8 知识库/商业运营类专项着色规则

**适用场景**：小红书运营、虚拟资料产品、AI 工具评测、商业竞品分析等结构化知识库内容。

**与通用规则的关系**：补充更细的语义映射，不替换通用规则，其余完全沿用通用着色词清单和背景色清单。

| 着色对象 | 颜色 | 示例 |
|---------|------|------|
| 平台名/账号名/产品名 | `blue` | 小红书、抖音、知识星球、「护理PPT副业日记」 |
| 数字/金额/比例/销量 | `red` | 4633份、¥198、91.7万元、7895粉、40%+（着色富矿，不要遗漏） |
| 运营策略词/方法论（作名词用时） | `blue` | 内容引流、精准定位、差异化、垂直赛道、心智占领（若作动词用如「去转化用户」则→`orange`） |
| 商业指标名称 | `blue` | GMV、ROI、粉丝量、转化率、口碑分（属于名词-概念，与通用规则一致） |
| 商业指标数值 | `red` | 91.7万元、7895粉、4.56分（属于数字，与通用规则一致） |
| 用户群体/人群标签 | `orange` | 精准粉丝、目标用户、护理从业者、刚需人群 |
| 褒义/成功结论词 | `green` | 高转化、精准、爆款、刚需、天然过滤、零跳转 |
| 风险/竞争/问题词 | `red` | 竞争激烈、红海、非满分、待改善、泛流量 |
| 核心洞察/关键数据金句 | `red` + `background-color="light-red"` | 「流水91.7万元」「转化路径最短」等强结论 |
| 方法论名称/框架名 | `blue` + `background-color="light-blue"` | 5维分析框架、三层分类体系 |
| 价格锚点/标志性数字 | `red` + `background-color="light-yellow"` | ¥198、500万注册护士 |

**⚠️ 核心提醒**：商业内容里数字天然密集（价格/销量/粉丝数/评分），这是着色密度的最大来源——逐一着红色，不要遗漏。运营术语（转化、引流、定位）作为策略名词时等同于教育类的「写作手法」，一律 blue。

**典型着色示例**（展示正确密度）：
```
<text color="blue">内容引流路径</text>：<text color="blue">护理PPT笔记</text>（<text color="orange">持续输出</text>）→ <text color="green">精准粉丝积累</text>（<text color="red">7895粉</text>）→ 主页商品<text color="blue">转化</text>（<text color="red">4633份</text>）

<text color="blue">小红书</text>商品主页<text color="green">直接承接</text>，<text color="green">无需</text>额外跳转，<text color="blue">转化路径最短</text>。已售 <text color="red">4633份</text> × <text color="red">¥198</text> ≈ <text color="red" background-color="light-red">流水91.7万元</text>
```

### 3.9 All In Podcast 专项排版规则

**适用场景**：All In Podcast 中英对照逐字稿知识库页面。

**核心原则**：与通用知识库排版规则**完全独立**，不继承通用颜色密度要求（每句 ≥4 着色词的规则在此**取消**）。排版目标是「内容干净，结构清晰」，不是「视觉丰富」。

#### 颜色体系（仅此五种，不扩展）

| 用途 | 标签 | 说明 |
|------|------|------|
| 章节标题（##/###） | `<text color="blue">` | 所有 ## 和 ### 标题包裹 |
| 英文原句 | `<text color="grey">` | `> **Speaker**: 英文原文` 行，视觉降权为参考层 |
| 关键数字/金额/比例 | `<text color="red">` | **仅限五维分析章节**，逐字稿禁止 |
| 注释块 | `<callout background-color="light-blue">` | 无 emoji，无标题 |
| 核心概览块 | `<callout background-color="light-yellow">` | 顶部概览专用，已在页面头部，不改 |

#### 分区处理规则

| 区域 | 处理方式 |
|------|---------|
| 页面头部（期号行 + 📌 摘要） | 公司名/产品名加 `blue`，数字加 `red` |
| light-yellow 概览 callout | **原封不动**，已格式化 |
| 五维分析各节 | 关键数字 `red`，公司名/人名 `blue`，核心结论句可加 `background-color="light-yellow"` |
| 精华金句 | 说话人名 `blue`，引号内关键判断词 `red` |
| **逐字稿区域** | **❌ 禁止任何 `<text color>` 着色**，原封不动复制 |
| light-blue 注释 callout | **原封不动**，已格式化 |

#### 与通用规则的差异对照

| 通用规则 | All In 产品覆盖 |
|---------|--------------|
| 每句 ≥4 着色词 | **取消**，逐字稿内不做关键词着色 |
| 多色背景高亮 | **只保留两种**：light-blue（注释）+ light-yellow（概览） |
| Callout 替代列表 | **仅限五维分析章节** |
| red 标注关键数据 | **限制频次**，仅五维分析，逐字稿绝对禁止 |

#### 自检要点

- 逐字稿段落（`## 中英对照逐字稿` 之后）有没有混入 `<text color>`？有则删掉
- 五维分析里有没有漏掉关键数字的 `red` 标注？

---

## Step 4: 写回文档

**4a. overwrite 写回**
```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
lark-cli docs +update --doc $node_token --mode overwrite --markdown "重写后的完整内容"
```

**4b. 确认更新**
```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
lark-cli docs +fetch --doc $node_token
```

**最终检查**：写回成功后，确认文档在飞书中正确显示彩色效果。