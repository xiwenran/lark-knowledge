# Fetchers Submodule

`fetchers/` 是 `lark-knowledge-intake` 的内部多源抓取器路由层，负责统一识别来源类型、抓正文、做降级，并返回稳定的 `FetchResult` 契约。

## Scope

- `dispatcher.py`
  - 负责按输入自动识别 `source_type`
  - 负责把输入路由到后续 fetcher，并在失败时级联降级
- `article.py`
  - 优先走 `https://r.jina.ai/<url>` 抓取公开网页
  - 失败后退到直连网页 + `trafilatura` / `beautifulsoup4` 本地解析
- `paywall.py`
  - 使用 Googlebot UA、`X-Forwarded-For`、`Referer` 伪装抓付费墙新闻
- `archive.py`
  - 作为无状态网页的最终降级层，尝试 `archive.today` 和 Google Cache
- `document.py`
  - 负责本地 `.pdf` / `.docx` / `.pptx` / `.xlsx` / `.epub` 文件转 markdown
  - 统一调用 Microsoft `markitdown`
  - 所有异常都收敛为 `FetchResult(success=False)`
- `arxiv.py`
  - 负责 `arxiv.org/abs/...` / `arxiv.org/pdf/...` 链接
  - 优先下载 PDF 到临时目录后复用 `document.fetch()`
  - 下载失败时降级到 `r.jina.ai` 抓 abstract 页面
- `transcript.py`
  - 负责 `video_bilibili` / `video_youtube` / `podcast` 的音视频转写骨架
  - 通过 `credentials.load_local_credential("getnote_api_key")` 读取 `~/.claude/skills/lark-knowledge-intake/.local/getnote_api_key`
  - 调用占位的 Get 笔记 API `https://api.getnote.ai/v1/transcribe`
  - 当前阶段只交付骨架 + mock 测试；真实 API key 与联调验收留待后续会话
- `wechat.py`
  - 负责 `wechat_mp` 的微信公众号正文抓取骨架
  - 使用 Playwright `storage_state` 复用微信登录态，cookie 固定落在 `~/.claude/skills/lark-knowledge-intake/.local/wechat_cookie.json`
  - 优先提取 `#js_content`，使用 `markdownify` 转 markdown，失败时降级简易 html2text
  - 当前阶段只交付骨架 + mock 测试，真实抓取验收待后续扫码联调
- `opencli_bridge.py`
  - 负责 `tweet` / `zhihu` / `xhs_note` 的登录态社交平台抓取骨架
  - 优先从 `~/.claude/skills/lark-knowledge-intake/.local/opencli_config/opencli_path` 读取 OpenCLI 绝对路径，读不到再退 `PATH`
  - 通过 `opencli fetch --url <url> --format json` 取回标准 JSON，并统一转成 markdown
  - 当前阶段只交付骨架 + mock 测试，真实凭据 / 扩展验收待后续会话
- `paywall_domains.py`
  - 维护常见付费墙新闻域名列表
- `types.py`
  - 定义统一 `FetchResult` 契约
- `credentials.py`
  - 负责读取本地凭据 / cookie / token

## Source Detection Order

1. 文件扩展名
2. 已知域名
3. `fallback`

## Fetch Cascade

- `source_type=article`
  - `article.fetch()` 失败后自动降级到 `archive.fetch()`
- `source_type=paywall_news`
  - `paywall.fetch()` 失败后自动降级到 `archive.fetch()`
- `source_type=fallback`
  - 先按通用文章走 `article.fetch()`，失败后再走 `archive.fetch()`
- `source_type=doc_pdf` / `doc_docx` / `doc_pptx` / `doc_xlsx` / `doc_epub`
  - 直接走 `document.fetch()`
- `source_type=arxiv`
  - 先下载 PDF 并走 `document.fetch()`，失败再降级到 `r.jina.ai`
- `source_type=wechat_mp`
  - 直接走 `wechat.fetch()`
  - 未完成首次扫码时稳定返回登录指引，不抛未捕获异常
- `source_type=tweet` / `zhihu` / `xhs_note`
  - 配置 OpenCLI CLI 路径后直接走 `opencli_bridge.fetch()`
  - 登录态失效时稳定返回重新登录提示
- `source_type=video_bilibili` / `video_youtube` / `podcast`
  - 直接走 `transcript.fetch()`
  - `429` 仅重试一次，间隔 `5s`
  - YouTube 若返回 `unsupported_platform`，收敛为 `FetchResult(success=False, source_type='fetch_failed')`
- 全部失败
  - 返回 `FetchResult(success=False, source_type='fetch_failed')`
  - 原始链接保留在 `url_or_path`

## FetchResult Contract

所有 fetcher 必须返回同一结构：

```python
{
    "markdown": str | None,
    "title": str | None,
    "meta": dict,
    "source_type": str,
    "url_or_path": str,
    "success": bool,
    "error": str | None,
}
```

## Dependencies

建议本机安装：

```bash
pip install requests beautifulsoup4 trafilatura markdownify playwright 'markitdown[all]'
```

- `requests`
  - 同步 HTTP 请求，默认 `30s timeout`，最多 `2` 次重试
- `beautifulsoup4`
  - 基础 HTML 解析
- `trafilatura`
  - 可选，更适合正文抽取；缺失时自动退回 `beautifulsoup4`
- `markitdown[all]`
  - 文档类抓取统一依赖，覆盖 PDF / DOCX / PPTX / XLSX / EPUB
  - `document.py` 未检测到该依赖时会返回失败态 `FetchResult`，不会抛出未捕获异常
- `markdownify`
  - 微信公众号 HTML 转 markdown 首选依赖
- `playwright`
  - 微信公众号登录态抓取依赖；首次使用需执行 `python -m fetchers.wechat --login`

## Local Credentials

本地凭据统一放在：

`~/.claude/skills/lark-knowledge-intake/.local/`

由于当前 skill 目录通过 symlink 指向仓库，这个目录会实际落到仓库对应路径下的 `skills/lark-knowledge-intake/.local/`。该目录只用于本机私有 cookie、token、会话文件，必须被 `.gitignore` 排除，禁止入仓。

`credentials.py` 提供：

```python
load_local_credential(name: str) -> str | None
```

当文件不存在时返回 `None`，不抛异常。

当前阶段 `article` / `paywall` / `document` 默认不依赖本地凭据，但代码路径已统一预留在 `credentials.load_local_credential(...)`，后续如需接 cookie / token，只能从这里接入。

## P11.4 WeChat Skeleton

- 微信公众号抓取骨架已落，真实抓取验收待后续（需扫码）。
- cookie 文件固定为 `~/.claude/skills/lark-knowledge-intake/.local/wechat_cookie.json`，禁止入仓。
- 首次使用执行 `python -m fetchers.wechat --login`，扫码成功后会持久化 Playwright `storage_state`。
- 本会话验收范围仅包含代码骨架与 mock 测试，不包含真实扫码与真实文章联调。

## P11.5 Transcript Skeleton

- 白名单平台：
  - `bilibili.com/video/` → `video_bilibili`
  - `xiaoyuzhoufm.com` / `ximalaya.com` → `podcast`
  - `youtube.com/watch` / `youtu.be/` → `video_youtube`
- 成功响应假定为 `{title, transcript, segments, duration}`，会转成：
  - `# title`
  - 正文逐行 `[mm:ss] text`
- `meta` 至少包含：
  - `duration`
  - `segment_count`
  - `api_endpoint`
- 当前实现不要求真实 key；没有 key 时会稳定返回：
  - `FetchResult(success=False, error="Get 笔记 API key 未配置，请将 key 写入 .local/getnote_api_key")`

## P11.6 OpenCLI Skeleton

- OpenCLI 骨架已落，首次真实使用需：
  1. 装 Chrome Browser Bridge 扩展
  2. 装 Node.js CLI
  3. 在 `.local/opencli_config/opencli_path` 写入 CLI 绝对路径
- 当前 `fetch(url)` 会调用：
  - `opencli fetch --url "<url>" --format json`
- 约定成功 JSON 结构：
  - `{title, content, media_urls, author, platform}`
- stderr 命中 `auth` / `login` / `session` 会收敛为登录态失效提示。
- 本会话验收范围仅包含代码骨架与 mock 测试，不包含 Browser Bridge、Node.js CLI 与真实平台联调。
