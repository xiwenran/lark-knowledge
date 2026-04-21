---
name: lark-knowledge-research
version: 0.2.0
description: "知识补漏研究：识别知识库空白并走完四步闭环中的后三步。触发词：/补空白、/Deep Research、/研究补漏。"
metadata:
  requires:
    bins: ["python3", "lark-cli"]
---

# lark-knowledge-research (v0.2.0)

**CRITICAL — 开始前 MUST 先用 Read 工具读取：**
1. `../lark-shared/SKILL.md` — 认证、权限处理
2. `~/.agents/skills/lark-knowledge-config/config.json` — `research_draft_table_id` / `research_draft_node_token`
3. `../lark-knowledge-lint/SKILL.md` — 巡检输出格式与空白/松散聚类契约

## 功能定位

`lark-knowledge-research` 负责把“已经识别到的知识空白”推进到**待确认草稿**，但仍然停在人工审核闸门之前。

它解决三件事：
- 把空白清单转成研究任务
- 用 Tavily 补来源
- 把主会话 Claude 提炼后的草稿写回飞书待确认区

它**不做**两件事：
- 不在脚本里调用 Anthropic / Claude API
- 不直接写正式知识库

## 触发词

- `/补空白`
- `/Deep Research`
- `/研究补漏`

## 四步闭环

```
① 空白识别
   blank_identifier.py / task_list_generator.py
   ↓
② Tavily 搜索
   tavily_search.py
   ↓
③ 主会话 Claude 提炼（不调 API）
   主会话读取搜索 JSON，整理成 markdown 草稿
   ↓
④ 回写飞书“待确认”区
   draft_writer.py
```

### Step 1: 空白识别

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

输出是结构化研究任务，不是最终正文。

### Step 2: Tavily 搜索

```bash
python3 scripts/lark_research/tavily_search.py \
  --tasks-json /tmp/research_tasks.json \
  --json-out /tmp/research_search_results.json
```

脚本行为：
- 读取 `blank_identifier.py` / `task_list_generator.py` 产出的任务 JSON
- 每个 gap 自动生成 2-3 个 Tavily query
- 调用 `https://api.tavily.com/search`
- 输出结构化结果 JSON，字段至少包含：
  - `gap_id`
  - `query`
  - `url`
  - `title`
  - `content`
  - `relevance_score`
- 结束时打印 handoff 提示，提醒把搜索结果交给主会话 Claude

### Step 3: 主会话 Claude 提炼（硬约束）

**正确姿势**：脚本只负责把搜索结果 JSON 打出来，**然后停下**。

主会话 Claude 负责：
- 去重
- 归纳冲突信息
- 产出 markdown 草稿
- 保留来源链接

**禁止**在 research 脚本中私自调用 Anthropic API。

交接提示固定为：

```text
=== 搜索完成，请将以上结果粘贴给主会话 Claude 进行提炼 ===
```

### Step 4: 回写飞书“待确认”区

```bash
python3 scripts/lark_research/draft_writer.py /tmp/research_draft.md
```

或：

```bash
cat /tmp/research_draft.md | python3 scripts/lark_research/draft_writer.py
```

脚本行为：
- 读取 markdown 草稿
- 从 `config.json` 读取 `research_draft_table_id` 或 `research_draft_node_token`
- 若配置了 `research_draft_table_id`，走 `lark-cli base +record-upsert`
- 若配置了 `research_draft_node_token`，走 `lark-cli docs +update --mode append`
- 写入失败时打印清晰错误；若表格路径已产生部分写入则尝试删除

## 配置要求

### 环境变量

- `TAVILY_API_KEY`

未配置时，`tavily_search.py` 会直接退出并提示：

```bash
export TAVILY_API_KEY=your_key
```

### config.json

research 写回至少需要以下二选一：

```json
{
  "research_draft_table_id": "tblxxxxxxxx",
  "research_draft_node_token": "xxxxxxxx"
}
```

说明：
- `research_draft_table_id`：待确认草稿表
- `research_draft_node_token`：待确认草稿文档节点
- 两个都没有时，`draft_writer.py` 会退出并提示补配置

如果走表格写入，还需要已有的：

```json
{
  "base": {
    "base_token": "base_xxx"
  }
}
```

## 待确认区 Gate

**硬约束**：research 产出只能进入“待确认”区，绝不直接写正式知识库。

草稿写入后流程到此为止，后续必须：
1. 人工审核草稿
2. 人工确认可入库
3. 再执行 `lark-knowledge-upgrade` skill 进入正式知识库

任何脚本都不允许绕过这个 gate。

## 输入源

支持两类入口：

### A. 来自 lint 的空白/松散聚类清单

推荐 JSON 契约：

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
      ]
    }
  ]
}
```

### B. 手工指定主题

```text
/补空白 研究 Claude Code 子代理协作
/研究补漏 主题=飞书知识库待确认区设计
```

## lint 协作契约

### research 对 lint 的输入要求

- 至少提供 `topic`
- 推荐提供 `blank_type`、`priority`、`signals`、`evidence`
- 配置与目标位置必须来自 `config.json`

### research 对后续链路的输出要求

研究任务清单每项应包含：
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

搜索结果每项应包含：
- `gap_id`
- `query`
- `url`
- `title`
- `content`
- `relevance_score`

## 默认路径

- 脚本目录：`scripts/lark_research/`
- 本地草稿输出目录：优先读取 `config.json` 中的 `research.output_dir`
- 飞书待确认区目标：`research_draft_table_id` 或 `research_draft_node_token`

## 权限

- `bitable:record`
- `docs:doc`
- `wiki:node`
