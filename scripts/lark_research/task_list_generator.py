"""Build research task bundles for the lark-knowledge research skeleton."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _draft_destination() -> dict[str, Any]:
    return {
        "mode": "pending_review",
        "configured": False,
        "target": "config.json: research.pending_review",
        "note": "P1-C skeleton only; actual Feishu writeback lands in P1-D.",
    }


def _research_question(topic: str) -> str:
    return f"围绕“{topic}”应补哪些可复用知识？"


def _search_brief(topic: str, blank_type: str) -> str:
    return (
        f"P1-D 将围绕主题“{topic}”和空白类型“{blank_type}”"
        "生成 Tavily 查询并补充来源。"
    )


def build_task_bundle(blanks: list[dict[str, Any]]) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for index, blank in enumerate(blanks, start=1):
        topic = str(blank.get("topic", "")).strip()
        if not topic:
            continue
        blank_type = str(blank.get("blank_type", "lint_gap")).strip() or "lint_gap"
        priority = str(blank.get("priority", "medium")).strip() or "medium"
        source = str(blank.get("source", "lark-knowledge-lint")).strip() or "lark-knowledge-lint"
        evidence = blank.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]

        tasks.append(
            {
                "task_id": f"research-{index:03d}",
                "topic": topic,
                "source": source,
                "blank_type": blank_type,
                "priority": priority,
                "research_question": _research_question(topic),
                "search_brief": _search_brief(topic, blank_type),
                "supporting_evidence": [str(item) for item in evidence if str(item).strip()],
                "signals": blank.get("signals", []),
                "related_records": blank.get("related_records", []),
                "suggested_topic_owner": blank.get("suggested_topic_owner"),
                "draft_destination": _draft_destination(),
                "status": "identified",
            }
        )

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "task_count": len(tasks),
        "tasks": tasks,
    }


def build_markdown(bundle: dict[str, Any]) -> str:
    lines = [
        "# 研究任务清单",
        "",
        f"- 生成时间：{bundle['generated_at']}",
        f"- 任务数量：{bundle['task_count']}",
        "- 状态说明：本期只完成空白识别与任务清单生成，未调用 Tavily API。",
        "",
    ]

    tasks = bundle.get("tasks", [])
    if not tasks:
        lines.append("暂无可生成的研究任务。")
        lines.append("")
        return "\n".join(lines)

    for index, task in enumerate(tasks, start=1):
        lines.extend(
            [
                f"## {index}. {task['topic']}",
                f"- 来源：{task['source']}",
                f"- 空白类型：{task['blank_type']}",
                f"- 优先级：{task['priority']}",
                f"- 研究问题：{task['research_question']}",
                f"- 搜索说明：{task['search_brief']}",
                f"- 待确认区目标：{task['draft_destination']['target']}",
                f"- 状态：{task['status']}",
            ]
        )
        evidence = task.get("supporting_evidence", [])
        if evidence:
            lines.append("- 支撑证据：")
            for item in evidence:
                lines.append(f"  - {item}")
        lines.append("")

    return "\n".join(lines)
