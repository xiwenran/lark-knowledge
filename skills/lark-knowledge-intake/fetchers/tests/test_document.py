from __future__ import annotations

import sys
import types
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest import mock


DOCUMENT_PATH = Path(__file__).resolve().parents[1] / "document.py"


def load_document_module():
    spec = spec_from_file_location("lk_fetchers_document_test", DOCUMENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load document module from {DOCUMENT_PATH}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DocumentFetcherTests(unittest.TestCase):
    def test_fetch_converts_file_and_uses_heading_as_title(self) -> None:
        module = load_document_module()
        fake_markitdown = types.SimpleNamespace(
            MarkItDown=lambda **_: types.SimpleNamespace(
                convert=lambda path: types.SimpleNamespace(
                    text_content="# Converted Title\n\nBody paragraph."
                )
            )
        )

        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "sample.pdf"
            file_path.write_bytes(b"%PDF-1.4\n% test\n")

            with mock.patch.dict(sys.modules, {"markitdown": fake_markitdown}):
                result = module.fetch(str(file_path))

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "doc_pdf")
        self.assertEqual(result.title, "Converted Title")
        self.assertIn("Body paragraph.", result.markdown or "")
        self.assertEqual(result.url_or_path, str(file_path))
        self.assertEqual(result.meta["timeout_seconds"], module.DEFAULT_TIMEOUT_SECONDS)

    def test_fetch_uses_filename_when_heading_missing(self) -> None:
        module = load_document_module()
        fake_markitdown = types.SimpleNamespace(
            MarkItDown=lambda **_: types.SimpleNamespace(
                convert=lambda path: types.SimpleNamespace(text_content="Plain first line")
            )
        )

        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "fallback-name.docx"
            file_path.write_bytes(b"test")

            with mock.patch.dict(sys.modules, {"markitdown": fake_markitdown}):
                result = module.fetch(str(file_path))

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "doc_docx")
        self.assertEqual(result.title, "fallback-name")

    def test_fetch_large_pdf_sets_warning_and_extended_timeout(self) -> None:
        module = load_document_module()
        fake_markitdown = types.SimpleNamespace(
            MarkItDown=lambda **_: types.SimpleNamespace(
                convert=lambda path: types.SimpleNamespace(text_content="# Large PDF")
            )
        )

        with NamedTemporaryFile(suffix=".pdf") as temp_file:
            temp_file.truncate(module.LARGE_PDF_SIZE_BYTES + 1)
            temp_file.flush()

            with mock.patch.dict(sys.modules, {"markitdown": fake_markitdown}):
                result = module.fetch(temp_file.name)

        self.assertTrue(result.success)
        self.assertEqual(result.meta["timeout_seconds"], 300)
        self.assertTrue(result.meta["warnings"])
        self.assertIn("50MB", result.meta["warnings"][0])

    def test_fetch_returns_failed_result_with_original_exception(self) -> None:
        module = load_document_module()
        fake_markitdown = types.SimpleNamespace(
            MarkItDown=lambda **_: types.SimpleNamespace(
                convert=mock.Mock(side_effect=RuntimeError("markitdown boom"))
            )
        )

        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "broken.pptx"
            file_path.write_bytes(b"test")

            with mock.patch.dict(sys.modules, {"markitdown": fake_markitdown}):
                result = module.fetch(str(file_path))

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "doc_pptx")
        self.assertIn("markitdown boom", result.error or "")


if __name__ == "__main__":
    unittest.main()
