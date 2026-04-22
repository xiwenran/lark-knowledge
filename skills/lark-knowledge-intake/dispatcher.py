from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import sys


CONFIG_PATH = Path.home() / ".agents" / "skills" / "lark-knowledge-config" / "config.json"
FETCHERS_DIR = Path(__file__).resolve().parent / "fetchers"

_GENERIC_SOURCE_CHANNEL_BY_TYPE = {
    "article": "网页",
    "paywall_news": "网页",
    "wechat_mp": "公众号",
    "tweet": "网页",
    "zhihu": "网页",
    "xhs_note": "网页",
    "video_bilibili": "网页",
    "video_youtube": "网页",
    "podcast": "网页",
    "doc_pdf": "PDF",
    "doc_docx": "其他",
    "doc_pptx": "其他",
    "doc_xlsx": "其他",
    "doc_epub": "其他",
    "arxiv": "网页",
    "image": "其他",
    "fallback": "其他",
    "fetch_failed": "其他",
}

_FETCHABLE_SOURCE_TYPES = {
    "article",
    "paywall_news",
    "wechat_mp",
    "tweet",
    "zhihu",
    "xhs_note",
    "xhs_product",
    "xhs_shop",
    "xhs_profile",
    "video_bilibili",
    "video_youtube",
    "podcast",
    "doc_pdf",
    "doc_docx",
    "doc_pptx",
    "doc_xlsx",
    "doc_epub",
    "arxiv",
}


def _load_module(name: str, module_path: Path):
    spec = spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_xhs_product = _load_module("lk_intake_xhs_product", Path(__file__).resolve().with_name("xhs_product.py"))
_fetchers_dispatcher = _load_module("lk_intake_fetchers_dispatcher", FETCHERS_DIR / "dispatcher.py")


@dataclass(slots=True)
class IntakeDispatchResult:
    source_type: str
    source_channel: str
    handler: str
    raw_input: str
    normalized_input: str
    fetcher_source_type: str | None
    should_fetch: bool
    record_defaults: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    fetch_result: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "source_type": self.source_type,
            "来源渠道": self.source_channel,
            "handler": self.handler,
            "raw_input": self.raw_input,
            "normalized_input": self.normalized_input,
            "fetcher_source_type": self.fetcher_source_type,
            "should_fetch": self.should_fetch,
            "record_defaults": self.record_defaults,
            "meta": self.meta,
        }
        if self.fetch_result is not None:
            payload["fetch_result"] = {
                "markdown": getattr(self.fetch_result, "markdown", None),
                "title": getattr(self.fetch_result, "title", None),
                "meta": getattr(self.fetch_result, "meta", None),
                "source_type": getattr(self.fetch_result, "source_type", None),
                "url_or_path": getattr(self.fetch_result, "url_or_path", None),
                "success": getattr(self.fetch_result, "success", None),
                "error": getattr(self.fetch_result, "error", None),
            }
        return payload


def _load_config() -> dict[str, Any]:
    try:
        import json

        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except ValueError:
        return {}


def _normalize_input(raw_input: str) -> str:
    return raw_input.strip()


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _looks_like_local_file(value: str) -> bool:
    if not value:
        return False
    if value.startswith("~") or value.startswith("/"):
        return True
    return bool(Path(value).suffix)


def _get_field_options(config: dict[str, Any], field_key: str) -> list[str]:
    fields = config.get("fields") if isinstance(config.get("fields"), dict) else {}
    options = fields.get(field_key)
    if isinstance(options, list):
        return [str(item) for item in options]
    return []


def _pick_option(config: dict[str, Any], field_key: str, preferred: str | None, fallback: str | None = None) -> str | None:
    options = _get_field_options(config, field_key)
    if preferred and preferred in options:
        return preferred
    if fallback and fallback in options:
        return fallback
    return preferred or fallback


def _resolve_directory_index(config: dict[str, Any], topic: str | None, bucket: str | None) -> dict[str, str] | None:
    if not topic or not bucket:
        return None

    wiki = config.get("wiki") if isinstance(config.get("wiki"), dict) else {}
    directories = wiki.get("directories") if isinstance(wiki.get("directories"), dict) else {}
    topic_dirs = directories.get(topic)
    if not isinstance(topic_dirs, dict):
        return None

    root = topic_dirs.get("root")
    bucket_token = topic_dirs.get(bucket)
    if not root or not bucket_token:
        return None

    return {
        "专题": topic,
        "目录": bucket,
        "root_token": str(root),
        "bucket_token": str(bucket_token),
    }


def _default_source_channel(config: dict[str, Any], source_type: str, preferred: str | None = None) -> str:
    fallback = _GENERIC_SOURCE_CHANNEL_BY_TYPE.get(source_type, "其他")
    return _pick_option(config, "来源渠道_options", preferred or fallback, fallback="其他") or "其他"


def _default_record_defaults(
    config: dict[str, Any],
    normalized_input: str,
    source_type: str,
    *,
    source_channel: str,
    topic_hint: str | None = None,
    asset_shape_hint: str | None = None,
    directory_topic: str | None = None,
    directory_bucket: str | None = None,
) -> dict[str, Any]:
    original_link = normalized_input if _is_http_url(normalized_input) else ""
    note = normalized_input if _looks_like_local_file(normalized_input) and not original_link else ""
    topic_value = _pick_option(config, "专题归属_options", topic_hint)
    asset_value = _pick_option(config, "资产形态_options", asset_shape_hint)

    return {
        "收录时间": date.today().isoformat(),
        "来源渠道": source_channel,
        "原始链接": original_link,
        "备注": note,
        "专题归属": topic_value,
        "资产形态": asset_value,
        "处理状态": _pick_option(config, "处理状态_options", "待判断", fallback="待判断"),
        "关联目录索引": _resolve_directory_index(config, directory_topic or topic_value, directory_bucket),
    }


def detect_source_type(raw_input: str) -> str:
    normalized = _normalize_input(raw_input)
    xhs_route = _xhs_product.dispatch(normalized)
    if xhs_route is not None:
        return xhs_route.source_type
    return _fetchers_dispatcher.detect_source_type(normalized)


def dispatch(raw_input: str, *, fetch_content: bool = False) -> IntakeDispatchResult:
    normalized = _normalize_input(raw_input)
    config = _load_config()
    xhs_route = _xhs_product.dispatch(normalized)

    if xhs_route is not None:
        source_channel = _default_source_channel(config, xhs_route.source_type, preferred=xhs_route.source_channel)
        record_defaults = _default_record_defaults(
            config,
            normalized,
            xhs_route.source_type,
            source_channel=source_channel,
            topic_hint=xhs_route.topic_hint,
            asset_shape_hint=xhs_route.asset_shape_hint,
            directory_topic=xhs_route.directory_topic,
            directory_bucket=xhs_route.directory_bucket,
        )
        fetch_result = _fetchers_dispatcher.dispatch(normalized) if fetch_content else None
        return IntakeDispatchResult(
            source_type=xhs_route.source_type,
            source_channel=source_channel,
            handler="xhs_product",
            raw_input=raw_input,
            normalized_input=xhs_route.normalized_url,
            fetcher_source_type="xhs_note",
            should_fetch=True,
            record_defaults=record_defaults,
            meta={
                **xhs_route.meta,
                "processor": xhs_route.processor,
                "config_path": str(CONFIG_PATH),
                "route_family": "xiaohongshu_commerce",
            },
            fetch_result=fetch_result,
        )

    fetcher_source_type = _fetchers_dispatcher.detect_source_type(normalized)
    source_channel = _default_source_channel(config, fetcher_source_type)
    record_defaults = _default_record_defaults(
        config,
        normalized,
        fetcher_source_type,
        source_channel=source_channel,
    )
    should_fetch = fetcher_source_type in _FETCHABLE_SOURCE_TYPES or (
        fetcher_source_type == "fallback" and _is_http_url(normalized)
    )
    fetch_result = _fetchers_dispatcher.dispatch(normalized) if fetch_content and should_fetch else None

    return IntakeDispatchResult(
        source_type=fetcher_source_type,
        source_channel=source_channel,
        handler="generic",
        raw_input=raw_input,
        normalized_input=normalized,
        fetcher_source_type=fetcher_source_type,
        should_fetch=should_fetch,
        record_defaults=record_defaults,
        meta={
            "config_path": str(CONFIG_PATH),
            "route_family": "generic",
        },
        fetch_result=fetch_result,
    )


def dispatch_and_fetch(raw_input: str) -> IntakeDispatchResult:
    return dispatch(raw_input, fetch_content=True)
