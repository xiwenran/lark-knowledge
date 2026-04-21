"""Configuration placeholders for the research skeleton.

P1-C only validates that env-based configuration is present when requested.
No secrets are stored here and no API is called from this module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchConfigStatus:
    tavily_api_key_present: bool
    env_var_name: str = "TAVILY_API_KEY"
    pending_review_config_key: str = "research.pending_review"
    output_dir_config_key: str = "research.output_dir"


def get_config_status() -> ResearchConfigStatus:
    return ResearchConfigStatus(
        tavily_api_key_present=bool(os.getenv("TAVILY_API_KEY")),
    )


def require_tavily_env() -> None:
    """Reserved for P1-D integration checks."""
    if not os.getenv("TAVILY_API_KEY"):
        raise EnvironmentError("Missing environment variable: TAVILY_API_KEY")
