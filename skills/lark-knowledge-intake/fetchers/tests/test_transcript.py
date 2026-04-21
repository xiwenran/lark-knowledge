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


class TranscriptFetcherTests(unittest.TestCase):
    def test_fetch_returns_error_when_api_key_missing(self) -> None:
        module = load_module("transcript")

        with patch.object(module, "load_local_credential", return_value=None):
            result = module.fetch("https://www.bilibili.com/video/BV1xxx")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "video_bilibili")
        self.assertEqual(
            result.error,
            "Get 笔记 API key 未配置，请将 key 写入 .local/getnote_api_key",
        )
        self.assertEqual(result.url_or_path, "https://www.bilibili.com/video/BV1xxx")

    def test_fetch_returns_failed_when_domain_is_not_supported(self) -> None:
        module = load_module("transcript")

        with patch.object(module, "load_local_credential", return_value="test-key"):
            result = module.fetch("https://example.com/video/123")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "fetch_failed")
        self.assertIn("暂不支持该音视频链接", result.error or "")

    def test_fetch_parses_success_response_into_markdown_and_meta(self) -> None:
        module = load_module("transcript")

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "title": "示例视频",
            "transcript": "ignored",
            "segments": [
                {"start": 0, "end": 12, "text": "第一句"},
                {"start": 65, "end": 72, "text": "第二句"},
            ],
            "duration": 360,
        }

        with patch.object(module, "load_local_credential", return_value="test-key"), patch.object(
            module.requests, "post", return_value=response
        ) as post_mock:
            result = module.fetch("https://www.bilibili.com/video/BV1xxx")

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "video_bilibili")
        self.assertEqual(result.title, "示例视频")
        self.assertEqual(
            result.markdown,
            "# 示例视频\n\n[00:00] 第一句\n[01:05] 第二句",
        )
        self.assertEqual(result.meta["duration"], 360)
        self.assertEqual(result.meta["segment_count"], 2)
        self.assertEqual(result.meta["api_endpoint"], module.GETNOTE_API_ENDPOINT)
        self.assertEqual(post_mock.call_args.kwargs["timeout"], 120)

    def test_fetch_returns_error_for_unauthorized_response(self) -> None:
        module = load_module("transcript")

        response = Mock()
        response.status_code = 401
        response.json.return_value = {"error": "invalid_api_key"}

        with patch.object(module, "load_local_credential", return_value="bad-key"), patch.object(
            module.requests, "post", return_value=response
        ):
            result = module.fetch("https://www.bilibili.com/video/BV1xxx")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "video_bilibili")
        self.assertIn("Get 笔记 API 认证失败", result.error or "")

    def test_fetch_retries_once_on_rate_limit_then_succeeds(self) -> None:
        module = load_module("transcript")

        rate_limited = Mock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {"error": "rate_limited"}

        success = Mock()
        success.status_code = 200
        success.json.return_value = {
            "title": "播客标题",
            "transcript": "ignored",
            "segments": [{"start": 5, "end": 10, "text": "开场"}],
            "duration": 1800,
        }

        with patch.object(module, "load_local_credential", return_value="test-key"), patch.object(
            module.requests, "post", side_effect=[rate_limited, success]
        ) as post_mock, patch.object(module.time, "sleep") as sleep_mock:
            result = module.fetch("https://www.xiaoyuzhoufm.com/episode/123")

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "podcast")
        self.assertEqual(post_mock.call_count, 2)
        sleep_mock.assert_called_once_with(5)

    def test_fetch_returns_error_when_rate_limit_persists(self) -> None:
        module = load_module("transcript")

        rate_limited = Mock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {"error": "rate_limited"}

        with patch.object(module, "load_local_credential", return_value="test-key"), patch.object(
            module.requests, "post", side_effect=[rate_limited, rate_limited]
        ), patch.object(module.time, "sleep") as sleep_mock:
            result = module.fetch("https://www.ximalaya.com/sound/123")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "podcast")
        self.assertIn("请求过于频繁", result.error or "")
        sleep_mock.assert_called_once_with(5)

    def test_fetch_returns_error_for_server_side_failure(self) -> None:
        module = load_module("transcript")

        response = Mock()
        response.status_code = 503
        response.json.return_value = {"error": "service_unavailable"}

        with patch.object(module, "load_local_credential", return_value="test-key"), patch.object(
            module.requests, "post", return_value=response
        ):
            result = module.fetch("https://www.bilibili.com/video/BV1xxx")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "video_bilibili")
        self.assertIn("服务暂时不可用", result.error or "")

    def test_fetch_returns_youtube_specific_degradation_when_platform_unsupported(self) -> None:
        module = load_module("transcript")

        response = Mock()
        response.status_code = 200
        response.json.return_value = {"error": "unsupported_platform"}

        with patch.object(module, "load_local_credential", return_value="test-key"), patch.object(
            module.requests, "post", return_value=response
        ):
            result = module.fetch("https://www.youtube.com/watch?v=abc123")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "fetch_failed")
        self.assertEqual(
            result.error,
            "YouTube 暂不支持，需 yt-dlp + Whisper 自建转写",
        )
        self.assertEqual(result.url_or_path, "https://www.youtube.com/watch?v=abc123")

    def test_dispatch_does_not_crash_for_transcript_source_without_api_key(self) -> None:
        dispatcher = load_module("dispatcher")

        with patch.object(dispatcher._transcript_fetcher, "fetch") as fetch_mock:
            fetch_mock.return_value = dispatcher.FetchResult(
                markdown=None,
                title=None,
                meta={},
                source_type="video_bilibili",
                url_or_path="https://www.bilibili.com/video/BV1xxx",
                success=False,
                error="Get 笔记 API key 未配置，请将 key 写入 .local/getnote_api_key",
            )
            result = dispatcher.dispatch("https://www.bilibili.com/video/BV1xxx")

        self.assertFalse(result.success)
        self.assertEqual(
            result.error,
            "Get 笔记 API key 未配置，请将 key 写入 .local/getnote_api_key",
        )


if __name__ == "__main__":
    unittest.main()
