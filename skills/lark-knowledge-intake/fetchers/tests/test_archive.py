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


class ArchiveFetcherTests(unittest.TestCase):
    def test_fetch_returns_failed_result_when_archive_and_cache_both_fail(self) -> None:
        module = load_module("archive")

        with patch.object(
            module,
            "_request_with_retries",
            side_effect=module.requests.RequestException("all backends failed"),
        ):
            result = module.fetch("https://example.com/missing")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "fetch_failed")
        self.assertEqual(result.url_or_path, "https://example.com/missing")
        self.assertIsNotNone(result.error)
        self.assertIn("archive.today", result.error or "")
        self.assertIn("google cache", result.error or "")

    def test_fetch_uses_google_cache_after_archive_failure(self) -> None:
        module = load_module("archive")

        cache_response = Mock()
        cache_response.status_code = 200
        cache_response.text = (
            "<html><head><title>Cached Title</title></head>"
            "<body><main><h1>Cached Title</h1><p>Cached paragraph.</p></main></body></html>"
        )
        cache_response.raise_for_status = Mock()

        def side_effect(_session, url, **_kwargs):
            if "archive.today" in url:
                raise module.requests.RequestException("archive failed")
            return cache_response

        with patch.object(module, "_request_with_retries", side_effect=side_effect):
            result = module.fetch("https://example.com/post")

        self.assertTrue(result.success)
        self.assertEqual(result.title, "Cached Title")
        self.assertIn("Cached paragraph.", result.markdown or "")


if __name__ == "__main__":
    unittest.main()
