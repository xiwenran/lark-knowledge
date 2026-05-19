from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = ROOT / "scripts" / "lark_research"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from source_planner import build_plan, build_queries, main


class SourcePlannerTests(unittest.TestCase):
    def sample_payload(self) -> dict:
        return {
            "tasks": [
                {
                    "task_id": "gap-001",
                    "topic": "小红书引流",
                    "source": "lint",
                    "blank_type": "missing_topic",
                    "priority": "high",
                    "research_question": "小红书引流 SOP 怎么做",
                    "supporting_evidence": ["知识库缺少案例"],
                }
            ]
        }

    def test_build_queries_prioritizes_feishu_public_knowledge(self) -> None:
        queries = build_queries("小红书引流", "小红书引流 SOP 怎么做", "知识库缺少案例")

        self.assertIn("site:docs.feishu.cn 小红书引流", queries["feishu_public_knowledge"])
        self.assertIn("site:open.feishu.cn 小红书引流", queries["official_sources"])
        self.assertIn("小红书引流 最佳实践 案例 教程", queries["tavily_optional"])

    def test_build_plan_keeps_manual_url_and_tavily_optional(self) -> None:
        plan = build_plan(
            self.sample_payload(),
            manual_urls=["https://ask.feishu.cn/shared-space/center"],
            max_tasks=5,
        )

        self.assertEqual(plan["task_count"], 1)
        task = plan["tasks"][0]
        self.assertEqual(task["manual_urls"], ["https://ask.feishu.cn/shared-space/center"])
        self.assertIn("tavily_optional", task["source_queries"])
        self.assertIn("没有 Tavily API 额度时跳过 tavily_optional，不阻塞流程。", task["draft_requirements"])

    def test_cli_writes_json_and_markdown_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            tasks_path = base / "tasks.json"
            json_out = base / "plan.json"
            markdown_out = base / "plan.md"
            tasks_path.write_text(json.dumps(self.sample_payload(), ensure_ascii=False), encoding="utf-8")

            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "--tasks-json",
                        str(tasks_path),
                        "--manual-url",
                        "https://ask.feishu.cn/shared-space/center",
                        "--json-out",
                        str(json_out),
                        "--markdown-out",
                        str(markdown_out),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("site:docs.feishu.cn 小红书引流", json_out.read_text(encoding="utf-8"))
            markdown = markdown_out.read_text(encoding="utf-8")
            self.assertIn("主来源：飞书公共知识库", markdown)
            self.assertIn("https://ask.feishu.cn/shared-space/center", markdown)


if __name__ == "__main__":
    unittest.main()
