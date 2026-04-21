from __future__ import annotations

import logging
import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2

try:
    import trafilatura  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    trafilatura = None


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
            logger.warning("Request failed for %s on attempt %s/%s: %s", url, attempt + 1, MAX_RETRIES + 1, exc)

    assert last_error is not None
    raise last_error


def _reserved_credential_meta() -> dict[str, Any]:
    placeholder = load_local_credential("fetcher-placeholder.txt")
    if placeholder:
        logger.info("Loaded reserved local credential placeholder for article fetcher.")
    return {"credential_path_reserved": True, "credential_present": bool(placeholder)}


def _normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    collapsed = re.sub(r"\s+", " ", title).strip()
    return collapsed or None


def _extract_title_from_markdown(markdown: str) -> str | None:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", markdown)
    return _normalize_title(match.group(1)) if match else None


def _extract_from_jina_text(text: str) -> tuple[str | None, str | None]:
    title_match = re.search(r"(?m)^Title:\s*(.+?)\s*$", text)
    markdown_match = re.search(r"Markdown Content:\s*(.*)$", text, re.DOTALL)
    markdown = markdown_match.group(1).strip() if markdown_match else text.strip()
    title = _normalize_title(title_match.group(1)) if title_match else _extract_title_from_markdown(markdown)
    return title, markdown or None


def _html_to_basic_markdown(soup: BeautifulSoup) -> str | None:
    root = soup.find("article") or soup.find("main") or soup.body
    if root is None:
        return None

    blocks: list[str] = []
    for node in root.find_all(["h1", "h2", "h3", "p", "li"]):
        text = " ".join(node.stripped_strings)
        if not text:
            continue
        if node.name == "h1":
            blocks.append(f"# {text}")
        elif node.name == "h2":
            blocks.append(f"## {text}")
        elif node.name == "h3":
            blocks.append(f"### {text}")
        elif node.name == "li":
            blocks.append(f"- {text}")
        else:
            blocks.append(text)

    markdown = "\n\n".join(blocks).strip()
    return markdown or None


def _extract_from_html(html: str) -> tuple[str | None, str | None, str]:
    if trafilatura is not None:
        markdown = trafilatura.extract(
            html,
            output_format="markdown",
            include_formatting=True,
            include_links=True,
        )
        if markdown:
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.find("h1")
            title = _normalize_title(h1.get_text(" ", strip=True) if h1 else soup.title.get_text(" ", strip=True) if soup.title else None)
            return title or _extract_title_from_markdown(markdown), markdown.strip(), "trafilatura"

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = _normalize_title(h1.get_text(" ", strip=True) if h1 else soup.title.get_text(" ", strip=True) if soup.title else None)
    markdown = _html_to_basic_markdown(soup)
    return title or _extract_title_from_markdown(markdown or ""), markdown, "beautifulsoup4"


def fetch(
    url_or_path: str,
    *,
    headers: dict[str, str] | None = None,
    source_type: str = "article",
) -> FetchResult:
    normalized = url_or_path.strip()
    session = requests.Session()
    meta: dict[str, Any] = {"strategy": "article", **_reserved_credential_meta()}

    jina_url = f"https://r.jina.ai/{normalized}"
    try:
        logger.info("Article fetch: trying r.jina.ai for %s", normalized)
        response = _request_with_retries(session, jina_url, headers=headers)
        title, markdown = _extract_from_jina_text(response.text)
        if markdown:
            meta.update({"backend": "r.jina.ai"})
            return FetchResult(
                markdown=markdown,
                title=title,
                meta=meta,
                source_type=source_type,
                url_or_path=normalized,
                success=True,
                error=None,
            )
        logger.warning("Article fetch: r.jina.ai returned empty markdown for %s", normalized)
    except requests.RequestException as exc:
        logger.warning("Article fetch: r.jina.ai failed for %s: %s", normalized, exc)
        meta["jina_error"] = str(exc)

    try:
        logger.info("Article fetch: falling back to direct HTML parsing for %s", normalized)
        response = _request_with_retries(session, normalized, headers=headers)
        title, markdown, parser_name = _extract_from_html(response.text)
        if markdown:
            meta.update({"backend": "direct_html", "parser": parser_name})
            return FetchResult(
                markdown=markdown,
                title=title,
                meta=meta,
                source_type=source_type,
                url_or_path=normalized,
                success=True,
                error=None,
            )
        error_message = f"Unable to extract article body from {normalized}."
    except requests.RequestException as exc:
        error_message = f"Article fetch failed for {normalized}: {exc}"
        logger.error(error_message)
        meta["direct_error"] = str(exc)
    else:
        logger.error(error_message)

    return FetchResult(
        markdown=None,
        title=None,
        meta=meta,
        source_type=source_type,
        url_or_path=normalized,
        success=False,
        error=error_message,
    )
