> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

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
