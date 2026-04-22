from __future__ import annotations

import logging
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)


def _load_types_module():
    module_path = Path(__file__).resolve().with_name("types.py")
    spec = spec_from_file_location("lk_fetchers_types", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load types module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FetchResult = _load_types_module().FetchResult


def _load_module(module_name: str):
    module_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = spec_from_file_location(f"lk_fetchers_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_article_fetcher = _load_module("article")
_archive_fetcher = _load_module("archive")
_paywall_fetcher = _load_module("paywall")
_document_fetcher = _load_module("document")
_arxiv_fetcher = _load_module("arxiv")
_transcript_fetcher = _load_module("transcript")
_wechat_fetcher = _load_module("wechat")
_opencli_fetcher = _load_module("opencli_bridge")
PAYWALL_DOMAINS = _load_module("paywall_domains").PAYWALL_DOMAINS

SUPPORTED_SOURCE_TYPES = {
    "article",
    "paywall_news",
    "wechat_mp",
    "tweet",
    "zhihu",
    "xhs_note",
    "video_bilibili",
    "video_youtube",
    "podcast",
    "doc_pdf",
    "doc_docx",
    "doc_pptx",
    "doc_xlsx",
    "doc_epub",
    "arxiv",
    "image",
    "fallback",
    "fetch_failed",
}

FILE_EXTENSION_SOURCE_TYPES = {
    ".pdf": "doc_pdf",
    ".doc": "doc_docx",
    ".docx": "doc_docx",
    ".ppt": "doc_pptx",
    ".pptx": "doc_pptx",
    ".xls": "doc_xlsx",
    ".xlsx": "doc_xlsx",
    ".csv": "doc_xlsx",
    ".tsv": "doc_xlsx",
    ".epub": "doc_epub",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".svg": "image",
}

KNOWN_DOMAIN_SOURCE_TYPES = {
    "mp.weixin.qq.com": "wechat_mp",
    "twitter.com": "tweet",
    "www.twitter.com": "tweet",
    "x.com": "tweet",
    "www.x.com": "tweet",
    "zhihu.com": "zhihu",
    "www.zhihu.com": "zhihu",
    "xiaohongshu.com": "xhs_note",
    "www.xiaohongshu.com": "xhs_note",
    "bilibili.com": "video_bilibili",
    "www.bilibili.com": "video_bilibili",
    "youtube.com": "video_youtube",
    "www.youtube.com": "video_youtube",
    "youtu.be": "video_youtube",
    "arxiv.org": "arxiv",
    "www.arxiv.org": "arxiv",
    "xiaoyuzhoufm.com": "podcast",
    "www.xiaoyuzhoufm.com": "podcast",
    "ximalaya.com": "podcast",
    "www.ximalaya.com": "podcast",
}


def _normalize_input(url_or_path: str) -> str:
    return url_or_path.strip()


def _detect_from_extension(url_or_path: str) -> str | None:
    candidate = _normalize_input(url_or_path)
    suffix = Path(candidate).suffix.lower()
    return FILE_EXTENSION_SOURCE_TYPES.get(suffix)


def _extract_hostname(url_or_path: str) -> str:
    parsed = urlparse(_normalize_input(url_or_path))
    hostname = parsed.hostname or ""
    return hostname.lower()


def _extract_path(url_or_path: str) -> str:
    parsed = urlparse(_normalize_input(url_or_path))
    return (parsed.path or "").lower()


def _is_generic_web_url(url_or_path: str) -> bool:
    parsed = urlparse(_normalize_input(url_or_path))
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _is_http_url(url_or_path: str) -> bool:
    # 与 _is_generic_web_url 语义相同，独立命名是为了让 dispatch 层"是否为 URL"的判定读起来更显眼。
    return _is_generic_web_url(url_or_path)


REMOTE_DOCUMENT_TIMEOUT_SECONDS = 60
REMOTE_DOCUMENT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _download_remote_document(url: str, suffix: str) -> Path:
    # 远程文档只做最小可用的下载（followed redirects by urllib 默认支持），拿到本地临时文件再交给 markitdown。
    request = Request(url, headers={"User-Agent": REMOTE_DOCUMENT_USER_AGENT})
    fd, temp_path = tempfile.mkstemp(suffix=suffix or "")
    try:
        with urlopen(request, timeout=REMOTE_DOCUMENT_TIMEOUT_SECONDS) as response, open(fd, "wb") as out:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except Exception:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:  # pragma: no cover
            pass
        raise
    return Path(temp_path)


def _detect_from_domain(url_or_path: str) -> str | None:
    hostname = _extract_hostname(url_or_path)
    path = _extract_path(url_or_path)
    if not hostname:
        return None

    if hostname in PAYWALL_DOMAINS:
        return "paywall_news"

    source_type = KNOWN_DOMAIN_SOURCE_TYPES.get(hostname)
    if source_type == "video_bilibili" and "/video/" not in path:
        return None

    if source_type:
        return source_type

    return None


def detect_source_type(url_or_path: str) -> str:
    # 识别顺序固定：文件扩展名 > 已知域名 > fallback。
    normalized = _normalize_input(url_or_path)
    if not normalized:
        return "fallback"

    from_extension = _detect_from_extension(normalized)
    if from_extension:
        return from_extension

    from_domain = _detect_from_domain(normalized)
    if from_domain:
        return from_domain

    if _is_generic_web_url(normalized):
        return "article"

    return "fallback"


def dispatch(url_or_path: str) -> FetchResult:
    normalized = _normalize_input(url_or_path)
    source_type = detect_source_type(normalized)
    logger.info("Dispatch routed %s to source_type=%s", normalized, source_type)

    if source_type == "article":
        primary = _article_fetcher.fetch(normalized)
        if primary.success:
            return primary
        logger.warning("Dispatch fallback: article fetch failed for %s, trying archive.", normalized)
        archive = _archive_fetcher.fetch(normalized)
        if archive.success:
            archive.meta = {**archive.meta, "fallback_from": "article"}
            archive.source_type = "article"
            return archive
        return FetchResult(
            markdown=None,
            title=None,
            meta={"routed": True, "fetcher_active": True, "fallback_chain": ["article", "archive"]},
            source_type="fetch_failed",
            url_or_path=normalized,
            success=False,
            error=" | ".join(filter(None, [primary.error, archive.error])),
        )

    if source_type == "paywall_news":
        primary = _paywall_fetcher.fetch(normalized)
        if primary.success:
            return primary
        logger.warning("Dispatch fallback: paywall fetch failed for %s, trying archive.", normalized)
        archive = _archive_fetcher.fetch(normalized)
        if archive.success:
            archive.meta = {**archive.meta, "fallback_from": "paywall_news"}
            archive.source_type = "paywall_news"
            return archive
        return FetchResult(
            markdown=None,
            title=None,
            meta={"routed": True, "fetcher_active": True, "fallback_chain": ["paywall_news", "archive"]},
            source_type="fetch_failed",
            url_or_path=normalized,
            success=False,
            error=" | ".join(filter(None, [primary.error, archive.error])),
        )

    if source_type == "fallback":
        # 修复：fallback 分支只对 http/https URL 走外网抓取，避免非 URL 的自由文本被外发到 r.jina.ai / archive.today。
        if not _is_http_url(normalized):
            return FetchResult(
                markdown=None,
                title=None,
                meta={"routed": True, "fetcher_active": False, "reason": "not_an_http_url"},
                source_type="fallback",
                url_or_path=normalized,
                success=False,
                error="输入既不是可识别的 URL，也不是本地文件路径；无法分发抓取",
            )
        primary = _article_fetcher.fetch(normalized)
        if primary.success:
            primary.source_type = "fallback"
            primary.meta = {**primary.meta, "fallback_chain": ["article"]}
            return primary
        logger.warning("Dispatch fallback: generic fetch failed for %s, trying archive.", normalized)
        archive = _archive_fetcher.fetch(normalized)
        if archive.success:
            archive.meta = {**archive.meta, "fallback_from": "fallback"}
            archive.source_type = "fallback"
            return archive
        return FetchResult(
            markdown=None,
            title=None,
            meta={"routed": True, "fetcher_active": True, "fallback_chain": ["article", "archive"]},
            source_type="fetch_failed",
            url_or_path=normalized,
            success=False,
            error=" | ".join(filter(None, [primary.error, archive.error])),
        )

    if source_type in {"doc_pdf", "doc_docx", "doc_pptx", "doc_xlsx", "doc_epub"}:
        # 修复：本地路径直接交给 markitdown；远程 URL 先下载到临时文件，再调 document.fetch，最后清理。
        if _is_http_url(normalized):
            suffix = Path(urlparse(normalized).path).suffix.lower()
            temp_path: Path | None = None
            try:
                temp_path = _download_remote_document(normalized, suffix)
                result = _document_fetcher.fetch(str(temp_path))
                # 保留用户可识别的原始 URL，而不是临时路径。
                result.url_or_path = normalized
                existing_meta = result.meta if isinstance(result.meta, dict) else {}
                result.meta = {
                    **existing_meta,
                    "remote_source_url": normalized,
                    "downloaded_to": str(temp_path),
                }
                return result
            except Exception as exc:
                logger.warning("Dispatch failed to download remote document %s: %s", normalized, exc)
                return FetchResult(
                    markdown=None,
                    title=None,
                    meta={"routed": True, "fetcher_active": True, "remote_source_url": normalized},
                    source_type="fetch_failed",
                    url_or_path=normalized,
                    success=False,
                    error=f"远程文档下载失败: {exc}",
                )
            finally:
                if temp_path is not None:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except Exception:  # pragma: no cover
                        pass
        return _document_fetcher.fetch(normalized)

    if source_type == "arxiv":
        return _arxiv_fetcher.fetch(normalized)

    if source_type == "wechat_mp":
        return _wechat_fetcher.fetch(normalized)

    if source_type in {"tweet", "zhihu", "xhs_note"}:
        # 修复：dispatcher 不再用 OPENCLI_CONFIG_PATH.is_file() 做前置门；让 bridge 自己决定
        # "读配置文件 / 从 PATH 发现 / 给出未配置错误"，保持与 opencli_bridge 文档一致。
        return _opencli_fetcher.fetch(normalized)

    if source_type in {"video_bilibili", "video_youtube", "podcast"}:
        return _transcript_fetcher.fetch(normalized)

    error_message = f"No active fetcher for source_type={source_type}."
    logger.info("Dispatch has no active fetcher for %s (%s).", normalized, source_type)
    return FetchResult(
        markdown=None,
        title=None,
        meta={"routed": True, "fetcher_active": False},
        source_type=source_type,
        url_or_path=normalized,
        success=False,
        error=error_message,
    )
