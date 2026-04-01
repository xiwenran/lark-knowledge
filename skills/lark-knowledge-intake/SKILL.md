---
name: lark-knowledge-intake
version: 2.0.1
description: "知识收件入表：将外部资料AI结构化处理后写入飞书多维表格。触发词：收件、入表、收录、处理资料。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# 知识收件入表

**CRITICAL — 开始前 MUST 先用 Read 工具读取：**
1. `~/.agents/skills/lark-knowledge-config/config.json` — 所有 token、字段名、选项值
2. `../lark-shared/SKILL.md` — 认证、权限处理

## 适用场景

用户提供 URL、文本、飞书文档链接等任何外部资料时收录入表。

## 工作流

```
用户输入资料 → 获取内容 → AI 结构化处理(22字段) → 用户确认 → 写入多维表格 → 评分≥4则自动升级+排版
```

### Step 1: 获取内容

```bash
# 飞书文档
lark-cli docs +fetch --doc "<url_or_token>" --format markdown
# 网页 URL → 使用 WebFetch 工具
# 纯文本 → 直接处理
```

### Step 2: AI 结构化处理

**系统身份**：你是"专题知识库与资料加工系统"核心执行助手，服务于三个正式专题：小红书、虚拟资料产品、AI 编程。

**判断流程**（按顺序执行）：
1. 识别来源类型（选项见 config.json → fields.来源渠道_options）
2. 判断处理策略：直接提炼型 / 清洗转化型 / 待人工判断
3. 判断是否值得长期保存（与三专题相关？有可复用价值？非纯噪音？）
4. 底层分类：认知 / 决策 / 操作
5. 专题归属（主专题，选项见 config.json → fields.专题归属_options）
6. 资产形态（选项见 config.json → fields.资产形态_options）
7. 质量判断：可执行性/信息密度/独特性（高/中/低）、综合评分（1-5）

**输出 22 个字段**：
标题、收录时间（YYYY-MM-DD）、来源渠道、原始链接、备注、AI摘要（100-200字）、关键词标签（多选，从 config.json 固定选项中选）、底层逻辑分类、专题归属、资产形态、适用场景（格式：一句话结论+三关键点）、可执行性、信息密度、独特性、综合评分、是否可复用、是否可产品化、产品化方向、潜在价值说明、处理状态、升级备注、**关联目录索引（不写入表格，仅内存传递）**

**处理原则**：不复制原文全文；信息不足不强行拔高价值；权限受限资料仅摘要归纳。

### Step 3: 写入多维表格

用户确认结构化结果后写入（token 从 config.json 读取）：

```bash
lark-cli base +record-upsert \
  --base-token "<config.base.base_token>" \
  --table-id "<config.base.table_id>" \
  --json '{
    "标题": "...",
    "收录时间": "YYYY-MM-DD",
    "来源渠道": "...",
    "原始链接": "...",
    "备注": "...",
    "AI摘要": "...",
    "关键词标签": ["案例拆解", "工作流"],
    "底层逻辑分类": "...",
    "专题归属": "...",
    "资产形态": "...",
    "适用场景": "一句话结论：xxx。关键点：①xxx②xxx③xxx",
    "可执行性": ["高"],
    "信息密度": ["高"],
    "独特性": ["高"],
    "综合评分": 5,
    "是否可复用": true,
    "是否可产品化": true,
    "产品化方向": "...",
    "潜在价值说明": "...",
    "处理状态": "待升级",
    "升级备注": "..."
  }'
```

> 综合评分为数字（不加引号）；可执行性/信息密度/独特性为数组格式 ["高"]。

### Step 4: 自动升级链（评分 ≥ 4 时自动触发）

写入成功后，如综合评分 ≥ 4，**立即自动执行升级链**，无需用户手动触发：

```
自动升级链触发：评分 ≥ 4 → 开始自动升级流程
```

#### Step 4a: 筛选目标记录

```bash
lark-cli base +record-list \
  --base-token "<config.base.base_token>" \
  --table-id "<config.base.table_id>"
```

筛选本条记录（专题归属 + 资产形态匹配）。

#### Step 4b: 创建知识库页面

**案例包**：创建主成品页 + 视角提炼页

```bash
# 创建主成品页（主专题/05_案例包/）
lark-cli docs +create \
  --title "<标题>" \
  --wiki-node "<config wiki_directories[主专题][05_案例包]>" \
  --markdown "<完整案例内容>"

# 在辅助专题/05_案例包/创建视角提炼页
lark-cli docs +create \
  --title "<标题>（<辅助专题>视角）" \
  --wiki-node "<config wiki_directories[辅助专题][05_案例包]>" \
  --markdown "<该专题视角提炼内容>"
```

**非案例包**：直接写入对应目录页（方法论/SOP/模板/技巧集）

#### Step 4c: 追加关联区块 + 目录索引

- 主成品页底部追加「来源与关联」链接区块（**必须含可跳转链接**，不可只有纯文本路径）：
  - 原始文档链接
  - 主专题成品页链接（如有辅助专题，该行也要有链接）
  - 辅助专题视角提炼页链接（每个辅助专题一行，都必须是真实可跳转URL）
  - 收录时间 + 处理状态
- 主、辅专题目录页各追加一条索引入口

#### Step 4d: 回填多维表格

```bash
lark-cli base +record-upsert \
  --base-token "<config.base.base_token>" \
  --table-id "<config.base.table_id>" \
  --record-id "<入库返回的record_id>" \
  --json '{
    "处理状态": "已升级",
    "知识库页面链接": "<主成品页URL>",
    "升级状态": "已完成"
  }'
```

#### Step 4e: 自动排版美化（关键步骤，必须执行）

入库 + 升级完成后，对每个新建页面**必须**执行完整排版流程：

**第一步：读取页面原始内容**
```bash
lark-cli docs +fetch --doc "<wiki_token>" --format markdown
```

**第二步：生成彩色增强版内容（严格按 lark-knowledge-format v6.4 规则）**
- 标题格式：**必须用 `<text color="...">一、标题</text>` 包裹**，禁止 `{color="..."}` 属性
- 文字颜色：`<text color="...">内容</text>` 闭合标签不许漏
- 背景高亮：`<text background-color="...">内容</text>` 组合使用
- 颜色密度：**每段 2-4 个着色词，每屏 3-5 处红色**，宁可过<minimax:tool_call>欠
- 红色用途：数字/时间节点/动作词/强调效果 全部用红
- 禁止：`<span style>` / 嵌套 `<text>` / 列表（→ Callout）
- Callout 5类固定：💡核心结论→light-yellow、✅重要动作→light-green、📌结构→light-blue、⚠️注意→light-orange、❌误区→light-red
- 参考效果：https://www.feishu.cn/wiki/STMFws3lIiSmWMktSY5cWVvtndf

**第三步：overwrite 写回**
```bash
lark-cli docs +update \
  --doc "<wiki_token>" \
  --mode overwrite \
  --markdown "<彩色增强版完整内容>"
```

**第四步：回填多维表格**（见 Step 4d）

> ⚠️ 注意：Step 4e 是独立步骤，不是注释。必须完整执行 fetch → 生成彩色内容 → overwrite 写回三步。排版后页面效果应达到：正文段落大量彩色词汇、关键数据全部红底红字、列表全部转为 Callout。

#### Step 4f: 输出完成汇总

```
入库完成 ✅
自动升级完成 ✅
自动排版完成 ✅

记录编号：<编号> | 标题：<标题> | 专题：<专题> | 评分：<分>
主成品页：<URL>
视角提炼页：<URL>

目录索引已写入：
- <主专题>/05_案例包/
- <辅助专题>/05_案例包/
```

## 权限

`bitable:record`、`docs:doc:readonly`、`wiki:node:readonly`
