"""
enumerate_channel.py — 枚举 All In Podcast YouTube 频道全部视频并按时长三档分类。

典型用法:
    python scripts/allin/enumerate_channel.py
    python scripts/allin/enumerate_channel.py --dry-run
    python scripts/allin/enumerate_channel.py --limit 20
    python scripts/allin/enumerate_channel.py --limit 50 --dry-run
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CHANNEL_URL = "https://www.youtube.com/@allin/videos"

# 三档分类阈值（秒）
EPISODE_MIN_SEC = 3600   # > 3600s → episode
INTERVIEW_MIN_SEC = 600  # 600s < duration ≤ 3600s → interview
# ≤ 600s → clip（默认 skipped）

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

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # ~/lark-knowledge/
# 脚本位于 scripts/allin/，上溯三级到项目根
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def classify(duration_sec) -> tuple[str, str, str]:
    """按时长返回 (category, intake_status, transcript_status)。
    duration_sec 为 None 时归 unknown。
    """
    if duration_sec is None:
        return "unknown", "pending", "pending"
    if duration_sec > EPISODE_MIN_SEC:
        return "episode", "pending", "pending"
    if duration_sec > INTERVIEW_MIN_SEC:
        return "interview", "pending", "pending"
    return "clip", "skipped", "skipped"


def fetch_metadata(limit: int | None) -> list[dict]:
    """用 yt-dlp --flat-playlist --print-json 拉全量元数据，每行一个 JSON 对象。"""
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print-json",
        CHANNEL_URL,
    ]
    if limit is not None:
        cmd += ["--playlist-end", str(limit)]

    print(f"[enumerate] 正在从 YouTube 拉取元数据（URL: {CHANNEL_URL}）...")
    if limit:
        print(f"[enumerate] 调试模式：仅取前 {limit} 个视频")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"[ERROR] yt-dlp 退出码 {result.returncode}", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        sys.exit(1)

    videos = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            videos.append(obj)
        except json.JSONDecodeError as e:
            print(f"[WARN] JSON 解析失败，跳过一行: {e}", file=sys.stderr)
    return videos


def build_row(meta: dict, now_iso: str) -> dict:
    """从 yt-dlp 元数据构建一行 CSV 字典。"""
    video_id = meta.get("id") or meta.get("video_id") or ""
    title = meta.get("title") or ""

    raw_duration = meta.get("duration")
    duration_sec: int | None = None
    if raw_duration is not None:
        try:
            duration_sec = int(raw_duration)
        except (ValueError, TypeError):
            duration_sec = None

    duration_min = (
        round(duration_sec / 60, 1) if duration_sec is not None else ""
    )

    # upload_date 格式 YYYYMMDD → YYYY-MM-DD
    raw_date = meta.get("upload_date") or ""
    if raw_date and len(raw_date) == 8:
        upload_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
    else:
        upload_date = raw_date

    category, intake_status, transcript_status = classify(duration_sec)

    return {
        "video_id": video_id,
        "title": title,
        "duration_sec": duration_sec if duration_sec is not None else "",
        "duration_min": duration_min,
        "upload_date": upload_date,
        "category": category,
        "intake_status": intake_status,
        "transcript_status": transcript_status,
        "record_id": "",
        "feishu_page_url": "",
        "error_reason": "",
        "last_updated": now_iso,
    }


def write_csv(rows: list[dict], csv_path: Path) -> None:
    """原子写入 CSV（先写临时文件再 os.replace）。"""
    tmp_path = csv_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, csv_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def print_summary(rows: list[dict]) -> None:
    counts = {"episode": 0, "interview": 0, "clip": 0, "unknown": 0}
    for row in rows:
        cat = row.get("category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
    total = len(rows)
    print(
        f"总计 {total} 个视频，"
        f"episode={counts['episode']}, "
        f"interview={counts['interview']}, "
        f"clip={counts['clip']}, "
        f"unknown={counts['unknown']}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="枚举 All In Podcast YouTube 频道全部视频，按时长三档分类，写入 CSV。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/allin/enumerate_channel.py               # 全量枚举并写 CSV
  python scripts/allin/enumerate_channel.py --dry-run     # 只打印统计，不写 CSV
  python scripts/allin/enumerate_channel.py --limit 20    # 只取前 20 个（调试用）
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印分类统计，不写 CSV",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="只取前 N 个视频（调试用）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="PATH",
        help="CSV 输出路径（默认 data/allin_channel_inventory.csv）",
    )
    args = parser.parse_args()

    csv_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else DATA_DIR / "allin_channel_inventory.csv"
    )

    videos = fetch_metadata(args.limit)
    if not videos:
        print("[ERROR] 未获取到任何视频元数据，请检查 yt-dlp 安装和网络", file=sys.stderr)
        sys.exit(1)

    now_iso = datetime.now(timezone.utc).isoformat()
    rows = [build_row(v, now_iso) for v in videos]

    print_summary(rows)

    if args.dry_run:
        print("[dry-run] 不写 CSV，退出。")
        return

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(rows, csv_path)
    print(f"[enumerate] CSV 已写入: {csv_path}")


if __name__ == "__main__":
    main()
