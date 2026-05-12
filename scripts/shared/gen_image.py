#!/usr/bin/env python3
"""
gen_image.py — 商品拆解笔记图片生成 CLI

商品拆解笔记图片生成，支持两种模式：
  - 动态模式（推荐）：analysis.json 含 story_plan 字段，页数/标题/内容由 AI 决定
  - 固定模式（兼容）：无 story_plan 时回退到 5 张固定结构

也保留单 prompt 生图兼容入口：
  python3 scripts/shared/gen_image.py --prompt "..." --output /tmp/sketch.png

商品拆解用法：
  python3 scripts/shared/gen_image.py --record-id recXXX --prompts-only
  python3 scripts/shared/gen_image.py --record-json /tmp/product_record.json --prompts-only
  python3 scripts/shared/gen_image.py --record-id recXXX --output-dir /tmp
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from openai import OpenAI

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = Path.home() / ".agents/skills/lark-knowledge-config/config.json"
DEFAULT_API_BASE = "https://api.vectorengine.cn/v1"
DEFAULT_MODEL = "gpt-image-2"
MIN_IMAGE_BYTES = 10 * 1024

sys.path.insert(0, str(SCRIPT_DIR))
from poster_template import (  # noqa: E402
    METAPHOR_LIBRARY,
    render_cover_prompt,
    render_inner_prompt,
)


def load_config() -> dict[str, Any]:
    """读取项目配置；本脚本只依赖 image_api 和 base 两个区块。"""
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _normalize_field_value(value: Any) -> Any:
    if isinstance(value, list) and len(value) == 1:
        return _normalize_field_value(value[0])
    if isinstance(value, dict):
        for key in ("text", "name", "value", "link", "url"):
            if key in value:
                return value[key]
    return value


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize_field_value(value) for key, value in record.items()}


def get_record(config: dict[str, Any], record_id: str) -> dict[str, Any]:
    """从通用知识库 Base 读取商品调研记录。"""
    base_cfg = config.get("base", {})
    base_token = base_cfg.get("base_token") or config.get("base_token")
    table_id = base_cfg.get("table_id") or config.get("table_id")
    if not base_token or not table_id:
        raise SystemExit("error: config.json 缺少 base.base_token 或 base.table_id")

    result = subprocess.run(
        [
            "lark-cli",
            "base",
            "+record-get",
            "--base-token",
            str(base_token),
            "--table-id",
            str(table_id),
            "--record-id",
            record_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: lark-cli 返回非 JSON: {result.stderr[:200]}") from exc
    if not data.get("ok"):
        msg = data.get("msg") or data.get("error") or result.stdout[:200]
        raise SystemExit(f"error: 读取记录失败: {msg}")
    return normalize_record(data["data"]["record"])


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_image_config() -> dict[str, str]:
    """从 config.json 读取 image_api 区块。"""
    cfg = load_config()
    img = cfg.get("image_api", {})
    return {
        "key": img.get("key") or os.environ.get("IMAGE_API_KEY", ""),
        "base_url": img.get("base_url") or os.environ.get("IMAGE_API_BASE", "") or DEFAULT_API_BASE,
        "model": img.get("model") or DEFAULT_MODEL,
    }


def _first(record: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(_normalize_field_value(value)).strip()
        if text:
            return text
    return default


def _truncate(text: str, limit: int = 42) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def extract_dim(text: str, marker: str) -> str:
    m = re.search(rf"{marker}[^\n]*\n(.*?)(?=①|②|③|④|⑤|\Z)", text, re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = re.search(rf"{marker}[^：:\n]*[：:]\s*(.+?)(?=\s*[①②③④⑤]|\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def extract_bullets(text: str, max_points: int = 3) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    candidates: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"^[\-*·\d.、\s]+", "", line.strip())
        if line:
            candidates.append(line)
    if len(candidates) < max_points:
        for sentence in re.split(r"[。；;]", text):
            sentence = sentence.strip()
            if len(sentence) > 6:
                candidates.append(sentence)
    deduped = list(dict.fromkeys(_truncate(item, 34) for item in candidates if item))
    return deduped[:max_points]


def _format_points(points: list[str]) -> str:
    while len(points) < 3:
        points.append("待从正文补充具体数据与判断")
    return "\n".join(f"- {point}" for point in points[:3])


def _lookup_metaphor(core_word: str, findings: list[dict[str, str]]) -> str:
    if core_word in METAPHOR_LIBRARY:
        return "\n".join(METAPHOR_LIBRARY[core_word])
    findings.append(
        {
            "file": "scripts/shared/poster_template.py",
            "line": "192",
            "description": f"METAPHOR_LIBRARY 缺少商品拆解核心词「{core_word}」的隐喻预设，已用通用视觉母题降级。",
            "owner": "K6/K5 后续补充隐喻预设",
        }
    )
    return f"A. 围绕「{core_word}」设计一个清晰、轻盈、可读的水彩剪纸视觉母题"


def _productize_prompt(prompt: str) -> str:
    """把 K6 All In V2 模板渲染结果转换为商品拆解语境。"""
    replacements = {
        "正在创作 All In Podcast 中文知识库的封面海报": "正在创作小红书商品拆解笔记的封面海报",
        "正在创作 All In Podcast 中文知识库的**内页**": "正在创作小红书商品拆解笔记的**内页**",
        "在本期 All In Podcast 商品拆解 的语境中": "在这份商品拆解笔记的语境中",
        "「ALL IN PODCAST 中文知识库」": "「商品拆解笔记」",
        "- 四位主播名：Jason · Chamath · Sacks · Friedberg（小字嵌入侧边或底部，像署名一样克制）\n": "",
        "底部右下角小字：「All In 中文笔记」（系列标识）": "底部右下角小字：「产品拆解笔记」（系列标识）",
        "根据本期议题情绪，参考以下色调建议（不强制，AI 可自行判断）：": (
            "本批是商品拆解，建议参考情绪库中电商/引流/轻盈分支。\n"
            "根据本期议题情绪，参考以下色调建议（不强制，AI 可自行判断）："
        ),
    }
    for old, new in replacements.items():
        prompt = prompt.replace(old, new)
    return prompt


def _analysis_text(analysis: dict[str, Any]) -> str:
    for key in ("five_dim", "五维分析", "analysis", "markdown", "content"):
        value = analysis.get(key)
        if value:
            return str(value)
    return ""


def _build_dynamic_breakdown_prompts(
    record: dict[str, Any], analysis: dict[str, Any], story_plan: dict
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """story_plan 驱动的动态商品拆解图片生成。"""
    record = normalize_record(record)
    findings: list[dict[str, str]] = []

    product_name = _first(record, "商品名称", "产品名称", "标题", "title", "Title", default="未命名商品")
    category = _first(record, "主营品类", "品类", "资产形态", "专题", default="商品品类")
    sales = _first(record, "销量", "销量数据", "已售", default="销量待补充")
    date = _first(record, "调研日期", "发布日期", "创建时间", default=time.strftime("%Y-%m-%d"))

    cover_title = story_plan.get('cover_title', product_name)
    cover_metaphors = _lookup_metaphor(product_name, findings)
    cover_points = _format_points([
        f"商品名称：{product_name}",
        f"品类：{category}",
        f"洞察角度：{story_plan.get('angle', '')}",
    ])
    cover_prompt = _productize_prompt(
        render_cover_prompt({
            "episode": "商品拆解",
            "date": date,
            "core_word": cover_title,
            "points": cover_points,
            "aux_poetry": f"- 「{story_plan.get('angle', '把一个商品拆成一张商业地图')}」",
            "forbidden": "- 不要出现推荐、种草、必买、安利等消费诱导措辞",
            "context": f"这是一份小红书电商商品拆解，核心商品是「{product_name}」。",
            "core_word_symbolism": f"「{product_name}」象征一个可被拆解的商品样本。",
            "metaphor_options": cover_metaphors,
            "sub_words": story_plan.get('angle', '商业模式·流量转化·机会洞察'),
            "title": f"{product_name}：{story_plan.get('angle', '商品拆解')}",
            "duration": "产品形态·定价·转化",
            "views": str(sales),
            "topic": f"{category}",
        })
    )

    pages: list[dict[str, Any]] = [
        {"page_num": 1, "title": "封面", "core_keyword": product_name, "prompt": cover_prompt},
    ]

    for idx, page_spec in enumerate(story_plan.get('pages', [])):
        title = page_spec.get('title', f'第{idx + 2}页')
        metaphors = _lookup_metaphor(f"{category}{title}", findings)
        points_raw = []
        for sec in page_spec.get('sections', []):
            label = sec.get('label', '')
            content = sec.get('content', '')
            points_raw.append(f"{label}：{content}" if label else content)
        prompt = _productize_prompt(
            render_inner_prompt({
                "page_title": title,
                "core_keyword": f"{category}{title}",
                "page_subtitle": page_spec.get('highlight', title),
                "cross_page_motif_hint": f"隐喻预设参考：{metaphors}",
                "points": _format_points(points_raw[:3] or [title]),
                "aux_poetry": page_spec.get('highlight', ''),
            })
        )
        pages.append({
            "page_num": idx + 2,
            "title": title,
            "core_keyword": f"{category}{title}",
            "prompt": prompt,
        })

    return pages, findings


def build_product_breakdown_prompts(
    record: dict[str, Any], analysis: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """构建商品拆解图。优先用 story_plan 动态模式，否则回退固定 5 张结构。"""
    record = normalize_record(record)
    analysis = analysis or {}

    story_plan = analysis.get('story_plan')
    if story_plan and story_plan.get('pages'):
        return _build_dynamic_breakdown_prompts(record, analysis, story_plan)
    findings: list[dict[str, str]] = []

    product_name = _first(record, "商品名称", "产品名称", "标题", "title", "Title", default="未命名商品")
    category = _first(record, "主营品类", "品类", "资产形态", "专题", default="商品品类")
    traffic_entry = _first(record, "流量入口", "引流方式", "来源渠道", default="流量入口")
    price = _first(record, "价格", "售价", "定价", default="价格待补充")
    sales = _first(record, "销量", "销量数据", "已售", default="销量待补充")
    date = _first(record, "调研日期", "发布日期", "创建时间", default=time.strftime("%Y-%m-%d"))

    text = _analysis_text(analysis)
    dim1 = extract_dim(text, "①")
    dim2 = extract_dim(text, "②")
    dim3 = extract_dim(text, "③")
    dim5 = extract_dim(text, "⑤")

    cover_core = product_name
    business_core = f"{category}商业引擎"
    traffic_core = f"{traffic_entry}流量漏斗"
    opportunity_core = f"{category}机会地图"
    cover_metaphors = _lookup_metaphor(cover_core, findings)
    business_metaphors = _lookup_metaphor(business_core, findings)
    traffic_metaphors = _lookup_metaphor(traffic_core, findings)
    opportunity_metaphors = _lookup_metaphor(opportunity_core, findings)

    cover_points = _format_points(
        [
            f"商品名称：{product_name}",
            f"主营品类：{category}",
            f"流量入口：{traffic_entry}",
        ]
    )
    cover_prompt = _productize_prompt(
        render_cover_prompt(
            {
                "episode": "商品拆解",
                "date": date,
                "core_word": cover_core,
                "points": cover_points,
                "aux_poetry": "- 「把一个商品拆成一张商业地图」\n- 「看见流量背后的结构」",
                "forbidden": "- 不要出现推荐、种草、必买、安利等消费诱导措辞",
                "context": f"这是一份小红书电商商品拆解，核心商品是「{product_name}」，主营品类是「{category}」，主要流量入口是「{traffic_entry}」。",
                "core_word_symbolism": f"「{product_name}」象征一个可被拆解的商品样本；「{category}」象征赛道位置；「{traffic_entry}」象征增长入口。",
                "metaphor_options": cover_metaphors,
                "sub_words": "商业模式·流量转化·机会洞察",
                "title": f"{product_name}：商品拆解笔记",
                "duration": "产品形态·定价·转化",
                "views": str(sales),
                "topic": f"{category} · {traffic_entry}",
            }
        )
    )

    pages = [
        {"page_num": 1, "title": "封面", "core_keyword": cover_core, "prompt": cover_prompt},
        {
            "page_num": 2,
            "title": "核心卖点洞察",
            "core_keyword": business_core,
            "prompt": _productize_prompt(
                render_inner_prompt(
                {
                    "page_title": "核心卖点洞察",
                    "core_keyword": business_core,
                    "page_subtitle": f"{product_name} 真正卖的是什么？",
                    "cross_page_motif_hint": (
                        "视觉母题建议用价格标签、时钟（省时间）、阶梯定价的剪纸结构。"
                        f"\n隐喻预设参考：{business_metaphors}"
                    ),
                    "points": _format_points(
                        extract_bullets(dim1 + "\n" + dim3, 3)
                        or [f"反常识洞察：{category}卖的不是内容，是省下的时间", f"定价逻辑：{price}不是终点价，是进门价", "对你的启发：问自己——我卖的到底是内容还是效率？"]
                    ),
                    "aux_poetry": "买家花的不是钱，是对省下时间的信任。",
                }
                )
            ),
        },
        {
            "page_num": 3,
            "title": "流量认知差",
            "core_keyword": traffic_core,
            "prompt": _productize_prompt(
                render_inner_prompt(
                {
                    "page_title": "流量认知差",
                    "core_keyword": traffic_core,
                    "page_subtitle": f"从「{traffic_entry}」看被低估的获客方式",
                    "cross_page_motif_hint": (
                        "视觉母题建议用搜索框vs推荐流、转化率对比、手绘箭头贯穿全页。"
                        f"\n隐喻预设参考：{traffic_metaphors}"
                    ),
                    "points": _format_points(
                        extract_bullets(dim2, 3)
                        or [f"反常识洞察：搜索流量转化率比推荐流量高3-5倍", f"入口：{traffic_entry}", "对你的启发：你现在的获客方式是搜索还是推荐？"]
                    ),
                    "aux_poetry": "主动搜你的人，才是最容易成交的客户。",
                }
                )
            ),
        },
        {
            "page_num": 4,
            "title": "可复用经验",
            "core_keyword": opportunity_core,
            "prompt": _productize_prompt(
                render_inner_prompt(
                {
                    "page_title": "可复用经验",
                    "core_keyword": opportunity_core,
                    "page_subtitle": f"3个通用原则 + 1个风险提醒",
                    "cross_page_motif_hint": (
                        "视觉母题建议用清单勾选、迁移箭头、风险警示牌贯穿全页。"
                        f"\n隐喻预设参考：{opportunity_metaphors}"
                    ),
                    "points": _format_points(
                        extract_bullets(dim5, 3)
                        or ["原则①：卖省的时间而非卖内容多", f"原则②：差评是最好的选品工具", f"风险：{category}同品类价格战，壁垒靠持续输出"]
                    ),
                    "aux_poetry": "最值得学的不是品类，而是背后可迁移的设计原则。",
                }
                )
            ),
        },
        {
            "page_num": 5,
            "title": "资料预览",
            "core_keyword": product_name,
            "prompt": _productize_prompt(
                render_inner_prompt(
                {
                    "page_title": "完整拆解报告预览",
                    "core_keyword": product_name,
                    "page_subtitle": f"{product_name} 完整操作手册",
                    "cross_page_motif_hint": (
                        "视觉母题建议用文档页面、目录索引、数据表格的信息密集展示。"
                    ),
                    "points": _format_points(
                        [f"五维深度分析：{category}赛道全景", "操作手册：从选品到变现完整路径", "数据对标：同品类竞品分析"]
                    ),
                    "aux_poetry": "这只是冰山一角，完整版远比你看到的多。",
                }
                )
            ),
        },
    ]
    return pages, findings


def generate_via_codex(prompt: str, output_path: Path, page_num: int = 0) -> bool:
    """用 Codex 子代理生图。成功时图片已写到 output_path。"""
    companion = shutil.which("codex-companion")
    label = f"第 {page_num} 张" if page_num else "图片"
    companion_cmd: list[str] | None = None
    if companion:
        print(f"codex-companion 路径：{companion}", file=sys.stderr)
        companion_cmd = [companion]
    else:
        root = Path.home() / ".claude/plugins/cache/openai-codex"
        candidates = sorted(
            root.glob("*/*/scripts/codex-companion.mjs"),
            key=lambda path: path.parent.parent.name,
        )
        if candidates:
            mjs_path = candidates[-1]
            print(f"codex-companion 路径：{mjs_path}", file=sys.stderr)
            companion_cmd = ["node", str(mjs_path)]

    if not companion_cmd:
        print("codex-companion 未找到，fallback 到 API", file=sys.stderr)
        return False

    prompt_path = Path(f"/tmp/allin_img_prompt_{page_num or int(time.time())}.txt")
    prompt_path.write_text(prompt, encoding="utf-8")
    task = (
        f"读取 {prompt_path} 的提示词，用 gpt-image-2 生成一张 1024x1536 竖版图片，"
        f"将图片保存到 {output_path}。只完成生图和保存，不修改其他文件。"
    )
    try:
        result = subprocess.run(
            [*companion_cmd, "task", task],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:
        print(f"warn: {label} Codex 失败：{exc}")
        return False
    finally:
        prompt_path.unlink(missing_ok=True)

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip().splitlines()
        print(f"warn: {label} Codex 失败：{msg[-1] if msg else 'unknown error'}")
        return False
    if output_path.exists() and output_path.stat().st_size > MIN_IMAGE_BYTES:
        return True

    print(f"warn: {label} Codex 未产出有效图片")
    return False


def generate_image(
    prompt: str,
    output_path: Path,
    size: str = "1024x1536",
    api_key: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
    retry: int = 3,
    page_num: int = 0,
) -> bool:
    """Codex 优先，失败后调用图片 API，保存到 output_path。"""
    failures = 0
    prefer_api = os.environ.get("IMAGE_GEN_PREFER_API", "").lower() in {"1", "true", "yes", "on"}

    if not prefer_api:
        if generate_via_codex(prompt, output_path, page_num):
            print(f"ok: {output_path} ({output_path.stat().st_size // 1024} KB)")
            return True
        failures += 1

    cfg = load_image_config()
    key = api_key or cfg["key"]
    base_url = api_base or cfg["base_url"]
    image_model = model or cfg["model"]
    if not key:
        print("error: Codex 失败且缺少图片 API Key（config.json image_api.key 或 IMAGE_API_KEY 环境变量）")
        return False

    client = OpenAI(api_key=key, base_url=base_url)

    while failures < retry:
        attempt = failures
        try:
            resp = client.images.generate(
                model=image_model,
                prompt=prompt,
                n=1,
                size=size,
                timeout=300,
            )
            items = resp.data if hasattr(resp, "data") else resp.get("data", [])
            item = items[0]

            b64 = getattr(item, "b64_json", None) or (
                item.get("b64_json") if isinstance(item, dict) else None
            )
            url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else None)

            if b64:
                img_bytes = base64.b64decode(b64)
            elif url:
                with urllib.request.urlopen(url, timeout=60) as response:
                    img_bytes = response.read()
            else:
                raise ValueError("响应中无 b64_json 也无 url")

            output_path.write_bytes(img_bytes)
            print(f"ok: {output_path} ({len(img_bytes) // 1024} KB)")
            return True

        except Exception as exc:
            failures += 1
            if failures < retry:
                wait = 30 * (attempt + 1)
                print(f"retry: 第 {attempt + 1} 次失败（{exc}），{wait}s 后重试...")
                time.sleep(wait)
            else:
                print(f"error: 放弃（{exc}）")
    return False


def generate(prompt: str, output: str, size: str = "1024x1536", retry: int = 3) -> bool:
    """兼容入口：生成单张图片。"""
    return generate_image(prompt, Path(output), size=size, retry=retry)


def _safe_filename(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|\s]+', "_", text.strip())
    return text.strip("_") or "image"


def _print_prompts(pages: list[dict[str, Any]], findings: list[dict[str, str]]) -> None:
    print("\n" + "=" * 60)
    for page in pages:
        print(f"\n-- 第 {page['page_num']} 张：{page['title']}（核心隐喻词：{page['core_keyword']}） --")
        print(page["prompt"])
    if findings:
        print("\n-- 发现清单 --")
        for item in findings:
            print(f"{item['file']}:{item['line']} - {item['description']} - {item['owner']}")


def _load_record_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.record_json:
        return normalize_record(load_json(args.record_json))
    if args.record_id:
        return get_record(load_config(), args.record_id)
    raise SystemExit("error: 商品拆解模式需要 --record-id 或 --record-json")


def _generate_one_page(page: dict[str, Any], output: Path, size: str) -> tuple[int, str, str | None, float]:
    start = time.time()
    ok = generate_image(page["prompt"], output, size=size, page_num=page["page_num"])
    elapsed = time.time() - start
    return page["page_num"], page["title"], str(output) if ok else None, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="生成商品拆解笔记图片（V2 模板）")
    parser.add_argument("--prompt", help="兼容模式：直接传单张图片提示词")
    parser.add_argument("--output", help="兼容模式：单张图片输出路径")
    parser.add_argument("--size", default="1024x1536", help="图片尺寸（默认竖版 1024x1536）")
    parser.add_argument("--record-id", help="商品调研记录 record_id")
    parser.add_argument("--record-json", help="离线商品调研记录 JSON")
    parser.add_argument("--analysis", help="五维分析 JSON，可包含 five_dim/markdown/content 字段")
    parser.add_argument("--output-dir", default="/tmp", help="批量生成输出目录")
    parser.add_argument("--prompts-only", action="store_true", help="只打印 4 张提示词，不调 API")
    parser.add_argument("--dry-run", action="store_true", help="等同 --prompts-only")
    args = parser.parse_args()

    if args.prompt or args.output:
        if not args.prompt or not args.output:
            raise SystemExit("error: --prompt 和 --output 必须同时提供")
        ok = generate(args.prompt, args.output, args.size)
        sys.exit(0 if ok else 1)

    record = _load_record_from_args(args)
    analysis = load_json(args.analysis) if args.analysis else {}
    pages, findings = build_product_breakdown_prompts(record, analysis)

    if args.prompts_only or args.dry_run:
        _print_prompts(pages, findings)
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    product_name = _first(record, "商品名称", "产品名称", "标题", "title", default="product")

    generated_by_page: dict[int, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for page in pages:
            output = output_dir / (
                f"sketchnote_{_safe_filename(product_name)}_{page['page_num']:02d}_{page['title']}.png"
            )
            futures[executor.submit(_generate_one_page, page, output, args.size)] = page

        completed = 0
        for future in concurrent.futures.as_completed(futures):
            page = futures[future]
            completed += 1
            try:
                page_num, title, result, elapsed = future.result()
            except Exception as exc:
                page_num, title, result, elapsed = page["page_num"], page["title"], None, 0.0
                print(f"error: 第 {page_num} 张异常（{exc}）")
            print(f"[完成] {completed}/{len(pages)} — {title} (耗时 {elapsed:.0f}s)")
            if result:
                generated_by_page[page_num] = result

    generated = [generated_by_page[page["page_num"]] for page in pages if page["page_num"] in generated_by_page]

    print(f"\n完成：{len(generated)}/{len(pages)} 张 -> {output_dir}")
    for path in generated:
        print(f"  {path}")
    if findings:
        print("\n发现清单：")
        for item in findings:
            print(f"- {item['file']}:{item['line']} - {item['description']} - {item['owner']}")
    sys.exit(0 if len(generated) == len(pages) else 1)


if __name__ == "__main__":
    main()
