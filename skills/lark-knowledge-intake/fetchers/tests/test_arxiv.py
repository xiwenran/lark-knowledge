from __future__ import annotations

import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock


ARXIV_PATH = Path(__file__).resolve().parents[1] / "arxiv.py"


def load_arxiv_module():
    spec = spec_from_file_location("lk_fetchers_arxiv_test", ARXIV_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load arxiv module from {ARXIV_PATH}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ArxivFetcherTests(unittest.TestCase):
    def test_fetch_downloads_pdf_and_delegates_to_document_fetcher(self) -> None:
        module = load_arxiv_module()

        pdf_response = mock.Mock()
        pdf_response.raise_for_status.return_value = None
        pdf_response.iter_content.return_value = [b"%PDF-1.4 test"]

        delegated = module.FetchResult(
            markdown="# Paper\n\nConverted body.",
            title="Paper",
            meta={"via": "document"},
            source_type="doc_pdf",
            url_or_path="/tmp/paper.pdf",
            success=True,
            error=None,
        )

        with mock.patch.object(module.requests, "get", return_value=pdf_response) as get_mock:
            with mock.patch.object(module.document, "fetch", return_value=delegated) as fetch_mock:
                result = module.fetch("https://arxiv.org/abs/1234.5678")

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "arxiv")
        self.assertEqual(result.title, "Paper")
        self.assertEqual(result.url_or_path, "https://arxiv.org/abs/1234.5678")
        self.assertEqual(result.meta["pdf_url"], "https://arxiv.org/pdf/1234.5678.pdf")
        self.assertEqual(get_mock.call_args.kwargs["timeout"], 60)
        delegated_path = fetch_mock.call_args.args[0]
        self.assertTrue(delegated_path.endswith(".pdf"))

    def test_fetch_falls_back_to_r_jina_when_pdf_download_fails(self) -> None:
        module = load_arxiv_module()

        jina_response = mock.Mock()
        jina_response.raise_for_status.return_value = None
        jina_response.text = "# Fallback Title\n\nAbstract body."

        with mock.patch.object(
            module.requests,
            "get",
            side_effect=[module.requests.RequestException("pdf failed"), jina_response],
        ):
            result = module.fetch("https://arxiv.org/abs/2501.01234")

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "arxiv")
        self.assertEqual(result.title, "Fallback Title")
        self.assertIn("Abstract body.", result.markdown or "")
        self.assertEqual(result.meta["fallback"], "r.jina.ai")

    def test_fetch_returns_failed_result_for_invalid_arxiv_url(self) -> None:
        module = load_arxiv_module()

        result = module.fetch("https://example.com/not-arxiv")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "arxiv")
        self.assertIn("Unsupported arXiv URL", result.error or "")


if __name__ == "__main__":
    unittest.main()
