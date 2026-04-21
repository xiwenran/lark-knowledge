from __future__ import annotations

import json
import subprocess
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


class OpenCliBridgeTests(unittest.TestCase):
    def test_fetch_returns_error_when_cli_path_is_missing(self) -> None:
        module = load_module("opencli_bridge")

        with patch.object(module, "_resolve_opencli_path", return_value=None):
            result = module.fetch("https://x.com/user/status/1")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "tweet")
        self.assertEqual(result.error, "OpenCLI 未配置，请参考 README 安装")

    def test_fetch_returns_markdown_when_subprocess_succeeds(self) -> None:
        module = load_module("opencli_bridge")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "title": "测试标题",
                    "content": "正文第一段\n正文第二段",
                    "media_urls": ["https://img.example.com/1.jpg", "https://img.example.com/2.jpg"],
                    "author": "测试作者",
                    "platform": "tweet",
                }
            ),
            stderr="",
        )

        with patch.object(module, "_resolve_opencli_path", return_value="/usr/local/bin/opencli"), patch.object(
            module.subprocess, "run", return_value=completed
        ) as run_mock:
            result = module.fetch("https://x.com/user/status/1")

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "tweet")
        self.assertEqual(result.title, "测试标题")
        self.assertIn("# 测试标题", result.markdown or "")
        self.assertIn("正文第一段", result.markdown or "")
        self.assertIn("## 媒体链接", result.markdown or "")
        self.assertIn("- https://img.example.com/1.jpg", result.markdown or "")
        self.assertEqual(result.meta["author"], "测试作者")
        self.assertEqual(result.meta["platform"], "tweet")
        run_mock.assert_called_once_with(
            ["/usr/local/bin/opencli", "fetch", "--url", "https://x.com/user/status/1", "--format", "json"],
            timeout=90,
            capture_output=True,
            text=True,
        )

    def test_fetch_returns_login_error_when_stderr_mentions_auth(self) -> None:
        module = load_module("opencli_bridge")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="session expired, please login again",
        )

        with patch.object(module, "_resolve_opencli_path", return_value="/usr/local/bin/opencli"), patch.object(
            module.subprocess, "run", return_value=completed
        ):
            result = module.fetch("https://www.zhihu.com/question/123")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "zhihu")
        self.assertEqual(result.error, "OpenCLI 登录态失效，请在浏览器重新登录对应平台")

    def test_fetch_returns_stderr_excerpt_when_process_fails(self) -> None:
        module = load_module("opencli_bridge")
        stderr = "boom" * 200
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout="",
            stderr=stderr,
        )

        with patch.object(module, "_resolve_opencli_path", return_value="/usr/local/bin/opencli"), patch.object(
            module.subprocess, "run", return_value=completed
        ):
            result = module.fetch("https://www.xiaohongshu.com/explore/abc123")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "xhs_note")
        self.assertEqual(result.error, stderr[:500])

    def test_fetch_returns_error_when_json_is_invalid(self) -> None:
        module = load_module("opencli_bridge")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="{invalid json}",
            stderr="",
        )

        with patch.object(module, "_resolve_opencli_path", return_value="/usr/local/bin/opencli"), patch.object(
            module.subprocess, "run", return_value=completed
        ):
            result = module.fetch("https://x.com/user/status/1")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "tweet")
        self.assertEqual(result.error, "OpenCLI 返回了无法解析的 JSON")

    def test_fetch_returns_timeout_error_when_subprocess_times_out(self) -> None:
        module = load_module("opencli_bridge")

        with patch.object(module, "_resolve_opencli_path", return_value="/usr/local/bin/opencli"), patch.object(
            module.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="opencli", timeout=90)
        ):
            result = module.fetch("https://x.com/user/status/1")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "tweet")
        self.assertEqual(result.url_or_path, "https://x.com/user/status/1")
        self.assertEqual(result.error, "OpenCLI 抓取超时（90s）")


if __name__ == "__main__":
    unittest.main()
