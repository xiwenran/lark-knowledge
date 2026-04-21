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


class PaywallFetcherTests(unittest.TestCase):
    def test_fetch_sends_googlebot_headers(self) -> None:
        module = load_module("paywall")

        jina_response = Mock()
        jina_response.status_code = 200
        jina_response.text = "# Paywall Title\n\nUnlocked body."
        jina_response.raise_for_status = Mock()

        with patch.object(module, "_request_with_retries", return_value=jina_response) as request_mock:
            result = module.fetch("https://www.nytimes.com/2026/04/21/example.html")

        self.assertTrue(result.success)
        self.assertEqual(result.title, "Paywall Title")
        headers = request_mock.call_args.kwargs["headers"]
        self.assertEqual(
            headers["User-Agent"],
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        )
        self.assertEqual(headers["X-Forwarded-For"], "66.249.66.1")
        self.assertEqual(headers["Referer"], "https://www.google.com/")


if __name__ == "__main__":
    unittest.main()
