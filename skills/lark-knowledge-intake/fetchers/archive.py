from __future__ import annotations

import logging
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from urllib.parse import quote

import requests


logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2


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
_article_module = _load_module("article")
_extract_from_html = _article_module._extract_from_html


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
            logger.warning("Archive request failed for %s on attempt %s/%s: %s", url, attempt + 1, MAX_RETRIES + 1, exc)

    assert last_error is not None
    raise last_error


def _build_archive_today_url(url: str) -> str:
    return f"https://archive.today/newest/{url}"


def _build_google_cache_url(url: str) -> str:
    return f"https://webcache.googleusercontent.com/search?q=cache:{quote(url, safe='')}"


def fetch(url_or_path: str) -> FetchResult:
    normalized = url_or_path.strip()
    session = requests.Session()
    errors: list[str] = []

    backends = [
        ("archive.today", _build_archive_today_url(normalized)),
        ("google cache", _build_google_cache_url(normalized)),
    ]

    for backend_name, backend_url in backends:
        try:
            logger.info("Archive fetch: trying %s for %s", backend_name, normalized)
            response = _request_with_retries(session, backend_url)
            title, markdown, parser_name = _extract_from_html(response.text)
            if markdown:
                return FetchResult(
                    markdown=markdown,
                    title=title,
                    meta={"backend": backend_name, "parser": parser_name},
                    source_type="article",
                    url_or_path=normalized,
                    success=True,
                    error=None,
                )
            errors.append(f"{backend_name} returned no extractable content")
            logger.warning("Archive fetch: %s returned no extractable content for %s", backend_name, normalized)
        except requests.RequestException as exc:
            errors.append(f"{backend_name}: {exc}")
            logger.warning("Archive fetch: %s failed for %s: %s", backend_name, normalized, exc)

    error_message = f"Archive fetch failed for {normalized}. Tried archive.today and google cache. Details: {'; '.join(errors)}"
    logger.error(error_message)
    return FetchResult(
        markdown=None,
        title=None,
        meta={"attempted_backends": ["archive.today", "google cache"]},
        source_type="fetch_failed",
        url_or_path=normalized,
        success=False,
        error=error_message,
    )
