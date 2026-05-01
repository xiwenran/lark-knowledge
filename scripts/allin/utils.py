#!/usr/bin/env python3
"""
utils.py — All In Podcast 脚本共享工具函数

统一处理：
- lark-cli 命令调用（带错误处理）
- 飞书收件表记录读取
- 双语解析（Doubao 输出格式 → [{speaker, en, zh}]）
- 五维分析提取
"""

import json
import re
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


def _strip_dim_heading(text: str) -> str:
    """去掉维度内容开头的冗余章节标题行。

    Sonnet 有时会在正文内容前加「一、本期议题：」这类子标题行，
    与模板已有的 ### 标题重复，也会导致概览 callout 里"议题"字样叠加。
    只去首行，且只匹配「中文序数 + 顿号 + 短标题」格式，不动正文内容。
    """
    return re.sub(
        r'^[一二三四五六七八九十][、，.]\s*[^\n：:]{0,20}[：:]?\s*\n',
        '', text, count=1
    ).strip()


def extract_dim(text: str, marker: str) -> str:
    """从五维分析文本提取单个维度内容，兼容两种 AI 输出格式：
    格式1（内容在下一行）：① 议题背景\\n内容...
    格式2（内容在同行）： ① 议题背景：内容...

    自动去掉 Sonnet 有时加在正文前的「一、本期议题：」冗余标题行。
    """
    m = re.search(rf'{marker}[^\n]*\n(.*?)(?=①|②|③|④|⑤|\Z)', text, re.DOTALL)
    if m and m.group(1).strip():
        return _strip_dim_heading(m.group(1).strip())
    m = re.search(rf'{marker}[^：:\n]*[：:]\s*(.+?)(?=\s*[①②③④⑤]|\Z)', text, re.DOTALL)
    return _strip_dim_heading(m.group(1).strip()) if m else ''


def parse_bilingual_turns(text: str) -> list:
    """解析 Doubao 双语输出，返回 [{speaker, en, zh}]

    支持的 EN 行格式（Doubao-seed-2.0-pro 实际输出）：
      > Speaker: EN text        （无加粗）
      > **Speaker**: EN text    （有加粗，兼容旧格式）
      > >>: EN text             （无法判断说话人，归一化为"主播"）
    ZH 行格式：**Speaker**：ZH text
    """
    turns = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # EN 行：> [**]说话人[**]: text（说话人 ≤30 字，支持 >>）
        en_m = re.match(r'>\s*\*{0,2}([^*:\n]{1,30}?)\*{0,2}\s*[：:]\s*(.*)', line)
        if en_m:
            speaker_en = en_m.group(1).strip()
            en_text = en_m.group(2).strip()
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or nxt.startswith('>') or nxt.startswith('**'):
                    break
                en_text += ' ' + nxt
                j += 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            zh_text = ''
            speaker = speaker_en
            if j < len(lines):
                zh_m = re.match(r'\*\*([^*]+)\*\*[：:]\s*(.*)', lines[j].strip())
                if zh_m:
                    speaker = zh_m.group(1).strip()
                    zh_text = zh_m.group(2).strip()
                    k = j + 1
                    while k < len(lines):
                        nxt = lines[k].strip()
                        if not nxt or nxt.startswith('>') or nxt.startswith('**'):
                            break
                        zh_text += ' ' + nxt
                        k += 1
                    j = k
            speaker = re.sub(r'[：:]\s*$', '', speaker).strip()
            if speaker == '>>':
                speaker = '主播'
            turns.append({'speaker': speaker, 'en': en_text.strip(), 'zh': zh_text.strip()})
            i = j
        else:
            i += 1
    return turns


def parse_views_wan(views) -> str:
    """播放量转万字符串，支持整数/字符串/带逗号格式，< 1万时显示原始数字"""
    try:
        v = int(str(views).replace(',', '').replace('，', ''))
        return f"{v // 10000}万" if v >= 10000 else str(v)
    except (ValueError, TypeError):
        return '?万'
