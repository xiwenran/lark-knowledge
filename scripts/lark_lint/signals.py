from __future__ import annotations

from itertools import combinations
from math import isfinite
from typing import Any

from graph import Page
from nx_compat import nx


def _type_affinity(page_a: Page, page_b: Page) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    if page_a.page_type and page_a.page_type == page_b.page_type:
        score = 1.0
        reasons.append(f"同为 `{page_a.page_type}` 类型")
    elif page_a.top_level_dir and page_a.top_level_dir == page_b.top_level_dir:
        score = 1.0
        reasons.append(f"同属 `{page_a.top_level_dir}` 目录")
    return score, reasons


def _incoming_overlap(graph: nx.DiGraph, left: str, right: str) -> tuple[float, list[str]]:
    left_refs = set(graph.predecessors(left))
    right_refs = set(graph.predecessors(right))
    overlap = sorted(left_refs & right_refs)
    if not overlap:
        return 0.0, []
    return 4.0 * len(overlap), [f"被相同页面引用 {len(overlap)} 次：{', '.join(overlap[:3])}"]


def suggest_links(
    graph: nx.DiGraph,
    pages: dict[str, Page],
    top_n: int = 20,
) -> list[dict[str, Any]]:
    if graph.number_of_nodes() < 2:
        return []

    undirected = graph.to_undirected()
    pairs: list[tuple[str, str]] = []
    for left, right in combinations(sorted(graph.nodes()), 2):
        if graph.has_edge(left, right) or graph.has_edge(right, left):
            continue
        pairs.append((left, right))

    adamic_scores = {
        tuple(sorted((left, right))): score
        for left, right, score in nx.adamic_adar_index(undirected, pairs)
        if isfinite(score) and score > 0
    }

    suggestions: list[dict[str, Any]] = []
    for left, right in pairs:
        reasons: list[str] = []
        score = 0.0

        overlap_score, overlap_reasons = _incoming_overlap(graph, left, right)
        score += overlap_score
        reasons.extend(overlap_reasons)

        adamic = adamic_scores.get(tuple(sorted((left, right))), 0.0)
        if adamic > 0:
            weighted_adamic = adamic * 1.5
            score += weighted_adamic
            reasons.append(f"共享邻居较多（Adamic-Adar {weighted_adamic:.2f}）")

        affinity_score, affinity_reasons = _type_affinity(pages[left], pages[right])
        score += affinity_score
        reasons.extend(affinity_reasons)

        if score <= 0:
            continue

        suggestions.append(
            {
                "page_a": left,
                "page_b": right,
                "title_a": pages[left].title,
                "title_b": pages[right].title,
                "score": round(score, 2),
                "reasons": reasons,
            }
        )

    suggestions.sort(key=lambda item: (-item["score"], item["page_a"], item["page_b"]))
    return suggestions[:top_n]
