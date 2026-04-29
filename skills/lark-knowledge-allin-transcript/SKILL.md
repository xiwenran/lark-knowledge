---
name: lark-knowledge-allin-transcript
version: 2.2.0
description: "All In Podcast 逐字稿生成：说一句话全自动完成，含翻译+AI分析+排版美化。触发词：allin逐字稿、生成逐字稿、allin转写、allin建页。用法：allin逐字稿 <YouTube_URL> <record_id>"
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

# All In Podcast 逐字稿生成 v2.1

**用户只需说一句话**，Claude Code 自动完成全部步骤：

```
allin逐字稿 https://youtube.com/watch?v=xxx recXXXXXX
```

---

## 完整自动化流程（Claude Code 自动执行）

触发后按以下顺序全部自动完成，无需用户手动干预：

### 🤖 Step 1：读取收件表记录

**CRITICAL — 开始前 MUST 先读取：**
1. `~/.agents/skills/lark-knowledge-config/config.json` → 读 `all_in_podcast` 区块
2. `../lark-shared/SKILL.md` — 认证、权限处理

```bash
lark-cli base +record-get \
  --base-token "<config.all_in_podcast.base_token>" \
  --table-id "<config.all_in_podcast.table_id>" \
  --record-id "<record_id>"
```

提取：期号、中文标题、发布日期、YouTube链接、主题分类、五维分析（AI摘要字段）。

---

### 🤖 Step 2：下载 + 翻译（run_episode.sh）

```bash
export ARK_API_KEY=<从用户环境或 config 读取>
cd ~/lark-knowledge
bash scripts/allin/run_episode.sh <YouTube_URL> <record_id>
```

自动完成：
- **2A** yt-dlp 下载英文字幕（`.en.vtt`）
- **2B** vtt_clean.py 去重清洗，按 15 分钟分段 → `segments.json`
- **2C** translate_bilingual.py 调 Doubao-Seed-2.0-pro 逐句翻译 → `bilingual.json`

输出路径：`/tmp/allin_<VIDEO_ID>/bilingual.json`

> **字幕下载失败时**：告知用户，接受手动上传 .vtt/.srt/.txt，直接传给 vtt_clean.py

---

### 🤖 Step 3：Haiku 事实核查

读取 `bilingual.json`，用 **Claude Haiku** 核查：
- 所有包含数字、$、% 的句子（原文 vs 译文数字一致性）
- 与已知四位主播立场有明显矛盾的表述
- 说话人归属是否合理

**权力边界**：只标 ❓，不改内容，只做机械比对。

输出中文报告展示给用户：
```
⚠️ 发现 N 处需确认：
① [时间] 问题描述 → 建议操作
```

用户确认后继续（默认全部接受可直接 Enter）。

---

### 🤖 Step 4：Sonnet 注释 + 五维分析 + 精华金句

基于完整中文译文，用 **Claude Sonnet** 生成：

**精华金句**（3-5条）：
```
> **"英文原句"**
> 中文译文 — 说话人
```

**注释**（≤15条，全期 91 分钟约每 5 分钟 1 条）：
- 触发：普通读者不熟悉的背景 / 中国市场类比 / 数据需背景 / 四人明显分歧
- 格式：`{time_label: ["注释内容"]}`

**五维分析终稿**（150-250字）：
```
① 议题背景
② 核心论点链
③ 市场与行业判断
④ 四人立场图谱（Chamath/Jason/Sacks/Friedberg）
⑤ 国内启示（必须出现中国公司/政策名词）
```

---

### 🤖 Step 5：Opus 异常检测

将中文译文 + 五维分析交给 **Claude Opus** 检测：
1. **世界知识核验**：四位主播立场与公开记录是否一致
   - Chamath：批评美联储，支持 AI/科技，批评 ESG
   - Sacks：关注估值和盈利能力，对监管保持警惕
   - Jason：乐观主义者，押注成长型公司
   - Friedberg：数据和科学导向，关注农业/生命科学
2. **内部一致性**：五维各维度是否有逻辑矛盾
3. **合理性检查**：数字量级是否异常

输出中文报告：⚠️ 需关注 或 ✅ 通过，用户确认后继续。

---

### 🤖 Step 6：保存 AI 分析结果

将 Step 3-5 的输出整合，保存到：

```
/tmp/allin_<record_id>_analysis.json
```

格式：
```json
{
  "quotes": "精华金句 Markdown 文本",
  "annotations": {
    "00:00:00–00:15:00": ["注释1", "注释2"],
    "00:15:00–00:30:00": ["注释3"]
  },
  "five_dim": "① 议题背景...\n② 论点链...\n③ ...\n④ ...\n⑤ ..."
}
```

---

### 🤖 Step 7：组装页面 + 写入飞书

```bash
python3 ~/lark-knowledge/scripts/allin/build_feishu_page.py \
  /tmp/allin_<VIDEO_ID>/bilingual.json \
  --record-id "<record_id>"
```

自动完成：
- 读取 `analysis.json` + 收件表元数据
- 组装完整飞书页面 Markdown
- lark-cli 分批写入飞书 Wiki（头部+五维先创建，逐字稿分批 append）
- 回填收件表：飞书页面URL、翻译状态=已完成、注释状态=已完成

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

### 🤖 Step 8：排版美化（分区处理）

> 完整排版规则见 `../lark-knowledge-format/SKILL.md`（模式 2 引用）

写入飞书后，对页面进行区域化排版：

#### 排版分区规则（All In 专用）

| 区域 | 排版策略 | 原因 |
|------|---------|------|
| 页面头部一句话摘要 | 正常着色（公司名 blue、数字 red） | 引流入口，需视觉冲击 |
| light-yellow 概览 callout | 保持原样，不改 | callout 背景已足够 |
| 五维分析各节 | **重点着色**（数字 red、公司人名 blue、判断词 green/red） | 分析类内容，颜色增强可读性 |
| 精华金句 | 金句引用块整体 `light-purple` 背景，说话人名 blue | 金句要突出，有格调 |
| **逐字稿区域** | **❌ 禁止添加任何 `<text color>` 着色** | 双语逐句体裁，加颜色变花哨乱 |
| 注释 callout | 保持 light-blue 原样，不改 | 已格式化 |

#### 五维分析着色规则

```
数字/金额/比例/量级   → <text color="red">$140B</text>
公司名/产品名         → <text color="blue">Salesforce（赛富时）</text>
主播人名              → <text color="blue">Chamath</text>
积极判断词            → <text color="green">显著改善</text>
风险/警告词           → <text color="red">债务炸弹</text>
核心结论句            → <text color="red" background-color="light-red">最强洞察</text>
专业术语首次出现      → <text background-color="light-yellow">自由现金流</text>
```

#### 执行方式

```bash
# 1. 读取页面
lark-cli docs +fetch --doc <wiki_url>

# 2. 按分区规则重写（只处理五维+金句+头部，逐字稿段跳过）

# 3. 写回
lark-cli docs +update --doc <wiki_url> --mode overwrite --markdown "<排版后内容>"
```

**注意**：逐字稿段（`## <text color="blue">中英对照逐字稿</text>` 之后的所有内容）**原封不动复制**，一个字符都不改。

---

## 注意事项

- **字幕无法获取**：yt-dlp 失败时告知用户，接受手动上传 .vtt/.srt/.txt
- **五维分析来源**：优先用收件表 AI摘要字段（P3-B 已生成）→ 再用 Sonnet 现场生成
- **注释密度**：全期不超过 20 条（约每 5 分钟 1 条）
- **ARK_API_KEY**：火山引擎控制台获取，不要硬编码进脚本
- **断点续传**：翻译中断后用 `--start-from N` 继续，不用重头来

---

## 权限

`bitable:record`、`docs:doc`、`wiki:node:readonly`
