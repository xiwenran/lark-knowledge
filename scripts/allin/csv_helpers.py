"""
csv_helpers.py — CSV 原子读写封装，供 run_intake_batch.py / run_transcript_batch.py 复用。

所有写操作均通过 临时文件 + os.replace 保证原子性，避免写入中途崩溃损坏状态文件。

CSV 字段顺序（与 enumerate_channel.py 保持一致）:
    video_id, title, duration_sec, duration_min, upload_date, category,
    intake_status, transcript_status, record_id, feishu_page_url,
    error_reason, last_updated

典型用法:
    from csv_helpers import load_inventory, update_row, iter_pending, count_by_status

    rows = load_inventory('data/allin_channel_inventory.csv')
    update_row('data/allin_channel_inventory.csv', 'VIDEO_ID', {
        'intake_status': 'done', 'record_id': 'rec_xxx'
    })
    for row in iter_pending('data/allin_channel_inventory.csv', phase='intake'):
        print(row['video_id'], row['title'])
"""

import csv
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional

CSV_FIELDS = [
    "video_id",
    "title",
    "duration_sec",
    "duration_min",
    "upload_date",
    "category",
    "intake_status",
    "transcript_status",
    "record_id",
    "feishu_page_url",
    "error_reason",
    "last_updated",
]


def _resolve(csv_path) -> Path:
    return Path(csv_path).expanduser().resolve()


def load_inventory(csv_path) -> List[Dict]:
    """加载 CSV 为 dict 列表。文件不存在时返回空列表。"""
    p = _resolve(csv_path)
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def get_row(csv_path, video_id: str) -> Optional[Dict]:
    """按 video_id 查一行，找不到返回 None。"""
    for row in load_inventory(csv_path):
        if row.get("video_id") == video_id:
            return row
    return None


def update_row(csv_path, video_id: str, updates: Dict) -> bool:
    """
    原子更新某行。
    - 找到 video_id 对应行后，把 updates 里的键值合并进去，同时更新 last_updated。
    - 返回 True 表示找到并更新成功，False 表示 video_id 不存在（不修改文件）。
    - 写操作用 tempfile + os.replace 保证原子性。
    """
    p = _resolve(csv_path)
    rows = load_inventory(csv_path)
    found = False
    now_iso = datetime.now(timezone.utc).isoformat()

    for row in rows:
        if row.get("video_id") == video_id:
            row.update(updates)
            row["last_updated"] = now_iso
            found = True
            break

    if not found:
        return False

    _write_atomic(p, rows)
    return True


def _write_atomic(csv_path: Path, rows: List[Dict]) -> None:
    """将 rows 原子写入 csv_path（tempfile + os.replace）。"""
    # 临时文件和目标文件同目录，确保 os.replace 是同一挂载点的移动操作
    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        dir=csv_path.parent,
        delete=False,
        suffix=".tmp",
    ) as tmp_f:
        tmp_path = Path(tmp_f.name)
        writer = csv.DictWriter(
            tmp_f,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    try:
        os.replace(tmp_path, csv_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def count_by_status(csv_path) -> Dict:
    """
    返回按 category × intake/transcript 状态的计数字典，格式:
    {
        'episode': {
            'intake':     {'pending': N, 'done': N, 'failed': N, 'skipped': N},
            'transcript': {'pending': N, 'done': N, 'failed': N, 'skipped': N},
        },
        'interview': { ... },
        'clip':      { ... },
        'unknown':   { ... },
        '_total':    {'intake': {...}, 'transcript': {...}},
    }
    """
    STATUS_KEYS = ["pending", "done", "failed", "skipped"]
    CATEGORIES = ["episode", "interview", "clip", "unknown"]

    def empty_stat():
        return {k: 0 for k in STATUS_KEYS}

    result: Dict = {
        cat: {
            "intake": empty_stat(),
            "transcript": empty_stat(),
        }
        for cat in CATEGORIES
    }
    result["_total"] = {"intake": empty_stat(), "transcript": empty_stat()}

    for row in load_inventory(csv_path):
        cat = row.get("category", "unknown")
        if cat not in CATEGORIES:
            cat = "unknown"
        for phase in ("intake", "transcript"):
            status = row.get(f"{phase}_status", "pending")
            if status not in STATUS_KEYS:
                status = "pending"
            result[cat][phase][status] += 1
            result["_total"][phase][status] += 1

    return result


def iter_pending(
    csv_path,
    phase: str,
    category_filter: Optional[List[str]] = None,
) -> Iterator[Dict]:
    """
    迭代 phase_status == 'pending' 的行，按 upload_date 倒序（最新先）。

    phase:
        'intake'     — intake_status == 'pending'
        'transcript' — transcript_status == 'pending' AND intake_status == 'done'

    category_filter:
        None 或 [] 表示不过滤（全部分类）
        ['episode'] 只返回 episode 行
        ['episode', 'interview'] 返回两类

    Yields:
        dict，包含所有 CSV_FIELDS 字段，外加 'youtube_url' 便利字段
        (值为 https://www.youtube.com/watch?v={video_id})
    """
    if phase not in ("intake", "transcript"):
        raise ValueError(f"phase 必须是 'intake' 或 'transcript'，得到: {phase!r}")

    rows = load_inventory(csv_path)

    def sort_key(row):
        # upload_date 格式 YYYY-MM-DD，字典序即时间序
        return row.get("upload_date") or ""

    rows_sorted = sorted(rows, key=sort_key, reverse=True)  # 倒序 = 最新先

    for row in rows_sorted:
        # 分类过滤
        if category_filter:
            if row.get("category") not in category_filter:
                continue

        # phase 筛选
        if phase == "intake":
            if row.get("intake_status") != "pending":
                continue
        else:  # transcript
            if row.get("transcript_status") != "pending":
                continue
            if row.get("intake_status") != "done":
                continue

        # 注入便利字段
        vid = row.get("video_id", "")
        row_out = dict(row)
        row_out["youtube_url"] = (
            f"https://www.youtube.com/watch?v={vid}" if vid else ""
        )
        yield row_out
