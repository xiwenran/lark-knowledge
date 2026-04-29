---
name: lark-knowledge-allin-transcript
version: 2.0.0
description: "All In Podcast 逐字稿生成：多模型分工流水线，Doubao翻译+Haiku核查+Sonnet注释+Opus异常检测，写入飞书知识库页面。触发词：allin逐字稿、生成逐字稿、allin转写、allin建页。"
metadata:
  requires:
    bins: ["lark-cli", "yt-dlp", "python3"]
    pip: ["openai", "anthropic"]
    scripts:
      - scripts/allin/vtt_clean.py
      - scripts/allin/translate_bilingual.py
      - scripts/allin/build_feishu_page.py
      - scripts/allin/run_episode.sh
    env:
      - ARK_API_KEY  # 火山引擎 API Key
---

# All In Podcast 逐字稿生成 v2.0

**CRITICAL — 开始前 MUST 先读取：**
1. `~/.agents/skills/lark-knowledge-config/config.json` → 读 `all_in_podcast` 区块
2. `../lark-shared/SKILL.md` — 认证、权限处理

---

## 一键运行（推荐）

```bash
export ARK_API_KEY=<火山引擎APIKey>
cd ~/lark-knowledge
bash scripts/allin/run_episode.sh <YouTube_URL> <record_id>
```

可选参数：
- `--skip-checks`：跳过 Haiku 核查和 Opus 异常检测（调试用）
- `--dry-run`：只生成预览 Markdown，不写入飞书
- `SEGMENT_MINUTES=20`：调整分段时长（默认 15 分钟）

---

## 模型分工与质量合同

### 各模型职责

| 角色 | 模型 | 职责 |
|------|------|------|
| 翻译 Worker | **Doubao-Seed-2.0-pro**（火山引擎） | 字幕全文逐句翻译，成本约为 Claude 的 1/10 |
| 事实校对 | **Claude Haiku** | 核查数字/人名/归属，输出中文异常报告 |
| 内容生产 | **Claude Sonnet** | 注释生成 + 五维分析 + 精华金句 |
| 异常检测 | **Claude Opus** | 世界知识核验 + 内部一致性检查 |

### 各角色权力边界（严格遵守）

- **Doubao**：只翻译，不分析，不判断重要性
- **Haiku**：只能标 ❓，不能改内容，只做机械比对
- **Sonnet**：定稿权，但必须回应每个 Haiku 的 ❓
- **Opus**：只输出 ⚠️ 或 ✅，不推翻 Sonnet 的风格判断，只纠事实错误

### 可验证事实标准（Haiku 执行）

- 数字：必须能在字幕原文找到出处，否则标 ❓
- 人名归属：Jason 说的 ≠ Chamath 说的，错了就是错了
- 公司名：英文原名保留，括号加中文（如 `Salesforce（赛富时）`）

---

## 手动分步操作

### Step 1：读取收件表记录

```bash
lark-cli base +record-get \
  --base-token "<config.all_in_podcast.base_token>" \
  --table-id "<config.all_in_podcast.table_id>" \
  --record-id "<record_id>"
```

提取：期号、中文标题、发布日期、YouTube链接、主题分类、五维分析（AI摘要字段）。

---

### Step 2：下载并清洗字幕

#### 2A. 下载字幕

```bash
yt-dlp --write-auto-sub --sub-lang en --sub-format vtt --skip-download \
  --output "/tmp/allin_<ID>" "<YouTube URL>"
```

#### 2B. 清洗 VTT → 分段 JSON

```bash
python3 scripts/allin/vtt_clean.py \
  /tmp/allin_<ID>.en.vtt \
  /tmp/allin_<ID>_segments.json \
  --segment-minutes 15
```

输出：`segments.json`，格式为 `[{index, time_label, sentences: [{time_start, text, speaker_change}]}]`

---

### Step 3：Doubao 翻译（逐句双语）

```bash
export ARK_API_KEY=<火山引擎APIKey>
python3 scripts/allin/translate_bilingual.py \
  /tmp/allin_<ID>_segments.json \
  /tmp/allin_<ID>_bilingual.json
```

**支持断点续传**：中断后加 `--start-from N` 从第 N 段继续。

**翻译输出格式**（每句）：
```
> Jason: 英文原句
**Jason**：中文翻译
```

**翻译原则**：
- 保持口语感，像真人在说话
- 公司名/产品名保留英文，括号加中文
- 金融/科技专业术语必须准确
- 数字保留英文原始格式（`$140B`不改成"1400亿"）

---

### Step 4：Haiku 事实核查

`build_feishu_page.py` 内置，自动执行。也可单独触发：

核查范围：
- 所有包含数字、$、% 的英文原句
- 与已知四位主播立场有明显矛盾的表述
- 说话人归属（基于上下文判断）

**输出**：中文异常报告，供用户决策：
```
⚠️ 发现 N 处需确认：
① [时间] 问题描述 → 建议操作
```

---

### Step 5：Sonnet 注释 + 五维分析 + 金句

自动执行。基于完整中文译文生成：

**精华金句**（3-5条）：
```
> **"英文原句"**
> 中文译文 — 说话人
```

**注释标注**（≤15条建议）：
- 触发条件：普通读者不熟悉的背景 / 中国市场类比 / 数据需背景 / 四人明显分歧
- 禁止：纯转述、政治倾向性解读、每段超过2条

---

### Step 6：Opus 异常检测

自动执行。评判维度（不依赖英文原文）：

1. **世界知识核验**：四位主播立场与公开记录是否一致
   - Chamath：批评美联储，支持 AI/科技，批评 ESG
   - Sacks：关注估值和盈利能力，对监管保持警惕
   - Jason：乐观主义者，押注成长型公司
   - Friedberg：数据和科学导向，关注农业/生命科学

2. **内部一致性**：五维分析各维度是否有逻辑矛盾

3. **合理性检查**：数字量级是否异常

**输出**：中文报告，⚠️ 需关注 或 ✅ 通过

---

### Step 7：组装页面 + 写入飞书

```bash
python3 scripts/allin/build_feishu_page.py \
  /tmp/allin_<ID>_bilingual.json \
  --record-id "<record_id>"
```

---

## 页面格式规范 v2.0

### 逐字稿格式（每个章节）

```markdown
**[HH:MM–HH:MM] 章节主题（AI概括）**

> **Jason**: 英文原句
**Jason**：中文翻译

> **Chamath**: 英文原句
**Chamath**：中文翻译

<callout background-color="light-blue">注释内容，1-2句，自然散文风格</callout>
```

### 格式铁律

| 规则 | 执行方式 |
|------|---------|
| 章节标题 | `## <text color="blue">标题</text>` |
| 英文原句 | `> **说话人**: 原文`（引用块） |
| 中文译文 | `**说话人**：译文` |
| 注释块 | `<callout background-color="light-blue">` 无 emoji 无标题 |
| 概览块 | `<callout background-color="light-yellow">` |
| **禁止** | 逐字稿区域不用 `<text color="red/blue/...">` 着色词 |
| red 着色 | 仅限五维分析里的关键数字 |

### 完整页面结构

```
{期号} · {日期} · {时长}分钟 · 播放量{播放量} · {主题}

📌 一句话核心亮点（≤30字）

<callout light-yellow>· 议题 · 关键判断 · 国内启示</callout>

## 手绘笔记速览
## 📥 下载资源
## 五维分析（一至五）
## 精华金句
## 中英对照逐字稿
```

---

## Step 8：更新收件表

```bash
lark-cli base +record-upsert \
  --base-token "<config.all_in_podcast.base_token>" \
  --table-id "<config.all_in_podcast.table_id>" \
  --record-id "<record_id>" \
  --json '{"飞书页面URL": "<url>", "翻译状态": "已完成", "注释状态": "已完成"}'
```

---

## 注意事项

- **字幕无法获取**：yt-dlp 失败时告知用户，接受手动上传 .vtt/.srt/.txt
- **五维分析来源**：优先用收件表 AI摘要字段（P3-B 已生成）
- **注释密度**：全期不超过 20 条（约每 5 分钟 1 条）
- **ARK_API_KEY**：火山引擎控制台获取，不要硬编码进脚本
- **断点续传**：翻译中断后用 `--start-from N` 继续，不用重头来

---

## 权限

`bitable:record`、`docs:doc`、`wiki:node:readonly`
