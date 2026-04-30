#!/usr/bin/env python3
"""
utils.py — All In Podcast 脚本共享工具函数

统一处理：
- lark-cli 命令调用（带错误处理）
- 飞书收件表记录读取
"""

import json
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".agents/skills/lark-knowledge-config/config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def safe_lark_run(cmd: list, action: str = "") -> dict | None:
    """
    执行 lark-cli 命令，统一处理错误。
    成功返回解析后的 dict；失败打印错误并返回 None。
    action: 用于错误信息的操作描述，如"读取收件表记录"
    """
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        if data.get("ok"):
            return data
        err = data.get("msg") or data.get("error") or result.stdout[:200]
        print(f"  ⚠️  {action or '飞书操作'}失败: {err}")
        return None
    except Exception:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        print(f"  ⚠️  {action or '飞书操作'}失败（非 JSON 响应）")
        if stderr:
            print(f"       stderr: {stderr[:200]}")
        if stdout:
            print(f"       stdout: {stdout[:200]}")
        return None


def get_record(config: dict, record_id: str) -> dict:
    """
    从飞书收件表读取记录，数组类型字段自动取第一个值。
    失败时打印错误并 sys.exit(1)。
    """
    data = safe_lark_run([
        "lark-cli", "base", "+record-get",
        "--base-token", config["all_in_podcast"]["base_token"],
        "--table-id", config["all_in_podcast"]["table_id"],
        "--record-id", record_id
    ], action=f"读取收件表记录 {record_id}")
    if data is None:
        print(f"  错误：无法读取 record_id={record_id}")
        print(f"  请检查：1) lark-cli 是否可用  2) token 是否过期  3) record_id 是否正确")
        sys.exit(1)
    raw = data["data"]["record"]
    normalized = {}
    for k, v in raw.items():
        normalized[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
    return normalized


def parse_views_wan(views) -> str:
    """播放量转万字符串，支持整数/字符串/带逗号格式，< 1万时显示原始数字"""
    try:
        v = int(str(views).replace(',', '').replace('，', ''))
        return f"{v // 10000}万" if v >= 10000 else str(v)
    except (ValueError, TypeError):
        return '?万'
