"""Identify research blanks from lint output or manual topics.

P1-C only implements blank identification and task list generation.
No search API or Feishu writeback happens in this phase.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from task_list_generator import build_markdown, build_task_bundle


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Lint JSON must be a top-level object.")
    return data


def _load_markdown_topics(path: Path) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    numbered_pattern = re.compile(r"^\d+\.\s+(?P<topic>.+)$")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "+ ")):
            topic = line[2:].strip()
        else:
            match = numbered_pattern.match(line)
            topic = match.group("topic").strip() if match else ""
        if not topic:
            continue
        topics.append(
            {
                "topic": topic,
                "blank_type": "markdown_gap",
                "priority": "medium",
                "signals": ["markdown_list"],
                "evidence": ["Imported from lint markdown list."],
            }
        )
    return topics


def _normalize_lint_blanks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_blanks = payload.get("blanks", [])
    if not isinstance(raw_blanks, list):
        raise ValueError("Lint JSON field 'blanks' must be a list.")

    normalized: list[dict[str, Any]] = []
    for item in raw_blanks:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "")).strip()
        if not topic:
            continue
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        normalized.append(
            {
                "topic": topic,
                "blank_type": str(item.get("blank_type", "lint_gap")).strip() or "lint_gap",
                "priority": str(item.get("priority", "medium")).strip() or "medium",
                "signals": item.get("signals", []),
                "evidence": [str(entry) for entry in evidence if str(entry).strip()],
                "related_records": item.get("related_records", []),
                "suggested_topic_owner": item.get("suggested_topic_owner"),
                "source": str(payload.get("source", "lark-knowledge-lint")).strip()
                or "lark-knowledge-lint",
            }
        )
    return normalized


def _manual_topics(topics: list[str]) -> list[dict[str, Any]]:
    manual_items: list[dict[str, Any]] = []
    for topic in topics:
        cleaned = topic.strip()
        if not cleaned:
            continue
        manual_items.append(
            {
                "topic": cleaned,
                "blank_type": "manual_gap",
                "priority": "medium",
                "signals": ["manual_topic"],
                "evidence": ["manual topic provided by user"],
                "source": "manual_topic",
            }
        )
    return manual_items


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate structured research tasks from lint blanks or manual topics."
    )
    parser.add_argument("--lint-json", type=Path, help="Path to lint JSON output.")
    parser.add_argument("--lint-markdown", type=Path, help="Path to lint markdown output.")
    parser.add_argument(
        "--topic",
        action="append",
        default=[],
        help="Manual topic to turn into a research task. Can be used multiple times.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional output path for research task JSON.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        help="Optional output path for research task markdown.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if not args.lint_json and not args.lint_markdown and not args.topic:
        raise SystemExit("Provide --lint-json, --lint-markdown, or at least one --topic.")

    blanks: list[dict[str, Any]] = []
    if args.lint_json:
        blanks.extend(_normalize_lint_blanks(_load_json(args.lint_json)))
    if args.lint_markdown:
        blanks.extend(_load_markdown_topics(args.lint_markdown))
    blanks.extend(_manual_topics(args.topic))

    bundle = build_task_bundle(blanks)
    markdown = build_markdown(bundle)
    json_text = json.dumps(bundle, ensure_ascii=False, indent=2)

    if args.json_out:
        args.json_out.write_text(json_text + "\n", encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.write_text(markdown, encoding="utf-8")

    print(json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
