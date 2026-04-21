"""Configuration placeholders for the research workflow."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchConfigStatus:
    tavily_api_key_present: bool
    env_var_name: str = "TAVILY_API_KEY"
    draft_table_config_key: str = "research_draft_table_id"
    draft_node_config_key: str = "research_draft_node_token"
    output_dir_config_key: str = "research.output_dir"


def get_config_status() -> ResearchConfigStatus:
    return ResearchConfigStatus(
        tavily_api_key_present=bool(os.getenv("TAVILY_API_KEY")),
    )


def require_tavily_env() -> None:
    if not os.getenv("TAVILY_API_KEY"):
        raise EnvironmentError("Missing environment variable: TAVILY_API_KEY")


CONFIG_GUIDE = {
    "env": {
        "TAVILY_API_KEY": "Tavily 检索密钥，运行 tavily_search.py 前必须设置。",
    },
    "config_json": {
        "research_draft_table_id": "待确认草稿表 table_id；配置后 draft_writer.py 将写入多维表格。",
        "research_draft_node_token": "待确认草稿文档 node_token；未配置表格时，draft_writer.py 将 append 到该文档。",
        "research.output_dir": "可选，本地 research 中间产物输出目录。",
    },
}
