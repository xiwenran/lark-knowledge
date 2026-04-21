from __future__ import annotations

import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import Mock, patch


FETCHERS_DIR = Path(__file__).resolve().parents[1]


def load_module(module_name: str):
    module_path = FETCHERS_DIR / f"{module_name}.py"
    spec = spec_from_file_location(f"lk_fetchers_{module_name}_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ArticleFetcherTests(unittest.TestCase):
    def test_fetch_prefers_r_jina_ai_and_returns_markdown(self) -> None:
        module = load_module("article")

        jina_response = Mock()
        jina_response.status_code = 200
        jina_response.text = (
            "Title: Example Title\n"
            "URL Source: https://example.com/post\n"
            "Markdown Content:\n"
            "# Example Title\n\n"
            "Body paragraph."
        )
        jina_response.raise_for_status = Mock()

        with patch.object(module, "_request_with_retries", return_value=jina_response) as request_mock:
            result = module.fetch("https://example.com/post")

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "article")
        self.assertEqual(result.title, "Example Title")
        self.assertIn("Body paragraph.", result.markdown or "")
        self.assertEqual(result.url_or_path, "https://example.com/post")
        self.assertEqual(request_mock.call_args.args[1], "https://r.jina.ai/https://example.com/post")

    def test_fetch_falls_back_to_html_parser_when_r_jina_ai_fails(self) -> None:
        module = load_module("article")

        html_response = Mock()
        html_response.status_code = 200
        html_response.text = (
            "<html><head><title>Fallback Title</title></head>"
            "<body><article><h1>Fallback Title</h1><p>Paragraph one.</p></article></body></html>"
        )
        html_response.raise_for_status = Mock()

        def side_effect(_session, url, **_kwargs):
            if url.startswith("https://r.jina.ai/"):
                raise module.requests.RequestException("jina unavailable")
            return html_response

        with patch.object(module, "_request_with_retries", side_effect=side_effect):
            result = module.fetch("https://example.com/post")

        self.assertTrue(result.success)
        self.assertEqual(result.title, "Fallback Title")
        self.assertIn("Paragraph one.", result.markdown or "")


if __name__ == "__main__":
    unittest.main()
