---
name: lark-knowledge-allin-transcript
version: 1.0.0
description: "All In Podcast 逐字稿生成：将 YouTube 字幕翻译为中英对照格式，含嵌入式注释，按 All In 专用排版规范写入飞书知识库页面。触发词：allin逐字稿、生成逐字稿、allin转写、allin建页。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# All In Podcast 逐字稿生成

**CRITICAL — 开始前 MUST 先用 Read 工具读取：**
1. `~/.agents/skills/lark-knowledge-config/config.json` → 读 `all_in_podcast` 区块，获取 base_token、table_id、wiki directories 字段
2. `../lark-shared/SKILL.md` — 认证、权限处理

## 适用场景

已完成 P3-B 收件（收件表里有对应记录）后，生成该期的完整飞书知识库页面：
- 中英对照逐字稿（全文翻译）
- 嵌入式注释（有实质洞察处才写）
- 完整页面结构（顶部信息块 + 五维分析 + 精华金句 + 逐字稿）

---

## 输入

用户提供**以下任一**：
- 收件表 record_id（P3-B 写入后返回的 ID）
- YouTube URL（skill 自行从收件表查找对应记录）
- 期号（如 E327）

---

## 工作流

```
读取收件表记录 → 获取完整字幕 → 分章节翻译（Worker）→ 添加注释（Writer）→ 组装页面 → 写入 Wiki → 更新收件表
```

---

## Step 1: 读取收件表记录

```bash
lark-cli base +record-get \
  --base-token "<config.all_in_podcast.base_token>" \
  --table-id "<config.all_in_podcast.table_id>" \
  --record-id "<record_id>"
```

从记录中提取（后续步骤使用）：
- 期号、英文原标题、中文标题
- 发布日期（用于确定年份节点）
- YouTube链接
- 主题分类（用于确定 wiki 目录节点）
- 五维综合评分的完整五维分析文本（P3-B 写入的 AI摘要字段中）
- 精华金句（P3-B 的审核备注字段，若有记录）

---

## Step 2: 获取完整字幕

### 2A. yt-dlp 下载英文字幕

```bash
yt-dlp --write-auto-sub --sub-lang en --sub-format vtt --skip-download \
  --output "/tmp/allin_%(id)s" "<YouTube URL>"
```

字幕文件路径：`/tmp/allin_<视频ID>.en.vtt`

### 2B. 清理 vtt 格式，获得纯文本

```bash
# 去掉时间码和 WEBVTT 头，合并为连续文本
python3 -c "
import re, sys
content = open(sys.argv[1]).read()
# 去时间码行
content = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*\n', '', content)
# 去 WEBVTT 和空行序号
content = re.sub(r'WEBVTT\n', '', content)
content = re.sub(r'^\d+\$', '', content, flags=re.MULTILINE)
# 合并空行
content = re.sub(r'\n{3,}', '\n\n', content)
print(content.strip())
" /tmp/allin_<视频ID>.en.vtt > /tmp/allin_<视频ID>_clean.txt
```

### 2C. 将全文按时间分段（约 10-15 分钟一段）

All In 单期 60-120 分钟，约 15000-30000 词，**必须分段处理**，否则单次 prompt 超限。

分段原则：
- 保留 vtt 时间码信息，每段约 10-15 分钟
- 按话题转换点切割（看时间码密度变化）
- 每段约 2000-4000 词

**输出**：`[{"time": "00:00–12:30", "text": "...原文..."}, ...]` 格式的分段列表

---

## Step 3: Worker — 逐段翻译（Sonnet 4.6 子代理）

**处理方式**：每段独立翻译，可并行处理（段间无依赖）。

**翻译规则**：

1. **逐段翻译，不压缩**：忠实原意，保留所有细节，不摘要、不删减
2. **说话人标注**：当能识别说话人时，在段落开头加 `**Chamath**：` / `**Jason**：` / `**Sacks**：` / `**Friedberg**：`；混杂难辨时可省略
3. **专有名词保留**：公司名、产品名、人名用原文；数字保留英文原始数字
4. **口语化翻译**：All In 是对谈节目，翻译要有口语感，不要文绉绉

**每段翻译输出格式**：

```
**[00:00–12:30] <章节主题（AI 概括）>**

中文翻译段落……（说话人对话按自然段落分隔）

<text color="grey">EN: Original transcript text here, as faithful as possible to the original, preserving speaker turns...</text>
```

> 每个时间段对应一个中文翻译块 + 一个 `<text color="grey">EN: ...</text>` 块。
> EN 块不换行（整个时间段的英文原文放在一个 grey text 标签里）。

---

## Step 4: Writer — 嵌入注释（Sonnet 4.6 子代理）

**任务**：在 Step 3 的翻译稿基础上，**仅在有实质洞察处**插入 light-blue callout 注释。

### 注释触发标准（必须满足至少一条才写注释）

- 出现了普通读者不熟悉的背景信息（公司历史、人物关系、行业术语）
- 四人的判断与中国市场有直接可迁移的类比
- 数据或论断需要背景补充才能理解意义
- 四人之间有明显分歧，值得单独点出

### 注释禁止事项

- ❌ 不写「以上是 XX 对 YY 的看法」等纯转述
- ❌ 不在政治敏感内容处做倾向性解读（只说「影响 XX 板块」）
- ❌ 每段不超过 1-2 条注释（宁缺勿滥）
- ❌ 逐字稿区域禁止着色词（不用 `<text color="red">` 等）

### 注释插入位置

注释 callout 紧跟对应中文段落之后、EN 块之前：

```
中文翻译段落……

<callout background-color="light-blue">注释内容，自然散文风格，1-3 句话。可以正常换行。</callout>

<text color="grey">EN: Original text...</text>
```

若该段无注释价值，直接跳过，格式为：

```
中文翻译段落……

<text color="grey">EN: Original text...</text>
```

---

## Step 5: 组装完整页面

### 5A. 确定 Wiki 目录节点

根据收件表记录的「主题分类」 + 发布日期年份，从 config 中查找对应节点 token：

```
config.all_in_podcast.wiki.directories["科技&AI"]["2025"]
```

| 主题分类 | 年份 | config 路径 |
|---------|------|------------|
| 科技&AI | 2024 | `directories["科技&AI"]["2024"]` |
| 科技&AI | 2025 | `directories["科技&AI"]["2025"]` |
| 全球视野 | 2024 | `directories["全球视野"]["2024"]` |
| … | … | … |

### 5B. 拼装页面 Markdown

按以下固定结构组装（All In 专用排版规范，与通用知识库规则完全独立）：

```markdown
<期号> · <发布日期> · <时长>分钟 · 播放量 <播放量（万为单位）> · <主题分类>

---

📌 <一句话定位——基于中文标题+五维分析的核心亮点改写，不超过30字>

<callout background-color="light-yellow">
· 议题：<从五维分析①摘取一句>
· 关键判断：<从五维分析②摘取最重要的一个论点>
· 国内启示：<从五维分析⑤摘取一句直接结论>
</callout>

---

## <text color="blue">手绘笔记速览</text>

（待补充）

---

## <text color="blue">📥 下载资源</text>

（待补充）

---

## <text color="blue">五维分析</text>

### <text color="blue">一、本期议题</text>

<p3-b五维分析①的内容>

### <text color="blue">二、核心论点链</text>

<p3-b五维分析②的内容>

### <text color="blue">三、市场与行业判断</text>

<p3-b五维分析③的内容>

### <text color="blue">四、四人立场图谱</text>

<p3-b五维分析④的内容>

### <text color="blue">五、国内启示</text>

<p3-b五维分析⑤的内容>

---

## <text color="blue">精华金句</text>

> **"<英文原句>"**
> <中文译文> — <说话人>

（3-5 条，来自 P3-B 收件时记录的精华金句）

---

## <text color="blue">中英对照逐字稿</text>

<Step 4 产出的完整注释版逐字稿，按时间段顺序拼接>
```

**排版铁律（All In 专用，与通用知识库规则完全独立）**：

| 规则 | All In 产品执行方式 |
|------|-------------------|
| 章节标题 | `## <text color="blue">标题</text>` |
| 英文原文 | `<text color="grey">EN: ...</text>` |
| 注释块 | `<callout background-color="light-blue">` 无 emoji 无标题 |
| 核心概览 | `<callout background-color="light-yellow">` 无 emoji 无标题 |
| 逐字稿着色词 | **禁止**，逐字稿区域不做关键词着色 |
| red 标注 | **仅限五维分析**里的关键数字 |
| 标题层级 | `## `（二级）用于主章节，`### `（三级）用于五维子章节 |

---

## Step 6: 写入 Wiki 页面

### 6A. 创建新页面

```bash
lark-cli docs +create \
  --wiki-node "<对应目录节点 token>" \
  --title "E<期号> · <中文标题>" \
  --markdown "<Step 5B 的完整页面内容>"
```

返回值中提取 `doc_url`（wiki 页面链接）。

### 6B. 页面过长时分批写入

All In 逐字稿约 5000-10000 字，超过 `docs +create` 单次限制时：

1. 先用 `+create` 创建页面，写入 Step 5B 中**逐字稿章节以外**的部分（信息块 + 五维分析 + 精华金句）
2. 再用 `+update --mode append` 追加完整逐字稿：

```bash
lark-cli docs +update \
  --doc "<doc_token>" \
  --mode append \
  --markdown "<逐字稿完整内容>"
```

---

## Step 7: 更新收件表记录

写入成功后，更新对应记录的状态字段：

```bash
lark-cli base +record-upsert \
  --base-token "<config.all_in_podcast.base_token>" \
  --table-id "<config.all_in_podcast.table_id>" \
  --record-id "<record_id>" \
  --json '{
    "飞书页面URL": "<wiki 页面链接>",
    "翻译状态": "已完成",
    "注释状态": "已完成"
  }'
```

---

## Step 8: 完成汇报

```
逐字稿页面生成完成 ✅
E<期号> | <中文标题>
Wiki 页面：<链接>
字幕段数：<N> 段 | 注释条数：<M> 条
翻译状态 → 已完成 | 注释状态 → 已完成
```

---

## 注意事项

- **字幕无法获取时**：yt-dlp 失败（无自动字幕）→ 告知用户，提供手动上传字幕文件的选项（.vtt/.srt/.txt 均可）
- **五维分析来源**：优先用收件表里的 AI摘要字段（P3-B 已生成）；若格式不完整，可重新生成
- **精华金句来源**：优先用收件表审核备注字段；若无，由 Writer 在翻译过程中从原文摘取
- **注释密度**：整期约 60-120 分钟，全文注释不超过 20 条（平均每 5-10 分钟 1 条）
- **分段翻译顺序**：可并行翻译不同段落，Writer 添加注释时需按顺序处理（保持前后文一致性）

---

## 权限

`bitable:record`、`docs:doc`、`wiki:node:readonly`
