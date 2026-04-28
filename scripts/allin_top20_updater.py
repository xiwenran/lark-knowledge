#!/usr/bin/env python3
"""
All In Podcast 精选 Top20 自动维护脚本

算法：综合得分 = YouTube播放量 × 0.4 + 五维综合评分 × 0.6
      (播放量已由飞书公式字段「综合得分（算法）」自动计算)

用法：
    python3 scripts/allin_top20_updater.py [--dry-run]

定时运行建议：每月 1 日执行一次（crontab 或 GitHub Actions）
"""

import json
import subprocess
import sys
import argparse
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".agents/skills/lark-knowledge-config/config.json"

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)["all_in_podcast"]

# ── lark-cli 调用封装 ──────────────────────────────────────────────────
def run_lark(args: list[str]) -> dict:
    """调用 lark-cli 并返回解析后的 JSON 结果。"""
    cmd = ["lark-cli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"lark-cli 失败：{result.stderr.strip()}")
    return json.loads(result.stdout)

# ── Step 1：从多维表格拉取所有已发布/可用记录 ─────────────────────────
def fetch_all_records(cfg: dict) -> list[dict]:
    """
    拉取节目收件表全量记录，按综合得分降序。
    使用 +data-query 在服务端排序，避免客户端大量拉取。
    """
    result = run_lark([
        "base", "+data-query",
        "--base-token", cfg["base_token"],
        "--table-id",   cfg["table_id"],
        "--json", json.dumps({
            "select": [
                "期号", "中文标题", "英文原标题", "发布日期",
                "主题分类", "五维综合评分", "YouTube播放量",
                "综合得分（算法）", "飞书页面URL", "发布状态"
            ],
            "where": {
                "logic": "and",
                "conditions": [
                    ["飞书页面URL", "is_not_empty", None],
                    ["翻译状态", "=", ["已完成"]]
                ]
            },
            "order_by": [{"field": "综合得分（算法）", "order": "desc"}],
            "limit": 50
        })
    ])
    return result.get("data", {}).get("items", [])

# ── Step 2：取 Top 20，生成页面 Markdown ────────────────────────────────
def build_top20_markdown(records: list[dict], generated_at: str) -> str:
    top20 = records[:20]

    lines = [
        "# 🔥 精选必读（Top 20）",
        "",
        f"> 根据综合算法（播放量 × 0.4 + 五维评分 × 0.6）自动排名，每月更新。",
        f"> 最近更新：{generated_at}",
        "",
        "---",
        "",
    ]

    for i, rec in enumerate(top20, 1):
        fields = rec.get("fields", rec)  # 兼容 +data-query 返回格式
        episode   = fields.get("期号", "—")
        title_zh  = fields.get("中文标题", "—")
        title_en  = fields.get("英文原标题", "—")
        topic     = fields.get("主题分类", "—")
        score_5d  = fields.get("五维综合评分", 0) or 0
        views     = fields.get("YouTube播放量", 0) or 0
        composite = fields.get("综合得分（算法）", 0) or 0
        page_url  = fields.get("飞书页面URL", "")
        pub_date  = fields.get("发布日期", "")

        views_str = f"{views/10000:.0f}万" if views >= 10000 else str(views)
        score_str = f"{score_5d:.1f}"
        composite_str = f"{composite:,.0f}"

        rank_label = f"**#{i}**"
        title_link = f"[{title_zh}]({page_url})" if page_url else title_zh

        lines += [
            f"### {rank_label} {title_link}",
            f"",
            f"**{episode}** · {pub_date} · `{topic}`",
            f"",
            f"五维评分 **{score_str}** · 播放量 **{views_str}** · 综合得分 {composite_str}",
            f"",
            f"> {title_en}",
            f"",
            "---",
            "",
        ]

    lines.append(f"*共 {len(top20)} 期 / 候选池 {len(records)} 期 · 算法：播放量×0.4 + 五维评分×0.6*")
    return "\n".join(lines)

# ── Step 3：更新「精选必读」wiki 页面 ───────────────────────────────────
def update_top20_page(cfg: dict, markdown: str, dry_run: bool) -> str:
    """用 lark-cli docs +update 覆写精选必读页面。"""
    node_token = cfg["wiki"]["directories"]["精选必读"]  # AePcwybNJi7mGykEEHDcWBWxnId

    if dry_run:
        print("[dry-run] 将更新节点：", node_token)
        print("[dry-run] 页面内容预览（前 500 字符）：")
        print(markdown[:500])
        return "(dry-run)"

    result = run_lark([
        "docs", "+update",
        "--doc", node_token,
        "--mode", "overwrite",
        "--markdown", markdown,
    ])
    return result.get("data", {}).get("doc_url", node_token)

# ── 主流程 ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="All In Top20 自动更新")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入飞书")
    args = parser.parse_args()

    print("📊 读取配置...")
    cfg = load_config()

    print("📋 拉取节目记录...")
    records = fetch_all_records(cfg)
    print(f"   候选记录：{len(records)} 条")

    if not records:
        print("⚠️  暂无满足条件的记录（需要「翻译状态=已完成」且「飞书页面URL非空」）")
        sys.exit(0)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("✍️  生成 Top20 页面...")
    markdown = build_top20_markdown(records, generated_at)

    print("🚀 更新飞书「精选必读」页面...")
    url = update_top20_page(cfg, markdown, args.dry_run)
    print(f"✅ 完成！页面：{url}")

if __name__ == "__main__":
    main()
