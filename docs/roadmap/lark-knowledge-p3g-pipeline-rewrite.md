> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

### P3-G: 逐字稿流水线重构（多模型分工 + 质量合同）
- 目标：用火山引擎 Doubao-Seed-2.0-pro 替换全文 Claude 翻译，引入异常检测器，重构 P3-C 逐字稿生成流水线，将 Claude token 消耗降低约 90%
- 触发：2026-04-29 复盘，发现原流水线全程用 Claude Sonnet × 5 agent，约 50 万 token/期，成本高、session 易被 context compaction 中断导致结果丢失
- 涉及文件：
  - `scripts/allin/vtt_clean.py`（新建：VTT 去重 + 分段）
  - `scripts/allin/translate_bilingual.py`（新建：调 Doubao API 出逐句双语稿）
  - `scripts/allin/build_feishu_page.py`（新建：组装页面 + 调 Claude 注释/分析）
  - `skills/lark-knowledge-allin-transcript/SKILL.md`（更新：模型分工 + 质量合同）
  - `skills/lark-knowledge-allin-intake/SKILL.md`（更新：Worker 改用 Doubao）

---

#### 新流水线架构

```
VTT字幕原文
  ↓ [vtt_clean.py — 零成本]
去重 + 分段（保留时间戳）
  ↓ [Doubao-Seed-2.0-pro — 极低成本]
逐句双语翻译（EN↔CN，说话人标注）
  ↓ [Claude Haiku — 低成本]
事实核查：数字/人名/说话人归属 → 中文异常报告
  ↓ [用户确认 — 5分钟，中文决策]
  ↓ [Claude Sonnet — 中等成本]
注释生成 + 五维分析终稿 + 精华金句
  ↓ [Claude Opus — 单次短调用]
异常检测（世界知识 + 内部一致性）→ 中文报告
  ↓ [用户确认 — 1分钟]
  ↓ [lark-cli — 零成本]
写入飞书 Wiki + 回填收件表
```

#### 各模型职责与选型理由

| 角色 | 模型 | 职责 | 选型理由 |
|------|------|------|---------|
| 翻译 Worker | Doubao-Seed-2.0-pro | 字幕全文逐句翻译 | 英文 STEM 理解最强，成本约为 Claude 的 1/10 |
| 事实校对 | Claude Haiku | 核查数字/人名/归属，输出中文报告 | 机械比对任务，轻量快速；Doubao 英文细节不如 Claude 系列稳 |
| 内容生产 | Claude Sonnet | 注释 + 五维分析 + 金句 | 推理和洞察，Claude 的核心价值所在 |
| 异常检测 | Claude Opus | 世界知识核验 + 内部一致性检查 | 对4位主播公开立场知识最深，单次短调用值得用最强模型 |
| 写入 | lark-cli | 飞书 Wiki + 收件表回填 | 不变 |

#### 质量合同（所有 Agent 共享）

所有 Agent 在任务前读取同一份规范，避免主观标准漂移：

**可验证事实标准（Haiku 负责）：**
- 数字：必须能在字幕原文找到出处，否则标❓
- 人名归属：Jason 说的 ≠ Chamath 说的，错了就是错了
- 公司名：英文原名保留，括号加中文

**五维分析结构标准（机械检查）：**
- 五维①-⑤ 是否都有 → 数数
- 总字数是否 150-250 字 → 统计
- ⑤国内启示是否出现中国公司/政策名词 → 关键词检查

**各角色权力边界：**
- Haiku：只能标❓，不能改内容
- Writer (Sonnet)：定稿权，但必须回应每个❓
- 异常检测 (Opus)：只输出"⚠️需关注"或"✅未发现异常"，不推翻 Sonnet 的风格判断

#### 被否决的方案及原因

| 方案 | 否决原因 |
|------|---------|
| ❌ 冷眼做主观质量审查 | 不同模型对"好"的定义不同，无法收敛，产生沉默的内耗（选贤陷阱） |
| ❌ 引入质量合同但保留主观冷眼 | 合同能解决结构检查，解决不了主观判断分歧，根本矛盾未消除 |
| ❌ 把质量判断完全交给用户 | 用户不懂英文，验证链断在能力边界处 |
| ❌ 彻底去掉外部视角 | 丢失交叉检查价值；问题是职责定义错了，不是角色多余 |
| ❌ 全程用 Claude（原方案） | 约 50 万 token/期，session 易中断，成本不可持续 |
| ❌ llm-subtrans 工具 | 需要额外依赖，直接调 Doubao API 更简洁，控制更精确 |

#### 逐字稿格式规范更新

原格式（已废弃）：
```
<大段 EN 灰色块>
中文翻译段落...
```

新格式（逐句对照，紧凑）：
```
**[时间] 章节标题**

> **Jason**: 英文原句
**Jason**：中文翻译

> **Chamath**: 英文原句
**Chamath**：中文翻译

<callout background-color="light-blue">有实质洞察时才加</callout>
```

- 验收：E271 起用新流水线跑通，单期 Claude 消耗 ≤ 5000 token，逐字稿格式符合新规范
- 状态：✅ 脚本开发完成（2026-04-29）
  - `scripts/allin/vtt_clean.py`：VTT 去重 + 分段，已测试 E270（6段 354句）
  - `scripts/allin/translate_bilingual.py`：调 Doubao API，支持断点续传，已测试 E270（~87KB 输出，约2分钟）
  - `scripts/allin/build_feishu_page.py`：组装页面，读取 analysis.json，dry-run 验证通过（102KB）
  - `scripts/allin/run_episode.sh`：一键运行脚本，串联全流程
  - `skills/lark-knowledge-allin-transcript/SKILL.md`：更新至 v2.0，新增多模型分工、质量合同、格式规范
  - 待验收：E271 真实运行跑通全流程（Claude AI 分析步骤需在主会话执行）
- API 配置：火山引擎 ARK，Base URL `https://ark.cn-beijing.volces.com/api/coding/v3`，Model `doubao-seed-2.0-pro`
