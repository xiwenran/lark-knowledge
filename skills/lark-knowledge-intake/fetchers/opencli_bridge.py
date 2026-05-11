from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


logger = logging.getLogger(__name__)

LOCAL_DIRECTORY = Path(__file__).resolve().parent.parent / ".local"
COOKIES_DIRECTORY = LOCAL_DIRECTORY / "opencli_cookies"
DEFAULT_TIMEOUT_MS = 45000
NAVIGATION_TIMEOUT_MS = 30000

PLATFORM_COOKIE_MAP = {
    "xhs": "xhs_state.json",
    "twitter": "twitter_state.json",
    "zhihu": "zhihu_state.json",
}

PLATFORM_LOGIN_URLS = {
    "xhs": "https://www.xiaohongshu.com/explore",
    "twitter": "https://x.com/login",
    "zhihu": "https://www.zhihu.com/signin",
}


def _load_sibling_module(module_name: str):
    module_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = spec_from_file_location(f"lk_fetchers_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    from .types import FetchResult
except ImportError:
    FetchResult = _load_sibling_module("types").FetchResult


def _detect_platform(url: str) -> str:
    hostname = (urlparse(url.strip()).hostname or "").lower()
    if hostname in {"twitter.com", "www.twitter.com", "x.com", "www.x.com"}:
        return "twitter"
    if hostname in {"zhihu.com", "www.zhihu.com"}:
        return "zhihu"
    if hostname in {"xiaohongshu.com", "www.xiaohongshu.com", "xhslink.com"}:
        return "xhs"
    return "unknown"


def _detect_source_type(url: str) -> str:
    platform = _detect_platform(url)
    if platform == "twitter":
        return "tweet"
    if platform == "zhihu":
        return "zhihu"
    if platform == "xhs":
        return "xhs_note"
    return "fetch_failed"


def _get_cookie_path(platform: str) -> Path | None:
    filename = PLATFORM_COOKIE_MAP.get(platform)
    if not filename:
        return None
    path = COOKIES_DIRECTORY / filename
    return path if path.is_file() else None


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def _extract_xhs_note(page) -> dict[str, Any]:
    """从小红书笔记页面提取内容。"""
    page.wait_for_selector("#detail-desc, .note-text, .content", timeout=DEFAULT_TIMEOUT_MS)

    result = page.evaluate("""() => {
        // 标题
        const titleEl = document.querySelector('#detail-title')
            || document.querySelector('.title')
            || document.querySelector('h1');
        const title = titleEl ? titleEl.innerText.trim() : '';

        // 正文
        const descEl = document.querySelector('#detail-desc')
            || document.querySelector('.note-text')
            || document.querySelector('.content .desc');
        const content = descEl ? descEl.innerText.trim() : '';

        // 图片
        const images = [];
        document.querySelectorAll('.swiper-slide img, .note-image img, .media-container img').forEach(img => {
            const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
            if (src && !src.includes('avatar') && !src.includes('emoji')) {
                images.push(src.split('?')[0]);
            }
        });

        // 作者
        const authorEl = document.querySelector('.author-wrapper .username')
            || document.querySelector('.user-nickname')
            || document.querySelector('[class*="author"] [class*="name"]');
        const author = authorEl ? authorEl.innerText.trim() : '';

        // 互动数据
        const likeEl = document.querySelector('[class*="like"] [class*="count"], .like-wrapper .count');
        const collectEl = document.querySelector('[class*="collect"] [class*="count"], .collect-wrapper .count');
        const likes = likeEl ? likeEl.innerText.trim() : '';
        const collects = collectEl ? collectEl.innerText.trim() : '';

        return { title, content, images, author, likes, collects };
    }""")
    return result


def _extract_xhs_profile(page) -> dict[str, Any]:
    """从小红书用户主页提取信息。"""
    page.wait_for_selector('.user-name, .user-nickname, [class*="nickname"]', timeout=DEFAULT_TIMEOUT_MS)

    result = page.evaluate("""() => {
        const nameEl = document.querySelector('.user-name')
            || document.querySelector('.user-nickname')
            || document.querySelector('[class*="nickname"]');
        const name = nameEl ? nameEl.innerText.trim() : '';

        const descEl = document.querySelector('.user-desc')
            || document.querySelector('.desc')
            || document.querySelector('[class*="description"]');
        const desc = descEl ? descEl.innerText.trim() : '';

        const ipEl = document.querySelector('[class*="ip-"]')
            || document.querySelector('.location');
        const ip_location = ipEl ? ipEl.innerText.trim() : '';

        // 笔记列表
        const notes = [];
        document.querySelectorAll('[class*="note-item"], .cover-item, section[class*="note"]').forEach(item => {
            const coverImg = item.querySelector('img');
            const titleEl = item.querySelector('[class*="title"], .footer span, .desc');
            notes.push({
                title: titleEl ? titleEl.innerText.trim() : '',
                cover: coverImg ? (coverImg.getAttribute('src') || '').split('?')[0] : '',
            });
        });

        // 粉丝/关注数
        const statsEls = document.querySelectorAll('[class*="count"], .data-info .count');
        const stats = [];
        statsEls.forEach(el => stats.push(el.innerText.trim()));

        return { name, desc, ip_location, notes: notes.slice(0, 20), stats };
    }""")
    return result


def _build_markdown_from_xhs(data: dict, url: str) -> str:
    """将 XHS 提取数据组装为 Markdown。"""
    lines = []

    path = urlparse(url).path.lower()
    is_profile = "/user/" in path

    if is_profile:
        name = data.get("name", "")
        lines.append(f"# {name}")
        if data.get("desc"):
            lines.append(f"\n{data['desc']}")
        if data.get("ip_location"):
            lines.append(f"\nIP: {data['ip_location']}")
        if data.get("stats"):
            lines.append(f"\n数据: {', '.join(data['stats'])}")
        if data.get("notes"):
            lines.append("\n## 笔记列表\n")
            for i, note in enumerate(data["notes"], 1):
                title = note.get("title", "(无标题)")
                lines.append(f"{i}. {title}")
    else:
        title = data.get("title", "") or data.get("content", "")[:30]
        lines.append(f"# {title}")
        if data.get("author"):
            lines.append(f"\n作者: {data['author']}")
        if data.get("content"):
            lines.append(f"\n{data['content']}")
        if data.get("likes") or data.get("collects"):
            lines.append(f"\n点赞: {data.get('likes', '-')} | 收藏: {data.get('collects', '-')}")
        if data.get("images"):
            lines.append("\n## 图片\n")
            for img_url in data["images"]:
                lines.append(f"- {img_url}")

    return "\n".join(lines).strip()


def fetch(url: str) -> FetchResult:
    """直接用 Playwright + 存储登录态抓取社交平台页面。"""
    normalized = url.strip()
    platform = _detect_platform(normalized)
    source_type = _detect_source_type(normalized)

    if platform == "unknown":
        return FetchResult(
            markdown=None,
            title=None,
            meta={"platform": platform},
            source_type="fetch_failed",
            url_or_path=normalized,
            success=False,
            error=f"无法识别平台: {normalized}",
        )

    cookie_path = _get_cookie_path(platform)
    if cookie_path is None:
        login_url = PLATFORM_LOGIN_URLS.get(platform, "")
        return FetchResult(
            markdown=None,
            title=None,
            meta={"platform": platform, "cookie_dir": str(COOKIES_DIRECTORY)},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error=f"{platform} 登录态未保存。请运行: python -m fetchers.opencli_bridge --login {platform}",
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return FetchResult(
            markdown=None,
            title=None,
            meta={"platform": platform},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error="playwright 未安装，请运行: pip install playwright && playwright install chromium",
        )

    browser = None
    context = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(cookie_path))
            page = context.new_page()
            page.goto(normalized, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            page.wait_for_timeout(3000)

            path = urlparse(normalized).path.lower()

            if platform == "xhs":
                is_profile = "/user/" in path
                if is_profile:
                    data = _extract_xhs_profile(page)
                    title = data.get("name", "XHS Profile")
                    media_urls = [n.get("cover", "") for n in data.get("notes", []) if n.get("cover")]
                else:
                    data = _extract_xhs_note(page)
                    title = data.get("title", "") or data.get("content", "")[:30] or "XHS Note"
                    media_urls = data.get("images", [])

                markdown = _build_markdown_from_xhs(data, normalized)
                author = data.get("author") or data.get("name")

            else:
                # Twitter / Zhihu: 通用提取
                title = page.title() or "Untitled"
                body_text = page.evaluate("() => document.body.innerText")
                markdown = f"# {title}\n\n{body_text[:5000]}"
                media_urls = []
                author = None

            context.close()
            browser.close()

            logger.info("OpenCLI bridge fetch succeeded for %s (platform=%s).", normalized, platform)
            return FetchResult(
                markdown=markdown,
                title=title,
                meta={
                    "platform": platform,
                    "author": author,
                    "media_urls": [u for u in media_urls if u],
                },
                source_type=source_type,
                url_or_path=normalized,
                success=True,
                error=None,
            )

    except Exception as exc:
        logger.error("OpenCLI bridge fetch failed for %s: %s", normalized, exc)
        return FetchResult(
            markdown=None,
            title=None,
            meta={"platform": platform, "cookie_path": str(cookie_path)},
            source_type=source_type,
            url_or_path=normalized,
            success=False,
            error=str(exc),
        )
    finally:
        _close_quietly(locals().get("context"))
        _close_quietly(locals().get("browser"))


def login(platform: str) -> int:
    """打开浏览器让用户手动登录，保存 storage_state。"""
    if platform not in PLATFORM_LOGIN_URLS:
        print(f"不支持的平台: {platform}。支持: {', '.join(PLATFORM_LOGIN_URLS.keys())}")
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright 未安装，请运行: pip install playwright && playwright install chromium")
        return 1

    COOKIES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    login_url = PLATFORM_LOGIN_URLS[platform]
    cookie_filename = PLATFORM_COOKIE_MAP[platform]
    save_path = COOKIES_DIRECTORY / cookie_filename

    print(f"即将打开 {platform} 登录页: {login_url}")
    print("请在浏览器中完成登录，登录成功后回到终端按回车保存。")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        input("\n登录完成后按回车保存登录态...")
        context.storage_state(path=str(save_path))
        context.close()
        browser.close()

    print(f"✅ {platform} 登录态已保存到: {save_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Playwright-based fetcher for login-gated platforms (XHS, Twitter, Zhihu)."
    )
    parser.add_argument("url", nargs="?", help="要抓取的页面 URL")
    parser.add_argument("--login", metavar="PLATFORM", help="登录指定平台 (xhs/twitter/zhihu)")
    args = parser.parse_args(argv)

    if args.login:
        return login(args.login)

    if not args.url:
        parser.error("请提供 URL，或使用 --login <platform> 完成首次登录。")

    result = fetch(args.url)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
