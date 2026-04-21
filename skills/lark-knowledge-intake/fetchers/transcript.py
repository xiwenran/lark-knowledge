from __future__ import annotations

import logging
import sys
import time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import requests


logger = logging.getLogger(__name__)

GETNOTE_API_ENDPOINT = "https://api.getnote.ai/v1/transcribe"
GETNOTE_TIMEOUT_SECONDS = 120
GETNOTE_RETRY_DELAY_SECONDS = 5
GETNOTE_SUPPORTED_DOMAINS = {
    "bilibili.com/video/": "video_bilibili",
    "xiaoyuzhoufm.com": "podcast",
    "ximalaya.com": "podcast",
    "youtube.com/watch": "video_youtube",
    "youtu.be/": "video_youtube",
}


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
    from .credentials import load_local_credential
    from .types import FetchResult
except ImportError:
    load_local_credential = _load_sibling_module("credentials").load_local_credential
    FetchResult = _load_sibling_module("types").FetchResult


def _detect_source_type(url: str) -> str | None:
    normalized = url.strip().lower()
    for domain_marker, source_type in GETNOTE_SUPPORTED_DOMAINS.items():
        if domain_marker in normalized:
            return source_type
    return None


def _format_timestamp(seconds: int | float | None) -> str:
    total_seconds = max(int(seconds or 0), 0)
    minutes, remainder = divmod(total_seconds, 60)
    return f"{minutes:02d}:{remainder:02d}"


def _build_markdown(title: str, transcript: str | None, segments: list[dict[str, object]]) -> str:
    lines: list[str] = [f"# {title}", ""]

    if segments:
        for segment in segments:
            timestamp = _format_timestamp(segment.get("start"))  # type: ignore[arg-type]
            text = str(segment.get("text") or "").strip()
            if text:
                lines.append(f"[{timestamp}] {text}")
    elif transcript:
        lines.append(transcript.strip())

    return "\n".join(lines).rstrip()


def _request_transcript(url: str, api_key: str) -> requests.Response:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "lark-knowledge-intake/1.0",
    }
    payload = {
        "url": url,
        "api_key": api_key,
    }

    for attempt in range(2):
        response = requests.post(
            GETNOTE_API_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=GETNOTE_TIMEOUT_SECONDS,
        )
        if response.status_code != 429 or attempt == 1:
            return response
        logger.warning("Getnote rate limited for %s, retrying once after %ss.", url, GETNOTE_RETRY_DELAY_SECONDS)
        time.sleep(GETNOTE_RETRY_DELAY_SECONDS)

    raise RuntimeError("unreachable")


def _extract_error_code(response: requests.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error_code = payload.get("error")
    return str(error_code) if error_code else None


def fetch(url: str) -> FetchResult:
    normalized = url.strip()
    source_type = _detect_source_type(normalized)

    api_key = load_local_credential("getnote_api_key")
    if not api_key:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type=source_type or "fetch_failed",
            url_or_path=normalized,
            success=False,
            error="Get 笔记 API key 未配置，请将 key 写入 .local/getnote_api_key",
        )

    if source_type is None:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type="fetch_failed",
            url_or_path=normalized,
            success=False,
            error="暂不支持该音视频链接，未命中 Get 笔记支持的平台白名单",
        )

    try:
        response = _request_transcript(normalized, api_key)
    except requests.Timeout:
        logger.warning("Getnote transcript request timed out for %s.", normalized)
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error="Get 笔记 API 请求超时（120s）",
        )
    except requests.RequestException as exc:
        logger.warning("Getnote transcript request failed for %s: %s", normalized, exc)
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error=f"Get 笔记 API 请求失败: {exc}",
        )

    error_code = _extract_error_code(response)
    if error_code == "unsupported_platform":
        logger.info("Getnote reported unsupported platform for %s.", normalized)
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type="fetch_failed",
            url_or_path=normalized,
            success=False,
            error="YouTube 暂不支持，需 yt-dlp + Whisper 自建转写",
        )

    if response.status_code == 401:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error="Get 笔记 API 认证失败，请检查 .local/getnote_api_key",
        )

    if response.status_code == 429:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error="Get 笔记 API 请求过于频繁，请稍后重试",
        )

    if 500 <= response.status_code <= 599:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error=f"Get 笔记 API 服务暂时不可用（HTTP {response.status_code}）",
        )

    if response.status_code != 200:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error=f"Get 笔记 API 返回异常状态码（HTTP {response.status_code}）",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning("Getnote transcript response JSON invalid for %s: %s", normalized, exc)
        return FetchResult(
            markdown=None,
            title=None,
            meta={"api_endpoint": GETNOTE_API_ENDPOINT},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error="Get 笔记 API 返回了无法解析的 JSON",
        )

    title = str(payload.get("title") or "Untitled Transcript").strip() or "Untitled Transcript"
    transcript = payload.get("transcript")
    transcript_text = str(transcript).strip() if transcript else None
    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    duration = payload.get("duration")

    return FetchResult(
        markdown=_build_markdown(title, transcript_text, segments),
        title=title,
        meta={
            "duration": duration,
            "segment_count": len(segments),
            "api_endpoint": GETNOTE_API_ENDPOINT,
            "segments": segments,
        },
        source_type=source_type,
        url_or_path=normalized,
        success=True,
        error=None,
    )
