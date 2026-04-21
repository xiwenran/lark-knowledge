from __future__ import annotations

import logging
from pathlib import Path


logger = logging.getLogger(__name__)

LOCAL_DIRECTORY = Path(__file__).resolve().parents[1] / ".local"


def load_local_credential(name: str) -> str | None:
    # 凭据文件统一放在 skill 的 .local 目录，缺失时静默返回 None。
    credential_name = name.strip()
    if not credential_name:
        logger.warning("Received empty credential name.")
        return None

    credential_path = LOCAL_DIRECTORY / credential_name
    if not credential_path.is_file():
        logger.debug("Local credential not found: %s", credential_path)
        return None

    return credential_path.read_text(encoding="utf-8").strip() or None


def local_path(name: str) -> Path:
    # 返回 .local 目录下的具体路径（不校验存在性，适合需要 Path 对象的场景，如 Playwright storage_state）。
    return LOCAL_DIRECTORY / name.strip()
