from __future__ import annotations

import logging
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_SECONDS = 60


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
    from . import document
    from .types import FetchResult
except ImportError:
    document = _load_sibling_module("document")
    FetchResult = _load_sibling_module("types").FetchResult


def _extract_arxiv_id(url: str) -> str:
    parsed = urlparse(url.strip())
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"arxiv.org", "www.arxiv.org"}:
        raise ValueError(f"Unsupported arXiv URL: {url}")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] not in {"abs", "pdf"}:
        raise ValueError(f"Unsupported arXiv URL: {url}")

    arxiv_id = "/".join(parts[1:])
    if parts[0] == "pdf" and arxiv_id.endswith(".pdf"):
        arxiv_id = arxiv_id[:-4]
    if not arxiv_id:
        raise ValueError(f"Unsupported arXiv URL: {url}")
    return arxiv_id


def _build_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _build_abs_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{arxiv_id}"


def _build_jina_url(abs_url: str) -> str:
    return f"https://r.jina.ai/http://{abs_url.removeprefix('https://')}"


def _extract_title(markdown: str | None, default: str) -> str:
    if markdown:
        for line in markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip() or default
            break
    return default


def _download_pdf(pdf_url: str, target_path: Path) -> None:
    response = requests.get(pdf_url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()
    with target_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                handle.write(chunk)


def _fetch_jina_fallback(abs_url: str, arxiv_id: str) -> FetchResult:
    jina_url = _build_jina_url(abs_url)
    response = requests.get(jina_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()
    markdown = response.text
    return FetchResult(
        markdown=markdown,
        title=_extract_title(markdown, arxiv_id),
        meta={
            "fallback": "r.jina.ai",
            "abs_url": abs_url,
            "jina_url": jina_url,
        },
        source_type="arxiv",
        url_or_path=abs_url,
        success=True,
        error=None,
    )


def fetch(url: str) -> FetchResult:
    normalized = url.strip()

    try:
        arxiv_id = _extract_arxiv_id(normalized)
        abs_url = _build_abs_url(arxiv_id)
        pdf_url = _build_pdf_url(arxiv_id)

        with TemporaryDirectory(prefix="lk-arxiv-") as temp_dir:
            temp_path = Path(temp_dir) / f"{arxiv_id.replace('/', '_')}.pdf"
            try:
                _download_pdf(pdf_url, temp_path)
            except Exception as exc:
                logger.warning("arXiv PDF download failed for %s: %s", normalized, exc)
                fallback_result = _fetch_jina_fallback(abs_url, arxiv_id)
                fallback_result.url_or_path = normalized
                fallback_result.meta["pdf_url"] = pdf_url
                fallback_result.meta["download_error"] = str(exc)
                return fallback_result

            document_result = document.fetch(str(temp_path))
            if document_result.success:
                merged_meta = dict(document_result.meta)
                merged_meta.update(
                    {
                        "abs_url": abs_url,
                        "pdf_url": pdf_url,
                        "temporary_file": str(temp_path),
                    }
                )
                return FetchResult(
                    markdown=document_result.markdown,
                    title=document_result.title,
                    meta=merged_meta,
                    source_type="arxiv",
                    url_or_path=normalized,
                    success=True,
                    error=None,
                )

            return FetchResult(
                markdown=document_result.markdown,
                title=document_result.title or arxiv_id,
                meta={
                    "abs_url": abs_url,
                    "pdf_url": pdf_url,
                    "document_meta": document_result.meta,
                },
                source_type="arxiv",
                url_or_path=normalized,
                success=False,
                error=document_result.error,
            )
    except Exception as exc:
        logger.warning("arXiv fetch failed for %s: %s", normalized, exc)
        return FetchResult(
            markdown=None,
            title=None,
            meta={},
            source_type="arxiv",
            url_or_path=normalized,
            success=False,
            error=str(exc),
        )
