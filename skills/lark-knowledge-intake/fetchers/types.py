from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FetchResult:
    # 统一抓取返回契约，P11.1 阶段允许正文为空。
    markdown: str | None = None
    title: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    source_type: str = "fallback"
    url_or_path: str = ""
    success: bool = False
    error: str | None = None
