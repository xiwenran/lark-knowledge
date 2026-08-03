> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

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

### P11.6 · 登录态社交平台（OpenCLI 适配器，不含小红书）
- **目标**：推特 / 知乎偶发归档能拿到正文；小红书不得走登录态抓取
- **涉及文件**：
  - `fetchers/opencli_bridge.py`（OpenCLI CLI 调用封装）
  - SKILL.md：Browser Bridge 扩展安装引导段
  - `~/.claude/skills/lark-knowledge-intake/.local/opencli_config/`
- **小红书禁令**：
  - 禁止把 OpenCLI Browser Bridge、MediaCrawler cookie/qrcode、redbook/xhs-cli/xiaohongshu-cli/XHS-Downloader 等登录态/cookie 方案用于小红书 intake。
  - 小红书仅允许走公开分享页、公开 H5 API、无登录 Playwright/Jina、用户手动提供文本/截图/OCR 等路径。
  - 账号主页、笔记列表、置顶内容、爆款笔记若无法通过公开 URL 直接取得，必须标记为信息不足，不得要求用户登录或读取本机浏览器 cookie。
- **验收**：
  - Browser Bridge 扩展首次引导装完
  - 推特单条 + 推特线程各测 1 条入库
  - 知乎回答 + 知乎盐选各测 1 条入库
  - 登录态失效有明确提示
- **派发模式**：🅱️ 施工模式（外部 Node.js 运行时 + 浏览器扩展，风险点多）
- **状态**：✅ 已完成（骨架，commit `47e249c`，2026-04-21；Browser Bridge 扩展 + OpenCLI CLI 真调用验收待后续会话）
