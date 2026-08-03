"""
run_transcript_batch.py — 输出 transcript 待办批次清单，供主会话 / 子代理逐期触发逐字稿 skill。

本脚本不直接调用 transcript skill，只负责:
  1. 筛选 intake_status=done AND transcript_status=pending 的行，输出本批 JSON 清单
  2. 提供子命令让子代理跑完后回填 CSV 状态
  3. 提供清理 /tmp/allin_<video_id> 中间产物的工具函数

典型用法:
  # 输出本批 transcript 待办（默认 5 期，倒序）
  python scripts/allin/run_transcript_batch.py

  # Dry-run
  python scripts/allin/run_transcript_batch.py --dry-run

  # 标记完成（子代理跑完后调用）
  python scripts/allin/run_transcript_batch.py --mark-done abc123 --page-url https://...

  # 标记失败
  python scripts/allin/run_transcript_batch.py --mark-failed abc123 --reason "subtitle_missing"

  # 手动清理某期中间产物（释放磁盘）
  python scripts/allin/run_transcript_batch.py --cleanup abc123
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import csv_helpers

DEFAULT_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "allin_channel_inventory.csv"


# ---------------------------------------------------------------------------
# 中间产物清理
# ---------------------------------------------------------------------------

def cleanup_tmp(video_id: str, verbose: bool = True) -> int:
    """
    删除 /tmp/allin_<video_id>/ 目录及 /tmp/allin_<video_id>* 文件。
    返回释放的字节数（近似值）。
    """
    released = 0
    tmp = Path("/tmp")

    # 目录形式：/tmp/allin_<video_id>/
    dir_path = tmp / f"allin_{video_id}"
    if dir_path.is_dir():
        size = sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file())
        shutil.rmtree(dir_path, ignore_errors=True)
        released += size
        if verbose:
            print(f"[cleanup] 已删除目录 {dir_path}  ({size / 1024:.1f} KB)")

    # 文件形式：/tmp/allin_<video_id>*.* （字幕、日志等）
    for p in tmp.glob(f"allin_{video_id}*"):
        if p.is_file():
            size = p.stat().st_size
            p.unlink(missing_ok=True)
            released += size
            if verbose:
                print(f"[cleanup] 已删除文件 {p}  ({size / 1024:.1f} KB)")

    if verbose:
        print(f"[cleanup] {video_id} 共释放 {released / 1024:.1f} KB")
    return released


# ---------------------------------------------------------------------------
# 子命令：mark-done
# ---------------------------------------------------------------------------

def cmd_mark_done(args, csv_path: Path) -> None:
    video_id: str = args.mark_done
    page_url: str = args.page_url or ""

    row = csv_helpers.get_row(csv_path, video_id)
    if row is None:
        print(f"[ERROR] video_id={video_id!r} 在 CSV 中不存在", file=sys.stderr)
        sys.exit(1)

    if row.get("transcript_status") == "done" and row.get("feishu_page_url"):
        print(
            f"[SKIP] {video_id} 已标记 transcript=done "
            f"(page_url={row['feishu_page_url']!r})，跳过重复写入"
        )
        return

    ok = csv_helpers.update_row(
        csv_path,
        video_id,
        {
            "transcript_status": "done",
            "feishu_page_url": page_url,
            "error_reason": "",
        },
    )
    if ok:
        print(f"[OK] {video_id} → transcript_status=done, feishu_page_url={page_url!r}")
    else:
        print(f"[ERROR] 更新失败，找不到 video_id={video_id!r}", file=sys.stderr)
        sys.exit(1)

    # --cleanup-after-each 自动清理
    if args.cleanup_after_each:
        cleanup_tmp(video_id)


# ---------------------------------------------------------------------------
# 子命令：mark-failed
# ---------------------------------------------------------------------------

def cmd_mark_failed(args, csv_path: Path) -> None:
    video_id: str = args.mark_failed
    reason: str = args.reason or ""

    row = csv_helpers.get_row(csv_path, video_id)
    if row is None:
        print(f"[ERROR] video_id={video_id!r} 在 CSV 中不存在", file=sys.stderr)
        sys.exit(1)

    ok = csv_helpers.update_row(
        csv_path,
        video_id,
        {"transcript_status": "failed", "error_reason": reason},
    )
    if ok:
        print(f"[OK] {video_id} → transcript_status=failed, error_reason={reason!r}")
    else:
        print(f"[ERROR] 更新失败，找不到 video_id={video_id!r}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 子命令：cleanup
# ---------------------------------------------------------------------------

def cmd_cleanup(args, csv_path: Path) -> None:
    video_id: str = args.cleanup
    released = cleanup_tmp(video_id, verbose=True)
    if released == 0:
        print(f"[cleanup] {video_id} 无中间产物可清理")


# ---------------------------------------------------------------------------
# 主命令：输出本批待办清单
# ---------------------------------------------------------------------------

def cmd_list_batch(args, csv_path: Path) -> None:
    batch_size: int = args.batch_size
    order: str = args.order  # desc | asc

    # transcript 批次不按 category 过滤（interview A/B 入表后同样需要逐字稿）
    pending = list(
        csv_helpers.iter_pending(
            csv_path,
            phase="transcript",
            category_filter=None,
        )
    )
    if order == "asc":
        pending = list(reversed(pending))

    batch = pending[:batch_size]

    if not batch:
        print("[INFO] 没有待办的 transcript 任务（所有 intake=done 的行均已完成或跳过）")
        return

    # 每期开跑前再次查 CSV 防重
    output = []
    for row in batch:
        fresh = csv_helpers.get_row(csv_path, row["video_id"])
        if (
            fresh
            and fresh.get("transcript_status") == "done"
            and fresh.get("feishu_page_url")
        ):
            continue
        output.append(
            {
                "video_id": row["video_id"],
                "title": row["title"],
                "youtube_url": row["youtube_url"],
                "upload_date": row["upload_date"],
                "duration_min": row.get("duration_min"),
                "category": row.get("category"),
                "record_id": row.get("record_id"),
            }
        )

    if not output:
        print("[INFO] 本批所有视频均已完成（去重后为空）")
        return

    print(f"[transcript-batch] 本批 {len(output)} 期待办（order={order}）：")
    print()
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print()
    print("[提示] 主会话 / 子代理触发 skill 的命令格式：")
    print("       allin逐字稿 <youtube_url> <record_id>")
    print()
    print("       跑完后回填状态：")
    print("       python scripts/allin/run_transcript_batch.py --mark-done <video_id> --page-url <url>")
    print("       python scripts/allin/run_transcript_batch.py --mark-failed <video_id> --reason <msg>")
    if args.cleanup_after_each:
        print()
        print("[提示] --cleanup-after-each 已启用，--mark-done 完成后自动清理 /tmp/allin_<video_id>/")

    if args.dry_run:
        print()
        print("[dry-run] 不修改 CSV，退出。")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "输出 transcript 待办批次清单，供主会话 / 子代理逐期触发逐字稿 skill。\n"
            "本脚本不直接调用 skill，只管状态 CSV 和中间产物清理。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令示例:
  # 输出本批待办
  python scripts/allin/run_transcript_batch.py --batch-size 5

  # 标记完成
  python scripts/allin/run_transcript_batch.py --mark-done VIDEO_ID --page-url https://...

  # 标记失败
  python scripts/allin/run_transcript_batch.py --mark-failed VIDEO_ID --reason subtitle_missing

  # 手动清理中间产物
  python scripts/allin/run_transcript_batch.py --cleanup VIDEO_ID
        """,
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=str(DEFAULT_CSV),
        metavar="PATH",
        help="CSV 状态文件路径（默认 data/allin_channel_inventory.csv）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        metavar="N",
        help="本批最大条数（默认 5）",
    )
    parser.add_argument(
        "--order",
        choices=["desc", "asc"],
        default="desc",
        help="按 upload_date 倒序(desc, 最新先)或正序(asc, 默认 desc)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印本批清单，不修改 CSV",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="从 CSV 第一个 pending 开始（默认行为，此参数保留作文档说明用）",
    )
    parser.add_argument(
        "--cleanup-after-each",
        action="store_true",
        default=True,
        help="--mark-done 完成后自动清理 /tmp/allin_<video_id> 中间产物（默认启用）",
    )
    parser.add_argument(
        "--no-cleanup-after-each",
        dest="cleanup_after_each",
        action="store_false",
        help="禁用 --mark-done 后的自动清理",
    )
    # 子命令：mark-done
    parser.add_argument(
        "--mark-done",
        metavar="VIDEO_ID",
        help="将指定 video_id 的 transcript_status 标记为 done",
    )
    parser.add_argument(
        "--page-url",
        metavar="URL",
        help="配合 --mark-done 使用，填写飞书逐字稿页面 URL",
    )
    # 子命令：mark-failed
    parser.add_argument(
        "--mark-failed",
        metavar="VIDEO_ID",
        help="将指定 video_id 的 transcript_status 标记为 failed",
    )
    parser.add_argument(
        "--reason",
        metavar="MSG",
        help="配合 --mark-failed 使用，填写 error_reason",
    )
    # 子命令：cleanup
    parser.add_argument(
        "--cleanup",
        metavar="VIDEO_ID",
        help="删除 /tmp/allin_<video_id>/ 及相关临时文件，打印释放空间",
    )

    args = parser.parse_args()
    csv_path = Path(args.csv).expanduser().resolve()

    if not csv_path.exists():
        print(f"[ERROR] CSV 文件不存在: {csv_path}", file=sys.stderr)
        print("[提示] 请先运行 enumerate_channel.py 生成 CSV", file=sys.stderr)
        sys.exit(1)

    # 路由到子命令
    if args.mark_done:
        cmd_mark_done(args, csv_path)
    elif args.mark_failed:
        cmd_mark_failed(args, csv_path)
    elif args.cleanup:
        cmd_cleanup(args, csv_path)
    else:
        cmd_list_batch(args, csv_path)


if __name__ == "__main__":
    main()
