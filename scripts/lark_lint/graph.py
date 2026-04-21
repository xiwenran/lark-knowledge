from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Page:
    path: Path
    rel_path: str
    stem_path: str
    title: str
    frontmatter: dict[str, Any]
    body: str
    raw_text: str
    wikilinks: list[str]

    @property
    def parent_dir(self) -> str:
        parent = Path(self.rel_path).parent.as_posix()
        return "" if parent == "." else parent

    @property
    def top_level_dir(self) -> str:
        parts = Path(self.rel_path).parts
        return parts[0] if len(parts) > 1 else ""

    @property
    def page_type(self) -> str:
        value = self.frontmatter.get("type")
        return str(value).strip() if value is not None else ""
