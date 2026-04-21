from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


logger = logging.getLogger(__name__)
WECHAT_SOURCE_TYPE = "wechat_mp"
WECHAT_COOKIE_FILENAME = "wechat_cookie.json"
# 统一走 credentials.py 的 LOCAL_DIRECTORY，避免 .claude/.agents/repo 三处硬编码不一致（三者 symlink 等价）。
# credentials.py 在同目录，用 __file__ 定位。
WECHAT_LOCAL_DIRECTORY = Path(__file__).resolve().parent.parent / ".local"
WECHAT_COOKIE_PATH = WECHAT_LOCAL_DIRECTORY / WECHAT_COOKIE_FILENAME
LOGIN_HINT = "扫码未完成，请运行 python -m fetchers.wechat --login 首次登录"
PLAYWRIGHT_HINT = "playwright 未安装"
DEFAULT_TIMEOUT_MS = 30000


def _load_module(module_name: str):
    module_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = spec_from_file_location(f"lk_fetchers_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FetchResult = _load_module("types").FetchResult
_credentials_module = _load_module("credentials")


def _load_cookie_path() -> Path | None:
    # 优先兼容 credentials.py 将来可能提供的 Path API，避免写死调用方式。
    load_path = getattr(_credentials_module, "load_local_credential_path", None)
    if callable(load_path):
        candidate = load_path(WECHAT_COOKIE_FILENAME)
        if candidate is not None:
            return candidate

    if WECHAT_COOKIE_PATH.is_file():
        return WECHAT_COOKIE_PATH
    return None


def _extract_title(soup: BeautifulSoup) -> str | None:
    for selector in ("#activity-name", "h2", "title"):
        node = soup.select_one(selector)
        if node is None:
            continue
        text = node.get_text(" ", strip=True)
        if text:
            return text
    return None


def _html_to_simple_markdown(content_node: Tag) -> str:
    blocks: list[str] = []
    for node in content_node.find_all(["h1", "h2", "h3", "p", "li", "pre", "blockquote"]):
        text = node.get_text("\n", strip=True)
        if not text:
            continue
        if node.name == "h1":
            blocks.append(f"# {text}")
        elif node.name == "h2":
            blocks.append(f"## {text}")
        elif node.name == "h3":
            blocks.append(f"### {text}")
        elif node.name == "li":
            blocks.append(f"- {text}")
        elif node.name == "pre":
            blocks.append(f"```\n{text}\n```")
        elif node.name == "blockquote":
            blocks.append(f"> {text}")
        else:
            blocks.append(text)
    return "\n\n".join(blocks).strip()


def _convert_content_to_markdown(content_node: Tag) -> tuple[str, str]:
    # 优先走 markdownify，失败时退回简易 HTML 转文本，保证骨架始终可调用。
    try:
        from markdownify import markdownify

        markdown = markdownify(str(content_node), heading_style="ATX").strip()
        if markdown:
            return markdown, "markdownify"
    except Exception as exc:  # pragma: no cover - 降级路径由 fallback 覆盖
        logger.warning("Wechat fetch: markdownify failed, fallback to simple html2text: %s", exc)

    markdown = _html_to_simple_markdown(content_node)
    if markdown:
        return markdown, "simple_html2text"
    raise ValueError("未找到公众号正文内容")


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        try:
            close()
        except Exception as exc:  # pragma: no cover - 关闭异常不影响主结果
            logger.debug("Wechat fetch: close resource failed: %s", exc)


def fetch(url: str) -> FetchResult:
    normalized = url.strip()
    cookie_path = _load_cookie_path()
    if cookie_path is None:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"strategy": "playwright", "cookie_path": str(WECHAT_COOKIE_PATH)},
            source_type=WECHAT_SOURCE_TYPE,
            url_or_path=normalized,
            success=False,
            error=LOGIN_HINT,
        )

    try:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return FetchResult(
                markdown=None,
                title=None,
                meta={"strategy": "playwright", "cookie_path": str(cookie_path)},
                source_type=WECHAT_SOURCE_TYPE,
                url_or_path=normalized,
                success=False,
                error=PLAYWRIGHT_HINT,
            )

        logger.info("Wechat fetch: opening page with persisted cookie for %s", normalized)
        browser = None
        context = None
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(cookie_path))
            page = context.new_page()
            page.goto(normalized, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            html = page.content()

        soup = BeautifulSoup(html, "html.parser")
        content_node = soup.select_one("#js_content")
        if content_node is None:
            raise ValueError("未找到公众号正文内容")

        title = _extract_title(soup)
        markdown, parser_name = _convert_content_to_markdown(content_node)
        return FetchResult(
            markdown=markdown,
            title=title,
            meta={
                "strategy": "playwright",
                "cookie_path": str(cookie_path),
                "parser": parser_name,
            },
            source_type=WECHAT_SOURCE_TYPE,
            url_or_path=normalized,
            success=True,
            error=None,
        )
    except Exception as exc:
        logger.error("Wechat fetch failed for %s: %s", normalized, exc)
        return FetchResult(
            markdown=None,
            title=None,
            meta={"strategy": "playwright", "cookie_path": str(cookie_path)},
            source_type=WECHAT_SOURCE_TYPE,
            url_or_path=normalized,
            success=False,
            error=str(exc),
        )
    finally:
        # finally 里重复关闭是安全的，避免异常路径泄露浏览器资源。
        _close_quietly(locals().get("context"))
        _close_quietly(locals().get("browser"))


def login() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(PLAYWRIGHT_HINT)
        return 1

    WECHAT_LOCAL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        print("请在弹出的浏览器里完成微信扫码登录，完成后回到终端按回车保存 cookie。")
        input()
        context.storage_state(path=str(WECHAT_COOKIE_PATH))
        context.close()
        browser.close()

    print(f"微信登录态已保存到 {WECHAT_COOKIE_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch WeChat MP article content with persisted Playwright state.")
    parser.add_argument("url", nargs="?", help="微信公众号文章 URL")
    parser.add_argument("--login", action="store_true", help="首次扫码登录并保存 storage_state")
    args = parser.parse_args(argv)

    if args.login:
        return login()

    if not args.url:
        parser.error("请提供公众号文章 URL，或使用 --login 完成首次扫码。")

    result = fetch(args.url)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
