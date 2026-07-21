> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

## 第四期 P3 — All In Podcast 中文知识库产品

**触发**：2026-04-28 会话。基于现有 lark-knowledge 生产线，新建独立飞书知识库空间，把 All In Podcast（硅谷顶级 VC 播客，107 万订阅）翻译、分析、结构化，做成三层付费知识库产品在小红书售卖。

**三层产品**：
1. 手绘笔记（Sketchnote，免费引流）
2. 中英对照逐字稿 原稿版（基础付费）
3. 含五维分析注释的 注释版（高级付费）
两个付费版均配 Kami 可打印 PDF。

**方案文档**：`~/Obsidian/PersonalWiki/方案/all-in-podcast-知识库产品.md`

**飞书基础设施**：
- Base（节目收件表）：base_token `<见 config.json>`，table_id `<见 config.json>`
- Wiki 空间：space_id `<见 config.json>`，根节点 `<见 config.json>`
- 知识库目录：导航总表 / 精选必读 / 科技&AI / 全球视野 / 金融&市场 / 商业&创业 / 人物专访（各含 2024/2025 子节点）
- 完整 ID 索引：`memory/reference_allinpodcast_ids.md`

### P3-A: 飞书基础设施搭建
- 目标：多维表格（17 字段）+ wiki 知识库目录结构就位，ID 入 config
- 涉及文件：`~/.agents/skills/lark-knowledge-config/config.json`、`memory/reference_allinpodcast_ids.md`
- 验收：表格 17 字段齐全（含综合得分公式）、6 大主题 + 2024/2025 子节点全部可访问
- 状态：✅ 已完成（commit `57e06f1`，2026-04-28）

### P3-B: All In 收件 Skill（YouTube 视频摘要入表）
- 目标：给定 YouTube 链接，自动提取标题/发布日期/播放量 + AI 生成五维分析摘要，写入节目收件表
- 涉及文件：新建 `skills/lark-knowledge-allin-intake/SKILL.md`
- 四段式流水线：Worker Sonnet 4.6（结构提取）→ Haiku 4.5（关键段校对）→ Writer Sonnet 4.6（五维分析撰写）→ 冷眼 Sonnet 4.6（审查）
- 五维框架：①议题背景 ②论点链 ③市场判断 ④四人立场 ⑤国内启示
- 验收：用 1 期真实 YouTube 链接跑完，收件表新增 1 条记录，五维摘要可读
- 状态：✅ 已完成（commit `6ea0e2d`，2026-04-28）

### P3-C: All In 逐字稿生成（中英对照排版）
- 目标：从 YouTube 字幕拉取原文，AI 翻译为中文，按「中文段落 + EN: 英文原文」格式排版，写入飞书知识库页面
- 涉及文件：新建 `skills/lark-knowledge-allin-transcript/SKILL.md`
- 排版规则：天蓝色标题、灰色 EN: 前缀、light-blue callout 作注释（有实质洞察才写）
- 验收：1 期逐字稿完整写入飞书页面，格式符合方案文档规范
- 状态：✅ 已完成（commit 4f51a00，2026-04-28）

### P3-D: All In 注释版生成（内联注释 + 五维分析章节）
- 目标：在逐字稿基础上，由 AI 添加内联注释 callout + 独立五维分析章节
- 涉及文件：`skills/lark-knowledge-allin-transcript/SKILL.md`（扩展注释逻辑）
- 注释标准：只在「数据/判断/公司名需要背景」处添加，不注水
- 验收：1 期注释版完整写入飞书页面，注释质量通过人工审查
- 状态：✅ 已合并进 P3-C（commit `4f51a00`，2026-04-28）
  - P3-C skill 的 Step 4（Writer 添加注释）和 Step 5B（独立五维章节）已覆盖本期全部内容
