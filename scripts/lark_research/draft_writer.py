"""Write research markdown drafts into Feishu pending-review storage only."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


CONFIG_CANDIDATES = (
    Path("config.json"),
    Path("~/.agents/skills/lark-knowledge-config/config.json").expanduser(),
)


def fail(message: str) -> "NoReturn":
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a Claude-refined research draft to Feishu pending-review storage."
    )
    parser.add_argument(
        "markdown_file",
        nargs="?",
        type=Path,
        help="Optional markdown file path. If omitted, read markdown from stdin.",
    )
    parser.add_argument("--config", type=Path, help="Path to config.json.")
    parser.add_argument("--title", help="Optional draft title override.")
    return parser.parse_args(argv)


def resolve_config_path(explicit_path: Path | None) -> Path:
    if explicit_path:
        resolved = explicit_path.expanduser().resolve()
        if not resolved.exists():
            fail(f"config.json 不存在: {resolved}")
        return resolved

    env_path = os.environ.get("LARK_KNOWLEDGE_CONFIG")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if not resolved.exists():
            fail(f"LARK_KNOWLEDGE_CONFIG 指向的 config.json 不存在: {resolved}")
        return resolved

    for candidate in CONFIG_CANDIDATES:
        resolved = candidate.expanduser().resolve()
        if resolved.exists():
            return resolved
    fail("config.json not found. Use --config or LARK_KNOWLEDGE_CONFIG.")


def load_config(config_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail(f"读取 config.json 失败: {exc}")
    except json.JSONDecodeError as exc:
        fail(f"config.json 解析失败: {exc}")
    if not isinstance(data, dict):
        fail("config.json 顶层必须是对象。")
    return data


def read_markdown(path: Path | None) -> str:
    try:
        raw = path.read_text(encoding="utf-8") if path else sys.stdin.read()
    except OSError as exc:
        fail(f"读取 markdown 草稿失败: {exc}")
    markdown = raw.strip()
    if not markdown:
        fail("未提供 markdown 草稿。请传入文件路径或通过 stdin 输入。")
    return markdown


def extract_title(markdown: str, override: str | None) -> str:
    if override and override.strip():
        return override.strip()
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        heading = re.sub(r"^#+\s*", "", stripped).strip()
        return heading[:120] if heading else "研究草稿"
    return "研究草稿"


def run_lark_cli(args: list[str]) -> Any:
    result = subprocess.run(args, capture_output=True, text=True)
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    payload = stdout or stderr
    if result.returncode != 0:
        raise RuntimeError(payload or "lark-cli command failed")
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return payload


def extract_record_id(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("record_id", "recordId", "id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for nested_key in ("data", "record"):
            nested = payload.get(nested_key)
            record_id = extract_record_id(nested)
            if record_id:
                return record_id
    if isinstance(payload, list):
        for item in payload:
            record_id = extract_record_id(item)
            if record_id:
                return record_id
    return ""


def cleanup_record(base_token: str, table_id: str, record_id: str) -> None:
    if not record_id:
        return
    try:
        run_lark_cli(
            [
                "lark-cli",
                "base",
                "+record-delete",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--record-id",
                record_id,
                "--yes",
            ]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 清理部分写入失败，请手动删除记录 {record_id}: {exc}", file=sys.stderr)


def write_to_table(config: dict[str, Any], title: str, markdown: str) -> Any:
    base = config.get("base")
    if not isinstance(base, dict):
        fail("config.json 缺少 base 配置，无法写入 research_draft_table_id。")

    base_token = str(base.get("base_token", "")).strip()
    table_id = str(config.get("research_draft_table_id", "")).strip()
    if not base_token:
        fail("config.json 缺少 base.base_token，无法写入待确认草稿表。")
    if not table_id:
        fail("config.json 缺少 research_draft_table_id。")

    payload = {
        "标题": title,
        "草稿正文": markdown,
    }

    created_record_id = ""
    try:
        response = run_lark_cli(
            [
                "lark-cli",
                "base",
                "+record-upsert",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--json",
                json.dumps(payload, ensure_ascii=False),
            ]
        )
        created_record_id = extract_record_id(response)
        return response
    except Exception as exc:  # noqa: BLE001
        cleanup_record(base_token, table_id, created_record_id)
        fail(f"飞书待确认表写入失败: {exc}")


def build_doc_append_markdown(title: str, markdown: str) -> str:
    return (
        "\n\n---\n\n"
        f"## 待确认草稿：{title}\n\n"
        f"{markdown}\n\n"
        "> 来源：lark-knowledge-research。人工确认后，方可执行 lark-knowledge-upgrade。\n"
    )


def write_to_node(config: dict[str, Any], title: str, markdown: str) -> Any:
    node_token = str(config.get("research_draft_node_token", "")).strip()
    if not node_token:
        fail("config.json 缺少 research_draft_node_token。")

    try:
        return run_lark_cli(
            [
                "lark-cli",
                "docs",
                "+update",
                "--doc",
                node_token,
                "--mode",
                "append",
                "--markdown",
                build_doc_append_markdown(title, markdown),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        fail(f"飞书待确认文档写入失败: {exc}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    markdown = read_markdown(args.markdown_file)
    title = extract_title(markdown, args.title)
    config_path = resolve_config_path(args.config)
    config = load_config(config_path)

    if not str(config.get("research_draft_table_id", "")).strip() and not str(
        config.get("research_draft_node_token", "")
    ).strip():
        fail("请在 config.json 中配置 research_draft_table_id 或 research_draft_node_token")

    # 安全边界：草稿一律写入待确认区，绝不写正式知识库。正式库写入需人工确认后执行 lark-knowledge-upgrade skill
    if str(config.get("research_draft_table_id", "")).strip():
        response = write_to_table(config, title, markdown)
        print(json.dumps({"destination": "research_draft_table_id", "response": response}, ensure_ascii=False, indent=2))
        return 0

    response = write_to_node(config, title, markdown)
    print(json.dumps({"destination": "research_draft_node_token", "response": response}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
