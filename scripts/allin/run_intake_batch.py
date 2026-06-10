"""
run_intake_batch.py — 输出 intake 待办批次清单，供主会话 / 子代理逐期触发 lark-knowledge-allin-intake skill。

本脚本不直接调用 intake skill，只负责:
  1. 从 CSV 读取待办，输出本批 JSON 清单（让主会话 / 子代理读取并逐期触发 skill）
  2. 提供子命令让子代理跑完后回填 CSV 状态

典型用法:
  # 输出本批 episode 待办（默认 20 期，倒序，不改 CSV）
  python scripts/allin/run_intake_batch.py

  # 指定批次大小和分类
  python scripts/allin/run_intake_batch.py --batch-size 10 --category interview

  # Dry-run：只看本批清单，不改 CSV
  python scripts/allin/run_intake_batch.py --dry-run

  # 标记完成（子代理跑完单期后调用）
  python scripts/allin/run_intake_batch.py --mark-done abc123 --record-id rec_xxx

  # 标记失败
  python scripts/allin/run_intake_batch.py --mark-failed abc123 --reason "API_timeout"
"""

import argparse
import json
import sys
from pathlib import Path

# csv_helpers.py 与本脚本同目录
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import csv_helpers

DEFAULT_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "allin_channel_inventory.csv"


# ---------------------------------------------------------------------------
# 子命令：mark-done
# ---------------------------------------------------------------------------

def cmd_mark_done(args, csv_path: Path) -> None:
    video_id: str = args.mark_done
    record_id: str = args.record_id

    # 防重复：查当前状态
    row = csv_helpers.get_row(csv_path, video_id)
    if row is None:
        print(f"[ERROR] video_id={video_id!r} 在 CSV 中不存在", file=sys.stderr)
        sys.exit(1)

    if row.get("intake_status") == "done" and row.get("record_id"):
        print(
            f"[SKIP] {video_id} 已标记 done (record_id={row['record_id']!r})，跳过重复写入"
        )
        return

    ok = csv_helpers.update_row(
        csv_path,
        video_id,
        {"intake_status": "done", "record_id": record_id, "error_reason": ""},
    )
    if ok:
        print(f"[OK] {video_id} → intake_status=done, record_id={record_id}")
    else:
        print(f"[ERROR] 更新失败，找不到 video_id={video_id!r}", file=sys.stderr)
        sys.exit(1)


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
        {"intake_status": "failed", "error_reason": reason},
    )
    if ok:
        print(f"[OK] {video_id} → intake_status=failed, error_reason={reason!r}")
    else:
        print(f"[ERROR] 更新失败，找不到 video_id={video_id!r}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 主命令：输出本批待办清单
# ---------------------------------------------------------------------------

def cmd_list_batch(args, csv_path: Path) -> None:
    batch_size: int = args.batch_size
    order: str = args.order  # desc | asc
    category: str = args.category  # episode | interview | all

    category_filter = None if category == "all" else [category]

    # iter_pending 内部已做倒序（upload_date desc），asc 则需要反转
    pending = list(
        csv_helpers.iter_pending(
            csv_path,
            phase="intake",
            category_filter=category_filter,
        )
    )
    if order == "asc":
        pending = list(reversed(pending))

    batch = pending[:batch_size]

    if not batch:
        print("[INFO] 没有待办的 intake 任务（所有行均已完成或跳过）")
        return

    # 构建输出清单
    output = []
    for row in batch:
        # 每期开跑前再次查 CSV 去重（防并发 / 重启重复）
        fresh = csv_helpers.get_row(csv_path, row["video_id"])
        if fresh and fresh.get("intake_status") == "done" and fresh.get("record_id"):
            # 已完成，跳过
            continue
        output.append(
            {
                "video_id": row["video_id"],
                "title": row["title"],
                "youtube_url": row["youtube_url"],
                "upload_date": row["upload_date"],
                "duration_min": row.get("duration_min"),
                "category": row.get("category"),
            }
        )

    if not output:
        print("[INFO] 本批所有视频均已完成（去重后为空）")
        return

    print(f"[intake-batch] 本批 {len(output)} 期待办（category={category}, order={order}）：")
    print()
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print()
    print("[提示] 主会话 / 子代理逐期触发 lark-knowledge-allin-intake skill 后，")
    print("       调用以下命令回填状态（建议每条 record_create 后 sleep 1s）：")
    print(f"       python scripts/allin/run_intake_batch.py --mark-done <video_id> --record-id <rid>")
    print(f"       python scripts/allin/run_intake_batch.py --mark-failed <video_id> --reason <msg>")

    if args.dry_run:
        print()
        print("[dry-run] 不修改 CSV，退出。")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "输出 intake 待办批次清单，供主会话 / 子代理逐期触发 lark-knowledge-allin-intake skill。\n"
            "本脚本不直接调用 intake skill，只管状态 CSV。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令示例:
  # 输出本批待办
  python scripts/allin/run_intake_batch.py --batch-size 20 --category episode

  # 标记完成
  python scripts/allin/run_intake_batch.py --mark-done VIDEO_ID --record-id rec_xxx

  # 标记失败
  python scripts/allin/run_intake_batch.py --mark-failed VIDEO_ID --reason "API_timeout"
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
        default=20,
        metavar="N",
        help="本批最大条数（默认 20）",
    )
    parser.add_argument(
        "--order",
        choices=["desc", "asc"],
        default="desc",
        help="按 upload_date 倒序(desc, 最新先)或正序(asc, 默认 desc)",
    )
    parser.add_argument(
        "--category",
        choices=["episode", "interview", "all"],
        default="episode",
        help="过滤分类（默认 episode）",
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
    # 子命令：mark-done
    parser.add_argument(
        "--mark-done",
        metavar="VIDEO_ID",
        help="将指定 video_id 的 intake_status 标记为 done",
    )
    parser.add_argument(
        "--record-id",
        metavar="RID",
        help="配合 --mark-done 使用，填写飞书 record_id",
    )
    # 子命令：mark-failed
    parser.add_argument(
        "--mark-failed",
        metavar="VIDEO_ID",
        help="将指定 video_id 的 intake_status 标记为 failed",
    )
    parser.add_argument(
        "--reason",
        metavar="MSG",
        help="配合 --mark-failed 使用，填写 error_reason",
    )

    args = parser.parse_args()
    csv_path = Path(args.csv).expanduser().resolve()

    if not csv_path.exists():
        print(f"[ERROR] CSV 文件不存在: {csv_path}", file=sys.stderr)
        print("[提示] 请先运行 enumerate_channel.py 生成 CSV", file=sys.stderr)
        sys.exit(1)

    # 路由到子命令
    if args.mark_done:
        if not args.record_id:
            print("[ERROR] --mark-done 必须同时指定 --record-id", file=sys.stderr)
            sys.exit(1)
        cmd_mark_done(args, csv_path)
    elif args.mark_failed:
        cmd_mark_failed(args, csv_path)
    else:
        cmd_list_batch(args, csv_path)


if __name__ == "__main__":
    main()
