from __future__ import annotations

import builtins
import sys
import types
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


class WechatFetcherTests(unittest.TestCase):
    def test_fetch_returns_error_when_cookie_is_missing(self) -> None:
        module = load_module("wechat")

        with patch.object(module, "_load_cookie_path", return_value=None):
            result = module.fetch("https://mp.weixin.qq.com/s/example")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "wechat_mp")
        self.assertEqual(
            result.error,
            "扫码未完成，请运行 python -m fetchers.wechat --login 首次登录",
        )

    def test_fetch_returns_error_when_playwright_is_not_installed(self) -> None:
        module = load_module("wechat")
        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "playwright.sync_api":
                raise ImportError("No module named playwright")
            return original_import(name, globals, locals, fromlist, level)

        with patch.object(module, "_load_cookie_path", return_value=Path("/tmp/wechat_cookie.json")), patch(
            "builtins.__import__", side_effect=fake_import
        ):
            result = module.fetch("https://mp.weixin.qq.com/s/example")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "wechat_mp")
        self.assertEqual(result.error, "playwright 未安装")

    def test_fetch_returns_markdown_when_playwright_succeeds(self) -> None:
        module = load_module("wechat")

        fake_sync_api = types.ModuleType("playwright.sync_api")
        fake_playwright = Mock()
        fake_browser = Mock()
        fake_context = Mock()
        fake_page = Mock()

        fake_page.content.return_value = (
            "<html><head><title>网页标题</title></head><body>"
            "<h2 id='activity-name'>公众号标题</h2>"
            "<div id='js_content'><p>第一段</p><pre><code>print(1)</code></pre></div>"
            "</body></html>"
        )
        fake_context.new_page.return_value = fake_page
        fake_browser.new_context.return_value = fake_context
        fake_playwright.chromium.launch.return_value = fake_browser

        fake_manager = Mock()
        fake_manager.__enter__ = Mock(return_value=fake_playwright)
        fake_manager.__exit__ = Mock(return_value=False)
        fake_sync_api.sync_playwright = Mock(return_value=fake_manager)

        with patch.object(module, "_load_cookie_path", return_value=Path("/tmp/wechat_cookie.json")), patch.dict(
            sys.modules, {"playwright.sync_api": fake_sync_api}
        ):
            result = module.fetch("https://mp.weixin.qq.com/s/example")

        self.assertTrue(result.success)
        self.assertEqual(result.source_type, "wechat_mp")
        self.assertEqual(result.title, "公众号标题")
        self.assertIn("第一段", result.markdown or "")
        self.assertIn("print(1)", result.markdown or "")
        fake_page.goto.assert_called_once_with(
            "https://mp.weixin.qq.com/s/example",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        fake_browser.new_context.assert_called_once_with(storage_state="/tmp/wechat_cookie.json")

    def test_fetch_converts_runtime_exception_to_failed_result(self) -> None:
        module = load_module("wechat")

        fake_sync_api = types.ModuleType("playwright.sync_api")
        fake_playwright = Mock()
        fake_browser = Mock()
        fake_playwright.chromium.launch.return_value = fake_browser
        fake_browser.new_context.side_effect = RuntimeError("context broken")

        fake_manager = Mock()
        fake_manager.__enter__ = Mock(return_value=fake_playwright)
        fake_manager.__exit__ = Mock(return_value=False)
        fake_sync_api.sync_playwright = Mock(return_value=fake_manager)

        with patch.object(module, "_load_cookie_path", return_value=Path("/tmp/wechat_cookie.json")), patch.dict(
            sys.modules, {"playwright.sync_api": fake_sync_api}
        ):
            result = module.fetch("https://mp.weixin.qq.com/s/example")

        self.assertFalse(result.success)
        self.assertEqual(result.source_type, "wechat_mp")
        self.assertEqual(result.error, "context broken")


if __name__ == "__main__":
    unittest.main()
