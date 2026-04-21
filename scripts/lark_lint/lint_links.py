from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from graph import Page
from nx_compat import nx
from signals import suggest_links


CONFIG_CANDIDATES = (
    Path("config.json"),
    Path("~/.agents/skills/lark-knowledge-config/config.json").expanduser(),
)
RELATED_SECTION_RE = re.compile(r"^##\s+相关词条\s*$", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
DOC_TOKEN_RE = re.compile(r"/(?:docx|docs|wiki)/([A-Za-z0-9]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate read-only link suggestions from Lark Base records.")
    parser.add_argument("--config", type=Path, help="Path to config.json. Defaults to repo config, then ~/.agents path.")
    parser.add_argument("--top-n", type=int, default=50, help="Number of suggestions to print. Default: 50.")
    parser.add_argument("--page-size", type=int, default=100, help="Pagination size for lark-cli record listing.")
    return parser.parse_args()


def resolve_config_path(explicit_path: Path | None) -> Path:
    if explicit_path:
        return explicit_path.expanduser().resolve()

    env_path = os.environ.get("LARK_KNOWLEDGE_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()

    for candidate in CONFIG_CANDIDATES:
        resolved = candidate.expanduser().resolve()
        if resolved.exists():
            return resolved
    raise FileNotFoundError("config.json not found. Use --config or LARK_KNOWLEDGE_CONFIG.")


def load_config(config_path: Path) -> dict[str, Any]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    try:
        base = data["base"]
        _ = base["base_token"]
        _ = base["table_id"]
    except KeyError as exc:
        raise KeyError(f"Missing required config field: {exc}") from exc
    return data


def run_lark_cli(args: list[str]) -> Any:
    result = subprocess.run(args, capture_output=True, text=True)
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    payload = stdout or stderr
    if result.returncode != 0:
        raise RuntimeError(payload or "lark-cli command failed")
    if not payload:
        raise RuntimeError("lark-cli returned empty output")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli returned non-JSON output: {payload[:200]}") from exc


def unwrap_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("items", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("items", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def extract_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "name", "title", "value", "link"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""
    if isinstance(value, list):
        parts = [extract_scalar(item) for item in value]
        parts = [item for item in parts if item]
        return " / ".join(parts)
    return str(value).strip()


def extract_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            scalar = extract_scalar(item)
            if scalar:
                items.append(scalar)
        return items
    scalar = extract_scalar(value)
    if not scalar:
        return []
    return [part.strip() for part in re.split(r"[,/;；、\n]+", scalar) if part.strip()]


def record_id_of(record: dict[str, Any]) -> str:
    for key in ("record_id", "recordId", "id"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def record_fields(record: dict[str, Any]) -> dict[str, Any]:
    fields = record.get("fields")
    return fields if isinstance(fields, dict) else {}


def list_all_records(base_token: str, table_id: str, page_size: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    while True:
        payload = run_lark_cli(
            [
                "lark-cli",
                "base",
                "+record-list",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--limit",
                str(page_size),
                "--offset",
                str(offset),
            ]
        )
        batch = unwrap_records(payload)
        if not batch:
            break
        records.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return records


def doc_token_from_link(link: str) -> str:
    if not link:
        return ""
    match = DOC_TOKEN_RE.search(link)
    return match.group(1) if match else ""


def fetch_doc_markdown(link: str) -> str:
    payload = run_lark_cli(["lark-cli", "docs", "+fetch", "--doc", link, "--format", "markdown"])
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("markdown", "content", "text"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
        for key in ("markdown", "content", "text"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
    raise RuntimeError("Unable to extract markdown from docs +fetch output")


def extract_related_links(markdown: str) -> list[tuple[str, str]]:
    match = RELATED_SECTION_RE.search(markdown)
    if not match:
        return []

    remainder = markdown[match.end():]
    lines: list[str] = []
    for line in remainder.splitlines():
        if line.startswith("## "):
            break
        lines.append(line)

    section = "\n".join(lines)
    return [(title.strip(), url.strip()) for title, url in MARKDOWN_LINK_RE.findall(section)]


def normalize_record(record: dict[str, Any]) -> dict[str, Any] | None:
    record_id = record_id_of(record)
    fields = record_fields(record)
    title = extract_scalar(fields.get("标题"))
    if not record_id or not title:
        return None

    topics = extract_list(fields.get("专题归属"))
    asset_type = extract_scalar(fields.get("资产形态"))
    page_link = extract_scalar(fields.get("知识库页面链接"))

    return {
        "record_id": record_id,
        "title": title,
        "topics": topics,
        "asset_type": asset_type,
        "page_link": page_link,
        "page_token": doc_token_from_link(page_link),
    }


def build_pages(records: list[dict[str, Any]]) -> dict[str, Page]:
    pages: dict[str, Page] = {}
    for record in records:
        top_dir = record["topics"][0] if record["topics"] else "未分类"
        rel_path = f"{top_dir}/{record['title']}"
        pages[record["record_id"]] = Page(
            path=Path(record["record_id"]),
            rel_path=rel_path,
            stem_path=record["record_id"],
            title=record["title"],
            frontmatter={"type": record["asset_type"]},
            body="",
            raw_text="",
            wikilinks=[],
        )
    return pages


def resolve_target(
    title: str,
    link: str,
    by_token: dict[str, str],
    by_link: dict[str, str],
    by_title: dict[str, list[str]],
) -> str | None:
    if link in by_link:
        return by_link[link]
    token = doc_token_from_link(link)
    if token and token in by_token:
        return by_token[token]

    title_matches = by_title.get(title, [])
    if len(title_matches) == 1:
        return title_matches[0]
    return None


def build_graph(records: list[dict[str, Any]]) -> tuple[nx.DiGraph, dict[str, Page]]:
    pages = build_pages(records)
    graph = nx.DiGraph()

    for record_id, page in pages.items():
        graph.add_node(record_id, page=page)

    by_token = {record["page_token"]: record["record_id"] for record in records if record["page_token"]}
    by_link = {record["page_link"]: record["record_id"] for record in records if record["page_link"]}
    by_title: dict[str, list[str]] = {}
    for record in records:
        by_title.setdefault(record["title"], []).append(record["record_id"])

    for record in records:
        if not record["page_link"]:
            continue
        markdown = fetch_doc_markdown(record["page_link"])
        for title, link in extract_related_links(markdown):
            target = resolve_target(title, link, by_token, by_link, by_title)
            if not target or target == record["record_id"]:
                continue
            graph.add_edge(record["record_id"], target)
    return graph, pages


def render_table(rows: list[list[str]]) -> str:
    headers = ["排名", "节点A", "节点B", "四信号得分", "推荐理由"]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def format_row(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells))

    divider = "-+-".join("-" * width for width in widths)
    lines = [format_row(headers), divider]
    lines.extend(format_row(row) for row in rows)
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if args.top_n <= 0:
        raise SystemExit("--top-n must be > 0")

    config_path = resolve_config_path(args.config)
    config = load_config(config_path)
    base_token = str(config["base"]["base_token"])
    table_id = str(config["base"]["table_id"])

    normalized_records = [
        item
        for item in (normalize_record(record) for record in list_all_records(base_token, table_id, args.page_size))
        if item is not None
    ]

    graph, pages = build_graph(normalized_records)
    suggestions = suggest_links(graph, pages, top_n=args.top_n)

    print("补链建议报告")
    print(f"配置文件: {config_path.name}")
    print(f"记录数: {len(normalized_records)} | 已识别关系数: {graph.number_of_edges()} | 输出 Top N: {args.top_n}")
    print("")

    if not suggestions:
        print("本次没有生成补链建议。")
        return 0

    rows: list[list[str]] = []
    for index, item in enumerate(suggestions, start=1):
        rows.append(
            [
                str(index),
                item["title_a"],
                item["title_b"],
                f"{item['score']:.2f}",
                "；".join(item["reasons"]),
            ]
        )

    print(render_table(rows))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
