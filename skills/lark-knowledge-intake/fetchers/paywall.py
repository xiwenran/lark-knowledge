from __future__ import annotations

import logging
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import requests


logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2
GOOGLEBOT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "X-Forwarded-For": "66.249.66.1",
    "Referer": "https://www.google.com/",
}


def _load_module(module_name: str):
    module_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = spec_from_file_location(f"lk_fetchers_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FetchResult = _load_module("types").FetchResult
load_local_credential = _load_module("credentials").load_local_credential
_article_module = _load_module("article")
_extract_from_html = _article_module._extract_from_html
_extract_from_jina_text = _article_module._extract_from_jina_text


def _request_with_retries(
    session: requests.Session,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
            logger.warning("Paywall request failed for %s on attempt %s/%s: %s", url, attempt + 1, MAX_RETRIES + 1, exc)

    assert last_error is not None
    raise last_error


def _reserved_credential_meta() -> dict[str, Any]:
    placeholder = load_local_credential("paywall-cookie.txt")
    if placeholder:
        logger.info("Loaded reserved local paywall credential placeholder.")
    return {"credential_path_reserved": True, "credential_present": bool(placeholder)}


def fetch(url_or_path: str) -> FetchResult:
    normalized = url_or_path.strip()
    session = requests.Session()
    meta: dict[str, Any] = {"strategy": "paywall_news", **_reserved_credential_meta()}

    jina_url = f"https://r.jina.ai/{normalized}"
    try:
        logger.info("Paywall fetch: trying r.jina.ai with Googlebot headers for %s", normalized)
        response = _request_with_retries(session, jina_url, headers=GOOGLEBOT_HEADERS)
        title, markdown = _extract_from_jina_text(response.text)
        if markdown:
            meta.update({"backend": "r.jina.ai", "headers_profile": "googlebot"})
            return FetchResult(
                markdown=markdown,
                title=title,
                meta=meta,
                source_type="paywall_news",
                url_or_path=normalized,
                success=True,
                error=None,
            )
    except requests.RequestException as exc:
        logger.warning("Paywall fetch: r.jina.ai failed for %s: %s", normalized, exc)
        meta["jina_error"] = str(exc)

    try:
        logger.info("Paywall fetch: trying direct HTML parse with Googlebot headers for %s", normalized)
        response = _request_with_retries(session, normalized, headers=GOOGLEBOT_HEADERS)
        title, markdown, parser_name = _extract_from_html(response.text)
        if markdown:
            meta.update({"backend": "direct_html", "parser": parser_name, "headers_profile": "googlebot"})
            return FetchResult(
                markdown=markdown,
                title=title,
                meta=meta,
                source_type="paywall_news",
                url_or_path=normalized,
                success=True,
                error=None,
            )
        error_message = f"Unable to extract paywall article body from {normalized}."
    except requests.RequestException as exc:
        error_message = f"Paywall fetch failed for {normalized}: {exc}"
        logger.error(error_message)
        meta["direct_error"] = str(exc)
    else:
        logger.error(error_message)

    return FetchResult(
        markdown=None,
        title=None,
        meta=meta,
        source_type="paywall_news",
        url_or_path=normalized,
        success=False,
        error=error_message,
    )
