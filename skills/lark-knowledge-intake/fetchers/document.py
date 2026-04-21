from __future__ import annotations

import logging
import signal
import sys
import threading
from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 120
LARGE_PDF_TIMEOUT_SECONDS = 300
LARGE_PDF_SIZE_BYTES = 50 * 1024 * 1024

SOURCE_TYPE_BY_SUFFIX = {
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


@contextmanager
def _alarm_timeout(seconds: int):
    if (
        seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    def _handle_timeout(signum, frame):  # type: ignore[unused-argument]
        raise TimeoutError(f"markitdown conversion timed out after {seconds}s")

    previous_handler = signal.signal(signal.SIGALRM, _handle_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _detect_source_type(file_path: Path) -> str:
    return SOURCE_TYPE_BY_SUFFIX.get(file_path.suffix.lower(), "fallback")


def _extract_title(markdown: str | None, file_path: Path) -> str:
    if markdown:
        for line in markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip() or file_path.stem
            break
    return file_path.stem


def _load_markitdown_module():
    try:
        import markitdown
    except ImportError as exc:
        raise RuntimeError("markitdown is not installed") from exc
    return markitdown


def _convert_with_markitdown(file_path: Path, timeout_seconds: int) -> str:
    markitdown = _load_markitdown_module()
    converter = markitdown.MarkItDown(enable_plugins=False)
    with _alarm_timeout(timeout_seconds):
        result = converter.convert(str(file_path))
    text_content = getattr(result, "text_content", None)
    if text_content is None:
        raise RuntimeError("markitdown returned no text_content")
    return text_content


def fetch(file_path: str) -> FetchResult:
    normalized = file_path.strip()
    path = Path(normalized)
    source_type = _detect_source_type(path)
    warnings: list[str] = []
    timeout_seconds = DEFAULT_TIMEOUT_SECONDS
    credential_name = "markitdown"
    credential_value = None

    try:
        credential_value = load_local_credential(credential_name)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to read optional credential %s: %s", credential_name, exc)

    try:
        if not normalized:
            raise ValueError("Empty file path.")
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        if source_type == "fallback":
            raise ValueError(f"Unsupported document type: {path.suffix or '<no extension>'}")

        file_size = path.stat().st_size
        if source_type == "doc_pdf" and file_size > LARGE_PDF_SIZE_BYTES:
            warnings.append("PDF exceeds 50MB; using extended 300s timeout.")
            timeout_seconds = LARGE_PDF_TIMEOUT_SECONDS

        markdown = _convert_with_markitdown(path, timeout_seconds)
        title = _extract_title(markdown, path)

        return FetchResult(
            markdown=markdown,
            title=title,
            meta={
                "file_size_bytes": file_size,
                "timeout_seconds": timeout_seconds,
                "warnings": warnings,
                "credential_name": credential_name,
                "credential_present": credential_value is not None,
            },
            source_type=source_type,
            url_or_path=normalized,
            success=True,
            error=None,
        )
    except Exception as exc:
        logger.warning("Document fetch failed for %s: %s", normalized, exc)
        return FetchResult(
            markdown=None,
            title=path.stem or None,
            meta={
                "timeout_seconds": timeout_seconds,
                "warnings": warnings,
                "credential_name": credential_name,
                "credential_present": credential_value is not None,
            },
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error=str(exc),
        )
