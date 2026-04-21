from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from urllib.parse import urlparse


logger = logging.getLogger(__name__)

OPENCLI_TIMEOUT_SECONDS = 90
# 统一走 .local 目录定位，避免 .claude/.agents/repo 三处硬编码不一致（三者 symlink 等价）。
OPENCLI_CONFIG_PATH = Path(__file__).resolve().parent.parent / ".local" / "opencli_config" / "opencli_path"
OPENCLI_AUTH_ERROR_HINTS = ("auth", "login", "session")


def _load_sibling_module(module_name: str) -> ModuleType:
    module_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = spec_from_file_location(f"lk_fetchers_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    from .types import FetchResult
except ImportError:
    FetchResult = _load_sibling_module("types").FetchResult


def _detect_source_type(url: str) -> str:
    hostname = (urlparse(url.strip()).hostname or "").lower()
    if hostname in {"twitter.com", "www.twitter.com", "x.com", "www.x.com"}:
        return "tweet"
    if hostname in {"zhihu.com", "www.zhihu.com"}:
        return "zhihu"
    if hostname in {"xiaohongshu.com", "www.xiaohongshu.com"}:
        return "xhs_note"
    return "fetch_failed"


def _resolve_opencli_path() -> str | None:
    # 优先读本地配置文件，便于未来切换到用户自装 CLI。
    try:
        configured = OPENCLI_CONFIG_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        configured = ""

    if configured:
        logger.debug("Using configured OpenCLI path: %s", configured)
        return configured

    discovered = shutil.which("opencli")
    if discovered:
        logger.debug("Using OpenCLI from PATH: %s", discovered)
        return discovered

    logger.warning("OpenCLI path is not configured.")
    return None


def _build_markdown(title: str, content: str, media_urls: list[str]) -> str:
    lines = [f"# {title}", ""]
    if content.strip():
        lines.append(content.strip())

    if media_urls:
        lines.extend(["", "## 媒体链接", ""])
        lines.extend(f"- {media_url}" for media_url in media_urls)

    return "\n".join(lines).rstrip()


def _extract_error_message(stderr: str) -> str:
    normalized = stderr.strip()
    lowered = normalized.lower()
    if any(hint in lowered for hint in OPENCLI_AUTH_ERROR_HINTS):
        return "OpenCLI 登录态失效，请在浏览器重新登录对应平台"
    return normalized[:500] or "OpenCLI 执行失败"


def fetch(url: str) -> FetchResult:
    normalized = url.strip()
    source_type = _detect_source_type(normalized)
    cli_path = _resolve_opencli_path()
    if not cli_path:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"cli_path": None},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error="OpenCLI 未配置，请参考 README 安装",
        )

    try:
        # 当前阶段只封装稳定 CLI 契约，不触碰真实浏览器环境。
        completed = subprocess.run(
            [cli_path, "fetch", "--url", normalized, "--format", "json"],
            timeout=OPENCLI_TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        logger.warning("OpenCLI fetch timed out for %s.", normalized)
        return FetchResult(
            markdown=None,
            title=None,
            meta={"cli_path": cli_path},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error="OpenCLI 抓取超时（90s）",
        )

    if completed.returncode != 0:
        logger.warning("OpenCLI fetch failed for %s: %s", normalized, completed.stderr.strip())
        return FetchResult(
            markdown=None,
            title=None,
            meta={"cli_path": cli_path},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error=_extract_error_message(completed.stderr),
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        logger.warning("OpenCLI returned invalid JSON for %s: %s", normalized, exc)
        return FetchResult(
            markdown=None,
            title=None,
            meta={"cli_path": cli_path},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error="OpenCLI 返回了无法解析的 JSON",
        )

    title = str(payload.get("title") or "Untitled").strip() or "Untitled"
    content = str(payload.get("content") or "").strip()
    media_urls = payload.get("media_urls") if isinstance(payload.get("media_urls"), list) else []
    normalized_media_urls = [str(media_url).strip() for media_url in media_urls if str(media_url).strip()]
    author = str(payload.get("author") or "").strip() or None
    platform = str(payload.get("platform") or "").strip() or None

    logger.info("OpenCLI fetch succeeded for %s (platform=%s).", normalized, platform or source_type)
    return FetchResult(
        markdown=_build_markdown(title, content, normalized_media_urls),
        title=title,
        meta={
            "author": author,
            "platform": platform,
            "media_urls": normalized_media_urls,
            "cli_path": cli_path,
        },
        source_type=source_type,
        url_or_path=normalized,
        success=True,
        error=None,
    )
