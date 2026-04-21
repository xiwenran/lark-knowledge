from __future__ import annotations

import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import sys


DISPATCHER_PATH = Path(__file__).resolve().parents[1] / "dispatcher.py"
CREDENTIALS_PATH = Path(__file__).resolve().parents[1] / "credentials.py"
TYPES_PATH = Path(__file__).resolve().parents[1] / "types.py"


def load_dispatcher_module():
    spec = spec_from_file_location("lk_fetchers_dispatcher", DISPATCHER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load dispatcher module from {DISPATCHER_PATH}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_module(module_name: str, module_path: Path):
    spec = spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DispatcherTests(unittest.TestCase):
    def test_detect_source_type_covers_urls_and_files(self) -> None:
        module = load_dispatcher_module()

        cases = [
            ("https://example.com/post", "article"),
            ("https://www.nytimes.com/2026/04/21/example.html", "paywall_news"),
            ("https://mp.weixin.qq.com/s/abc", "wechat_mp"),
            ("https://x.com/user/status/1", "tweet"),
            ("https://twitter.com/user/status/2", "tweet"),
            ("https://www.zhihu.com/question/123456", "zhihu"),
            ("https://www.xiaohongshu.com/explore/abc123", "xhs_note"),
            ("https://www.bilibili.com/video/BV1xx411c7mD", "video_bilibili"),
            ("https://www.youtube.com/watch?v=abc123", "video_youtube"),
            ("https://youtu.be/abc123", "video_youtube"),
            ("https://www.xiaoyuzhoufm.com/episode/123", "podcast"),
            ("https://www.ximalaya.com/sound/123", "podcast"),
            ("https://arxiv.org/abs/1234.5678", "arxiv"),
            ("/tmp/example.pdf", "doc_pdf"),
            ("/tmp/example.docx", "doc_docx"),
            ("/tmp/example.pptx", "doc_pptx"),
            ("/tmp/example.xlsx", "doc_xlsx"),
            ("/tmp/example.epub", "doc_epub"),
            ("/tmp/example.png", "image"),
            ("mailto:test@example.com", "fallback"),
            ("random free text", "fallback"),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(module.detect_source_type(value), expected)

    def test_dispatch_returns_failed_fetch_result_for_unsupported_active_fetcher(self) -> None:
        module = load_dispatcher_module()

        result = module.dispatch("https://x.com/user/status/1")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "tweet")
        self.assertEqual(result.url_or_path, "https://x.com/user/status/1")
        self.assertIsNone(result.markdown)
        self.assertIsNotNone(result.error)
        self.assertIn("No active fetcher", result.error)
        self.assertEqual(
            result.meta,
            {
                "routed": True,
                "fetcher_active": False,
            },
        )

    def test_dispatch_falls_back_from_article_to_archive(self) -> None:
        module = load_dispatcher_module()
        fetch_result_module = load_module("lk_fetchers_types_test_dispatcher_article", TYPES_PATH)

        article_failed = fetch_result_module.FetchResult(
            source_type="article",
            url_or_path="https://example.com/post",
            success=False,
            error="article failed",
        )
        archive_success = fetch_result_module.FetchResult(
            markdown="# Archived\n\nRecovered body.",
            title="Archived",
            meta={"backend": "archive.today"},
            source_type="article",
            url_or_path="https://example.com/post",
            success=True,
            error=None,
        )

        with patch.object(module._article_fetcher, "fetch", return_value=article_failed), patch.object(
            module._archive_fetcher, "fetch", return_value=archive_success
        ):
            result = module.dispatch("https://example.com/post")

        self.assertTrue(result.success)
        self.assertEqual(result.title, "Archived")
        self.assertEqual(result.meta["backend"], "archive.today")

    def test_dispatch_returns_fetch_failed_when_archive_chain_fails(self) -> None:
        module = load_dispatcher_module()
        fetch_result_module = load_module("lk_fetchers_types_test_dispatcher_failed", TYPES_PATH)

        article_failed = fetch_result_module.FetchResult(
            source_type="article",
            url_or_path="https://example.com/post",
            success=False,
            error="article failed",
        )
        archive_failed = fetch_result_module.FetchResult(
            source_type="fetch_failed",
            url_or_path="https://example.com/post",
            success=False,
            error="archive failed",
        )

        with patch.object(module._article_fetcher, "fetch", return_value=article_failed), patch.object(
            module._archive_fetcher, "fetch", return_value=archive_failed
        ):
            result = module.dispatch("https://example.com/post")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "fetch_failed")
        self.assertEqual(result.url_or_path, "https://example.com/post")
        self.assertIn("article failed", result.error or "")
        self.assertIn("archive failed", result.error or "")

    def test_dispatch_handles_more_than_ten_urls_and_three_files(self) -> None:
        module = load_dispatcher_module()

        cases = [
            ("https://example.com/post", "article"),
            ("https://www.nytimes.com/2026/04/21/example.html", "paywall_news"),
            ("https://mp.weixin.qq.com/s/abc", "wechat_mp"),
            ("https://x.com/user/status/1", "tweet"),
            ("https://www.zhihu.com/question/123456", "zhihu"),
            ("https://www.xiaohongshu.com/explore/abc123", "xhs_note"),
            ("https://www.bilibili.com/video/BV1xx411c7mD", "video_bilibili"),
            ("https://www.youtube.com/watch?v=abc123", "video_youtube"),
            ("https://www.xiaoyuzhoufm.com/episode/123", "podcast"),
            ("https://arxiv.org/abs/1234.5678", "arxiv"),
            ("https://unknown.invalid/resource", "article"),
            ("/tmp/example.pdf", "doc_pdf"),
            ("/tmp/example.docx", "doc_docx"),
            ("/tmp/example.pptx", "doc_pptx"),
            ("/tmp/example.xlsx", "doc_xlsx"),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(module.detect_source_type(value), expected)

    def test_supported_source_types_constant_is_complete(self) -> None:
        module = load_dispatcher_module()

        expected = {
            "article",
            "paywall_news",
            "wechat_mp",
            "tweet",
            "zhihu",
            "xhs_note",
            "video_bilibili",
            "video_youtube",
            "podcast",
            "doc_pdf",
            "doc_docx",
            "doc_pptx",
            "doc_xlsx",
            "doc_epub",
            "arxiv",
            "image",
            "fallback",
            "fetch_failed",
        }

        self.assertEqual(module.SUPPORTED_SOURCE_TYPES, expected)

    def test_fetch_result_contract_fields_are_stable(self) -> None:
        module = load_module("lk_fetchers_types_test", TYPES_PATH)

        result = module.FetchResult(
            markdown=None,
            title="Sample",
            meta={"key": "value"},
            source_type="article",
            url_or_path="https://example.com/post",
            success=False,
            error="Not fetched",
        )

        self.assertEqual(result.markdown, None)
        self.assertEqual(result.title, "Sample")
        self.assertEqual(result.meta, {"key": "value"})
        self.assertEqual(result.source_type, "article")
        self.assertEqual(result.url_or_path, "https://example.com/post")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Not fetched")

    def test_load_local_credential_returns_none_when_file_missing(self) -> None:
        module = load_module("lk_fetchers_credentials_test", CREDENTIALS_PATH)

        with TemporaryDirectory() as temp_dir:
            original_directory = module.LOCAL_DIRECTORY
            module.LOCAL_DIRECTORY = Path(temp_dir)
            try:
                self.assertIsNone(module.load_local_credential("missing-cookie.txt"))
            finally:
                module.LOCAL_DIRECTORY = original_directory


if __name__ == "__main__":
    unittest.main()
