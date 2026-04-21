---
name: lark-knowledge-research
version: 0.1.0
description: "知识补漏研究：识别知识库空白并生成结构化研究任务清单，后续可接 Tavily Deep Research 与飞书待确认区。触发词：/补空白、/Deep Research、/研究补漏。"
metadata:
  requires:
    bins: ["python3"]
---

# lark-knowledge-research (v0.1.0)

**CRITICAL — 开始前 MUST 先用 Read 工具读取：**
1. `../lark-shared/SKILL.md` — 认证、权限处理
2. `~/.agents/skills/lark-knowledge-config/config.json` — research 相关配置、待确认区写回路径、默认输出目录
3. `../lark-knowledge-lint/SKILL.md` — 巡检输出格式与空白/松散聚类契约

## 功能定位

`lark-knowledge-research` 是 lark-knowledge 生产线里第一个「补未有」的 skill。它负责把“已经识别到的知识空白”转成可执行的研究任务，再交给后续搜索、提炼、回写链路处理。

**本期范围（P1-C）**：
- 只实现 **Step ① 空白识别**
- 产出 **结构化研究任务清单**
- 明确 `lint → research` 契约
- 预留 Tavily 与飞书待确认区写回接口

**不在本期实现（P1-D）**：
- 不调用 Tavily API
- 不执行 LLM 搜索结果提炼
- 不写入飞书正式库
- 不写入飞书待确认区，仅输出待写回草稿与目标位置说明

## 触发词

- `/补空白`
- `/Deep Research`
- `/研究补漏`

## 四步闭环

```
① 空白识别（P1-C 已实现）
   ↓
② Tavily 搜索（P1-D 预留，不在本期实现）
   ↓
③ LLM 提炼（P1-D 预留，不在本期实现）
   ↓
④ 回写飞书“待确认”区（P1-D 预留，不在本期实现）
```

**硬约束**：所有 research 产出都只能进入飞书“待确认”区，绝不直接写正式知识库。

## 输入源

支持两类入口，二选一或混合：

### A. 来自 lint 的空白/松散聚类清单

优先接收 `lark-knowledge-lint` 在 P1-B 阶段产出的结构化结果。推荐 JSON 契约如下：

```json
{
  "generated_at": "2026-04-21",
  "source": "lark-knowledge-lint",
  "blanks": [
    {
      "topic": "Claude Code 技能编排",
      "blank_type": "keyword_gap",
      "priority": "high",
      "signals": ["keyword_gap", "loose_cluster"],
      "evidence": [
        "关键词出现 5 次但无独立词条",
        "相关页面互链稀疏"
      ],
      "related_records": [
        {"title": "Claude Code 工作流", "record_id": "recxxx"}
      ],
      "suggested_topic_owner": "AI编程"
    }
  ]
}
```

若 lint 只输出 markdown，本 skill 允许读取 bullet list / checklist 形式的“空白主题清单”，再转成同等结构的 research 任务。

### B. 手工指定主题

用户可直接提供一个或多个主题，例如：

```text
/补空白 研究 Claude Code 子代理协作
/研究补漏 主题=飞书知识库待确认区设计
```

手工主题默认 `source=manual_topic`，并标记为待补证据。

## lint 协作契约

### research 对 lint 的输入要求

- 至少提供 `topic`
- 推荐提供 `blank_type`、`priority`、`signals`、`evidence`
- 若有 `related_records` / `related_pages`，可作为后续 Tavily 搜索的上下文
- 配置与目标目录必须来自 `config.json`，不允许在 skill 或脚本中硬编码

### research 回传给 lint/后续链路的输出要求

研究任务清单中的每一项都应包含：
- `task_id`
- `topic`
- `source`
- `blank_type`
- `priority`
- `research_question`
- `search_brief`
- `supporting_evidence`
- `draft_destination`
- `status`

其中：
- `status` 本期固定为 `identified`
- `draft_destination` 本期只写“目标位置说明”，真正写回飞书在 P1-D 落地

## 输出规范

本 skill 同时输出两份内容：

1. **JSON**：机器可消费，供 P1-D 的 Tavily 搜索与后续调度脚本接入
2. **Markdown**：人工可审阅，便于用户确认优先级与研究范围

输出内容是 **研究任务清单**，不是最终知识库正文，也不是正式入库数据。

## 默认路径

- **脚本目录**：`scripts/lark_research/`
- **本地草稿输出目录**：优先读取 `config.json` 中的 `research.output_dir`
- **飞书待确认区目标**：优先读取 `config.json` 中的 `research.pending_review` / 等效键

若配置缺失：
- 本期允许只在终端输出 JSON / Markdown
- 同时提示用户补齐 `config.json`
- 不允许私自降级为写正式库

## Step 1: 空白识别（P1-C 已实现）

执行入口：

```bash
python3 scripts/lark_research/blank_identifier.py \
  --lint-json <lint_output.json> \
  --json-out /tmp/research_tasks.json \
  --markdown-out /tmp/research_tasks.md
```

或：

```bash
python3 scripts/lark_research/blank_identifier.py \
  --topic "Claude Code 子代理协作" \
  --topic "飞书知识库待确认区设计"
```

脚本行为：
- 读取 lint 输出或手工主题
- 标准化为空白候选项
- 生成研究任务 JSON
- 同步生成 Markdown 审阅稿
- 标注待确认区目标位置（仅说明，不写入）

## Step 2: Tavily 搜索（P1-D 预留）

后续将读取 `TAVILY_API_KEY` 环境变量并调用 Tavily，对每个任务按多个角度检索资料。

**本期不实现。**

## Step 3: LLM 提炼（P1-D 预留）

后续将对搜索结果做去重、摘要、结构化整理，并保留来源信息。

**本期不实现。**

## Step 4: 回写飞书“待确认”区（P1-D 预留）

后续将把研究草稿写入飞书“待确认”区，不进入正式知识库。

**本期不实现。**

## 输出示例

### JSON

```json
{
  "generated_at": "2026-04-21T18:00:00+08:00",
  "task_count": 1,
  "tasks": [
    {
      "task_id": "research-001",
      "topic": "Claude Code 子代理协作",
      "source": "manual_topic",
      "blank_type": "manual_gap",
      "priority": "medium",
      "research_question": "围绕“Claude Code 子代理协作”应补哪些可复用知识？",
      "search_brief": "P1-D 将据此生成 Tavily 查询。",
      "supporting_evidence": ["manual topic provided by user"],
      "draft_destination": {
        "mode": "pending_review",
        "configured": false,
        "target": "config.json: research.pending_review"
      },
      "status": "identified"
    }
  ]
}
```

### Markdown

```markdown
# 研究任务清单

## 1. Claude Code 子代理协作
- 来源：manual_topic
- 空白类型：manual_gap
- 优先级：medium
- 研究问题：围绕“Claude Code 子代理协作”应补哪些可复用知识？
- 待确认区目标：config.json: research.pending_review
```

## 权限

本期只做本地结构化与草稿生成，无额外 API 权限要求。
