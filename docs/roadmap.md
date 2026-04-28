# lark-knowledge 路线图

> 全项目规划文件,所有版本期都在此文件中。按 Echo「跨阶段项目规划必须物理化」规则维护。

## 第一期 P1 — lint 升级 + Deep Research 接入(进行中)

**触发**:2026-04-21 会话讨论。参考 nashsu/llm_wiki 的四信号关联算法与空白识别思路,决定偷学两样能力进 lark-knowledge:
1. 现有 lark-knowledge-lint 扩展补链/聚类能力
2. 新建 lark-knowledge-research skill,调 Tavily API 自动补空白

**已砍掉**(用户本日拍板):Chrome 剪藏(Claude Code WebFetch 已够用)、lark-knowledge-intake 两步摄入升级(批量摄入一步够)。

### P1-A:lark-knowledge-lint 加四信号补链算法
- 目标:给现有 lint skill 加"未直接互链但内容相关"的补链建议能力
- 涉及文件:`skills/lark-knowledge-lint/SKILL.md`、可能新增 `scripts/lark_lint/signals.py`
- 算法参考:`~/Echo/scripts/obsidian_lint/signals.py`(直接链接 ×3.0、来源重叠 ×4.0、Adamic-Adar ×1.5、类型亲和 ×1.0)
- 验收:在现有飞书知识库实跑,Top 20 补链建议能由用户肉眼判合理
- 状态:✅ 已完成（commit `2073f44`）

### P1-B:lark-knowledge-lint 加 Louvain 聚类 + 松散聚类识别
- 目标:识别内聚度偏低的社区、孤岛页面
- 涉及文件:`skills/lark-knowledge-lint/SKILL.md`、可能新增 `scripts/lark_lint/community.py`
- 参数调优:Obsidian 端用内聚度 < 0.15 判松散;lark-knowledge 规模更大,阈值和 Top N 可能需要放宽(首跑后调)
- 验收:松散聚类清单能指向真实的"没整理完"区块
- 状态:✅ 已完成（commit `6408931`）

### P1-C:新建 lark-knowledge-research skill 框架
- 目标:搭骨架——触发词、默认路径、与 lint 的协作契约、草稿写回位置
- 涉及文件:新建 `skills/lark-knowledge-research/SKILL.md`、`scripts/lark_research/` 目录
- 触发词(建议):补空白 / Deep Research / 研究补漏
- 与 lint 的协作:P1-B 产出的空白/松散聚类清单可作为 research 的输入
- 验收:skill 可被触发,输出结构化的研究任务清单(尚未真跑 API)
- 状态:✅ 已完成（commit `01a96d7`）

### P1-D:research skill 接入 Tavily API
- 目标:空白识别 → Tavily 搜索 → LLM 提炼 → 回写飞书草稿
- 涉及文件:`skills/lark-knowledge-research/SKILL.md`、`scripts/lark_research/*.py`
- 前置:用户已有 Tavily API 订阅,密钥走 env 变量不硬编码
- 验收:针对一个真实空白主题,能产出可读的草稿写入飞书"待确认"区
- 状态:✅ 已完成（commit `ee2d23e`）

### P1-E:两个 skill 联动闭环
- 目标:lint 扫出空白 → research 批量补 → 用户确认后写入正式库
- 涉及文件:两个 skill 的 SKILL.md 互相引用、可能新增调度脚本
- 验收:一次"巡检 → 研究 → 确认"完整跑通,无人工粘合
- 状态:⏸ 待启动(依赖 P1-A/B/C/D 全部落地)

---

## 本期依赖

- 依赖 Obsidian 端 Echo v5.4-C 落地经验(networkx + python-louvain 验证过,可直接迁移)
- 算法参考 `~/Echo/scripts/obsidian_lint/`,不重造轮子
- lark-knowledge 规模大于 Obsidian,算法参数(Top N、聚类阈值)首跑后调优

## 本期不做(用户本日明确砍掉)

- Chrome 剪藏浏览器扩展——Claude Code 的 WebFetch 已经能读网页,不值得自建扩展
- lark-knowledge-intake 两步思维链摄入——商业资产批量场景容错度比个人档案高,一步够用,两步是 Obsidian 端才需要的精度

---

## 第二期 P11 — 多源抓取器（✅ 已完成，2026-04-21）

> 说明：编号 P11 是历史决定，保留以对齐已有 commit（`47e249c` / `37d4339`）和 9 处引用（SKILL.md / fetchers/README.md / types.py / superpowers plan 等）。编号非连续不影响项目推进。

整体分 6 期。依赖链：**P11.1（基础设施）→ P11.2-P11.6 按复杂度递进**。每期独立可派单，前序阶段不完成不能开下一期。图片类型不单独立期，走"附件入库 + 下游多模态直读"，不消耗 OCR 工期。

### P11.1 · 基础设施：分发器 + source_type 字段 + fetchers 骨架
- **目标**：搭好路由架构，但不抓任何新内容。让任意 URL / 文件进入 intake 时能被正确识别类型，字段扩展就位
- **涉及文件**：
  - `~/lark-knowledge/config.json`（加 `source_type` 字段定义 + 枚举值）
  - `~/.claude/skills/lark-knowledge-intake/SKILL.md`（引入 fetchers 模块说明）
  - `~/.claude/skills/lark-knowledge-intake/fetchers/dispatcher.py`（新建，分发器核心）
  - `~/.claude/skills/lark-knowledge-intake/fetchers/__init__.py`
  - 飞书多维表格模板：手动加 source_type 字段
- **验收**：
  - dispatcher 给 10 个测试 URL + 3 个文件路径，正确返回 source_type 枚举
  - 任何类型输入至少返回 `{source_type, url/file_path}` 不崩溃
  - source_type 字段成功写入多维表格一条测试记录
- **派发模式**：🅰️ 自主模式
- **状态**：✅ 已完成（commit `47e249c`，2026-04-21）

### P11.2 · 无状态网页类（article / paywall_news / fallback）
- **目标**：公开网页 + 付费墙新闻能正文入库，fallback 链完整工作
- **涉及文件**：
  - `fetchers/article.py`（r.jina.ai / defuddle.md 调用）
  - `fetchers/paywall.py`（Googlebot UA + X-Forwarded-For + Referer 伪装）
  - `fetchers/archive.py`（Archive.today / Google Cache 降级）
  - `fetchers/dispatcher.py`（级联逻辑接入）
  - 配置：已知 paywall 域名列表（yaml）
- **验收**：
  - 10 个公开网页（blog / Substack 等）全部拿到 markdown 正文
  - 3 个 paywall 站（NYT / WSJ / FT）至少 2 个能正文入库
  - 故意给失效链接，fallback 能降级到 archive 拿到历史版本
- **派发模式**：🅰️ 自主模式
- **状态**：✅ 已完成（commit `47e249c`，2026-04-21）

### P11.3 · 文档附件（markitdown 全家桶）
- **目标**：PDF / DOCX / PPTX / XLSX / EPUB / arxiv 统一转 markdown 入库
- **涉及文件**：
  - `fetchers/document.py`（markitdown 封装）
  - `fetchers/arxiv.py`（识别 arxiv URL 走 PDF 路径）
  - 依赖：`pip install markitdown`
- **验收**：
  - 每种扩展名至少一份真实样本转换成功
  - arxiv 链接能自动下载 PDF 并转 md
  - 大文件（>50MB PDF）有超时保护
- **派发模式**：🅰️ 自主模式
- **状态**：✅ 已完成（commit `47e249c`，2026-04-21）

### P11.4 · 微信公众号（Playwright 登录态）
- **目标**：公众号长文 URL 能全文入库，扫码登录态走 `.local`
- **涉及文件**：
  - `fetchers/wechat.py`（Playwright 封装 或 `wexin-read-mcp` 集成）
  - `~/.claude/skills/lark-knowledge-intake/.local/wechat_cookie.json`（gitignore）
  - `.gitignore`（确认 `.local/` 已排除）
  - SKILL.md：加首次使用时的扫码引导段
- **验收**：
  - 首次运行弹扫码，登录后 cookie 持久化
  - 3 篇不同公众号长文（含图片、代码块）正文入库
  - cookie 过期时有明确错误提示，引导重新扫码
- **派发模式**：🅱️ 施工模式（登录态管理是高风险点，Opus 主导设计 `.local` 机制后 Codex 施工）
- **状态**：✅ 已完成（骨架，commit `47e249c`，2026-04-21；真实扫码+抓取验收待后续会话）

### P11.5 · 音视频转写（Get 笔记 API）
- **目标**：B 站 / 小宇宙 / 喜马拉雅 / YouTube 视频能转写入库
- **涉及文件**：
  - `fetchers/transcript.py`（Get 笔记 API 封装）
  - `~/.claude/skills/lark-knowledge-intake/.local/getnote_api_key`（用户输入）
  - 配置：Get 笔记支持的平台域名白名单
- **验收**：
  - B 站视频 + 小宇宙播客 + 喜马拉雅各测 1 条，逐字稿入库
  - YouTube 如 Get 笔记支持则过；不支持则标 `source_type=fetch_failed` 加降级 TODO
  - 转写时间戳信息保留在 meta 字段
- **派发模式**：🅰️ 自主模式
- **启动前需用户确认**：Get 笔记 API 费率 / 稳定性
- **状态**：✅ 已完成（骨架，commit `47e249c`，2026-04-21；Get 笔记 API key 真调用验收待后续会话）

### P11.6 · 登录态社交平台（OpenCLI 适配器）
- **目标**：推特 / 知乎 / 小红书偶发归档能拿到正文
- **涉及文件**：
  - `fetchers/opencli_bridge.py`（OpenCLI CLI 调用封装）
  - SKILL.md：Browser Bridge 扩展安装引导段
  - `~/.claude/skills/lark-knowledge-intake/.local/opencli_config/`
- **验收**：
  - Browser Bridge 扩展首次引导装完
  - 推特单条 + 推特线程各测 1 条入库
  - 知乎回答 + 知乎盐选各测 1 条入库
  - 小红书笔记测 1 条入库
  - 登录态失效有明确提示
- **派发模式**：🅱️ 施工模式（外部 Node.js 运行时 + 浏览器扩展，风险点多）
- **状态**：✅ 已完成（骨架，commit `47e249c`，2026-04-21；Browser Bridge 扩展 + OpenCLI CLI 真调用验收待后续会话）

### 整体验收
- intake skill 接到任意 URL / 文件，都能给出结构化入库结果（成功或 `fetch_failed` 带链接保留）
- 现有 5 个 skill 对外接口无破坏，原有流程不受影响
- `.local/` 目录零凭据入仓，git log 历史提交无敏感泄露

### 依赖与顺序约束
- P11.2 / P11.3 可并行（无状态、无依赖）
- P11.4 / P11.5 / P11.6 均依赖 P11.1
- P11.4 / P11.5 / P11.6 互不依赖，可按用户优先级拉动
- 图片类型不单独立期，走附件入库，由下游多模态模型直读

### 对抗性审查修复（2026-04-22，commit `37d4339`）

P11 全期落地后走 `/codex:adversarial-review`，Codex 发现并修复 3 处 dispatcher 安全/逻辑问题：

| # | 级别 | 问题 | 修法 |
|---|---|---|---|
| 1 | 🔴 HIGH | fallback 分支把非 URL 自由文本外发到 r.jina.ai / archive.today（数据外泄风险） | `dispatch()` fallback 加 `_is_http_url` 门，非 URL 直接返回本地校验错误 |
| 2 | 🔴 HIGH | `https://host/file.pdf` 远程 URL 被当本地路径送给 markitdown（必然失败） | doc 分支判 `_is_http_url`，远程先 `_download_remote_document()` 到临时文件再转，finally 清理 |
| 3 | 🟡 MEDIUM | dispatcher 用 `OPENCLI_CONFIG_PATH.is_file()` 前置门，绕过 bridge 的 PATH 发现能力 | 去掉前置门，bridge 自己按「配置文件 → PATH → 未配置错误」三档决定 |

新增 3 条回归测试（`test_dispatch_rejects_non_url_fallback_input_locally` / `test_dispatch_downloads_remote_document_url_before_conversion` / `test_dispatch_routes_social_urls_through_opencli_bridge`），41/41 通过。

---

## 第三期 P2 — 小红书虚拟产品分析模块（进行中）

**触发**：2026-04-22 会话。新增第4个专题"小红书虚拟产品"，核心是引入**商业洞察5维框架**作为整个知识库的底层分析逻辑。

**架构决策**：5维框架（产品形态/流量转化/赛道竞争/操盘手画像/机会洞察）适用于所有内容——商品链接、文章、精华帖均通过此框架分析。所有知识库成品页和视角提炼页统一使用5维章节结构。

### P2-A: 配置与 wiki 目录
- 目标：新增专题/资产形态/source_type，飞书 wiki 子目录上线
- 涉及文件：`~/.agents/skills/lark-knowledge-config/config.json`
- 变更：新增专题"小红书虚拟产品"、资产形态"商品调研"/"赛道分析"、source_type xhs_product/xhs_shop/xhs_profile
- wiki 节点：04_小红书虚拟产品（`S4kqwctcFiPIlQkHcbUcUjSGnpg`）/ 01_竞品案例（`T86Bw4KpciQFHikwUdncSTpXnv2`）/ 02_赛道分析（`IKTxwoR4HimnV9k3ZBCc4Xv1ned`）
- 状态：✅ 已完成（2026-04-22）

### P2-B: xhs_product Fetcher + dispatcher 扩展
- 目标：识别 xhslink 短链 + 调 playwright-stealth 抓商品/店铺/主页页面
- 涉及文件：`skills/lark-knowledge-intake/xhs_product.py`（新建）、`skills/lark-knowledge-intake/dispatcher.py`（新建顶层分发器）
- 状态：✅ 已完成（commit `9c218b2`）

### P2-C: Intake 5维分析框架（全库通用）
- 目标：所有内容 AI摘要 通过5维框架撰写，不限专题
- 涉及文件：`skills/lark-knowledge-intake/SKILL.md`
- 状态：✅ 已完成（2026-04-22）

### P2-D: Upgrade 5维章节结构（全库通用）
- 目标：所有资产形态成品页/视角提炼页统一使用5维章节结构，替换原有按资产形态分列的模板
- 涉及文件：`skills/lark-knowledge-upgrade/SKILL.md`
- 状态：✅ 已完成（2026-04-22）

### P2-E: 赛道分析自动汇总（未来）
- 目标：积累到一定数量的商品调研记录后，自动汇总生成赛道分析页
- 状态：⏸ 待规划（P3 考虑）

### P2-F: 端到端验收
- 目标：用3个测试链接跑完整流程（商品/店铺/主页各1个）
- 状态：⏸ 待 P2-B 完成后执行

---

## 第四期 P3 — All In Podcast 中文知识库产品

**触发**：2026-04-28 会话。基于现有 lark-knowledge 生产线，新建独立飞书知识库空间，把 All In Podcast（硅谷顶级 VC 播客，107 万订阅）翻译、分析、结构化，做成三层付费知识库产品在小红书售卖。

**三层产品**：
1. 手绘笔记（Sketchnote，免费引流）
2. 中英对照逐字稿 原稿版（基础付费）
3. 含五维分析注释的 注释版（高级付费）
两个付费版均配 Kami 可打印 PDF。

**方案文档**：`~/Obsidian/PersonalWiki/方案/all-in-podcast-知识库产品.md`

**飞书基础设施**：
- Base（节目收件表）：base_token `BUpGbPzJFaAp3ustfdIcr8penJe`，table_id `tblRL4DkyUhp5ieR`
- Wiki 空间：space_id `7405572495342665731`，根节点 `Wq2JwALP9ilYc4kdGB7c70uuntb`
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
- 状态：⏸ 待启动

### P3-C: All In 逐字稿生成（中英对照排版）
- 目标：从 YouTube 字幕拉取原文，AI 翻译为中文，按「中文段落 + EN: 英文原文」格式排版，写入飞书知识库页面
- 涉及文件：新建 `skills/lark-knowledge-allin-transcript/SKILL.md`
- 排版规则：天蓝色标题、灰色 EN: 前缀、light-blue callout 作注释（有实质洞察才写）
- 验收：1 期逐字稿完整写入飞书页面，格式符合方案文档规范
- 状态：⏸ 待 P3-B 完成后启动

### P3-D: All In 注释版生成（内联注释 + 五维分析章节）
- 目标：在逐字稿基础上，由 AI 添加内联注释 callout + 独立五维分析章节
- 涉及文件：`skills/lark-knowledge-allin-transcript/SKILL.md`（扩展注释逻辑）
- 注释标准：只在「数据/判断/公司名需要背景」处添加，不注水
- 验收：1 期注释版完整写入飞书页面，注释质量通过人工审查
- 状态：⏸ 待 P3-C 完成后启动

### P3-E: Kami PDF 排版模板
- 目标：用 Kami（HTML/CSS）生成可打印 PDF，主副式双语，霞鹜文楷，天蓝色 #4DABF7
- 涉及文件：新建 `templates/allin-kami/` 目录（HTML + CSS 模板）
- 验收：1 期 PDF 导出，双语对照排版，可在 Kami 中标注
- 状态：⏸ 待启动（可与 P3-C/D 并行）

### P3-F: 精选 Top20 自动维护
- 目标：每月由 AI 根据「播放量×0.4 + 五维评分×0.6」算法自动更新「精选必读」页面
- 涉及文件：`scripts/allin_top20_updater.py`（新建）
- 验收：脚本跑通，精选必读页面内容自动刷新
- 状态：⏸ 待 P3-B 积累足够数据后启动
