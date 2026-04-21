from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identify loose knowledge clusters and isolated pages from Lark Base records."
    )
    parser.add_argument("--config", type=Path, help="Path to config.json. Defaults to repo config, then ~/.agents path.")
    parser.add_argument("--page-size", type=int, default=100, help="Pagination size for lark-cli record listing.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.10,
        help="Community cohesion threshold. Communities below this value are reported. Default: 0.10.",
    )
    parser.add_argument(
        "--member-limit",
        type=int,
        default=8,
        help="Max members to print per community or type group before truncation. Default: 8.",
    )
    return parser.parse_args()


def _format_titles(titles: list[str], limit: int) -> str:
    if len(titles) <= limit:
        return "、".join(titles)
    remaining = len(titles) - limit
    preview = "、".join(titles[:limit])
    return f"{preview} 等 {remaining} 个"


def _community_buckets(graph: nx.DiGraph) -> dict[int, list[str]]:
    from nx_compat import nx

    undirected = graph.to_undirected()
    if undirected.number_of_nodes() == 0:
        return {}
    partition = nx.best_partition(undirected) if undirected.number_of_edges() else {
        node: index for index, node in enumerate(undirected.nodes())
    }
    buckets: dict[int, list[str]] = {}
    for node, group in partition.items():
        buckets.setdefault(group, []).append(node)
    return buckets


def _loose_communities(
    graph: Any,
    pages: dict[str, Any],
    threshold: float,
) -> list[dict[str, object]]:
    from community import _community_cohesion

    undirected = graph.to_undirected()
    loose: list[dict[str, object]] = []
    for community_id, members in _community_buckets(graph).items():
        cohesion = _community_cohesion(undirected, members)
        if len(members) < 3 or cohesion >= threshold:
            continue
        titles = sorted(pages[node].title for node in members)
        page_types = sorted({pages[node].page_type for node in members if pages[node].page_type})
        loose.append(
            {
                "community_id": community_id,
                "size": len(members),
                "cohesion": round(cohesion, 3),
                "titles": titles,
                "page_types": page_types,
            }
        )
    loose.sort(key=lambda item: (item["cohesion"], -item["size"], item["community_id"]))
    return loose


def _group_isolates(graph: Any, pages: dict[str, Any]) -> list[tuple[str, list[str]]]:
    from nx_compat import nx

    isolates = sorted(nx.isolates(graph), key=lambda node: (pages[node].page_type or "", pages[node].title))
    grouped: dict[str, list[str]] = defaultdict(list)
    for node in isolates:
        label = pages[node].page_type or pages[node].top_level_dir or "未标注类型"
        grouped[label].append(pages[node].title)
    return sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))


def render_report(
    config_path: Path,
    record_count: int,
    graph: Any,
    community_count: int,
    loose_communities: list[dict[str, object]],
    isolated_groups: list[tuple[str, list[str]]],
    threshold: float,
    member_limit: int,
) -> str:
    lines = [
        "没整理完区块报告",
        f"配置文件: {config_path.name}",
        (
            f"记录数: {record_count} | 已识别关系数: {graph.number_of_edges()} | "
            f"社区数: {community_count} | 松散阈值: < {threshold:.2f}"
        ),
        "",
        f"松散聚类（{len(loose_communities)} 个）",
    ]

    if not loose_communities:
        lines.append("✅ 未发现低于阈值的松散聚类。")
    else:
        for item in loose_communities:
            lines.append(
                (
                    f"- 社区 #{item['community_id']} | 规模 {item['size']} | "
                    f"内聚度 {item['cohesion']:.3f}"
                )
            )
            page_types = item["page_types"] or ["未标注类型"]
            lines.append(f"  类型: {' / '.join(page_types)}")
            lines.append(f"  成员: {_format_titles(item['titles'], member_limit)}")

    lines.extend(["", f"孤立页（{sum(len(items) for _, items in isolated_groups)} 个）"])
    if not isolated_groups:
        lines.append("✅ 未发现完全孤立的页面。")
    else:
        for page_type, titles in isolated_groups:
            lines.append(f"- {page_type}（{len(titles)} 个）: {_format_titles(titles, member_limit)}")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if args.page_size <= 0:
        raise SystemExit("--page-size must be > 0")
    if args.member_limit <= 0:
        raise SystemExit("--member-limit must be > 0")
    if not 0 <= args.threshold <= 1:
        raise SystemExit("--threshold must be between 0 and 1")

    from lint_links import build_graph, list_all_records, load_config, normalize_record, resolve_config_path

    config_path = resolve_config_path(args.config)
    config = load_config(config_path)
    base_token = str(config["base"]["base_token"])
    table_id = str(config["base"]["table_id"])

    normalized_records = [
        item
        for item in (normalize_record(record) for record in list_all_records(base_token, table_id, args.page_size))
        if item is not None
    ]
    graph, pages = build_graph(normalized_records)
    from community import analyze_communities

    baseline = analyze_communities(graph, pages)
    loose_communities = _loose_communities(graph, pages, args.threshold)
    isolated_groups = _group_isolates(graph, pages)

    print(
        render_report(
            config_path=config_path,
            record_count=len(normalized_records),
            graph=graph,
            community_count=int(baseline["community_count"]),
            loose_communities=loose_communities,
            isolated_groups=isolated_groups,
            threshold=args.threshold,
            member_limit=args.member_limit,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
