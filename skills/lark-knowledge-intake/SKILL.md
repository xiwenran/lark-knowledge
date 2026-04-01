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

**按来源类型处理**：

**飞书文档**：
```bash
lark-cli docs +fetch --doc "<url_or_token>" --format markdown
```

**纯文本**：直接处理。

**微信公众号文章**（`mp.weixin.qq.com`）— 自动降级链：

```
① Jina AI Reader：WebFetch https://r.jina.ai/<原始URL>
      ↓ 失败（返回验证页/空内容）
② Chrome MCP：用 mcp__Claude_in_Chrome__navigate 打开原始URL，
   再用 mcp__Claude_in_Chrome__get_page_text 读取正文
      ↓ 失败（仍为验证页）
③ 提示用户：
   "微信文章无法自动读取，请选择：
    A. 在手机微信中打开 → 右上角… → 打印 → 存为 PDF → 发给我
    B. 复制全文粘贴过来"
   → 用户提供 PDF 后用 PDF Skill 识别；提供文本后直接处理
```

**其他网页 URL**：使用 WebFetch 工具。

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

执行 [`../lark-knowledge-upgrade/SKILL.md`](../lark-knowledge-upgrade/SKILL.md) 的完整升级流程，传入当前 record_id。

#### Step 4f: 输出完成汇总

```
入库完成 ✅  升级完成 ✅  排版完成 ✅
<编号> | <标题> | 专题：<专题> | 评分：<分>
主成品页：<URL>  视角提炼页：<URL>（若有）
```

## 权限

`bitable:record`、`docs:doc:readonly`、`wiki:node:readonly`
