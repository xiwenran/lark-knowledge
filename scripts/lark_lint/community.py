from __future__ import annotations

from typing import Any

from graph import Page
from nx_compat import nx


def _community_cohesion(graph: nx.Graph, members: list[str]) -> float:
    if len(members) < 2:
        return 0.0
    subgraph = graph.subgraph(members)
    possible_edges = len(members) * (len(members) - 1) / 2
    if possible_edges == 0:
        return 0.0
    return subgraph.number_of_edges() / possible_edges


def analyze_communities(graph: nx.DiGraph, pages: dict[str, Page]) -> dict[str, Any]:
    zero_backlinks = sorted(
        (
            {
                "path": node,
                "title": pages[node].title,
                "outgoing_links": graph.out_degree(node),
            }
            for node in graph.nodes()
            if graph.in_degree(node) == 0
        ),
        key=lambda item: (-item["outgoing_links"], item["path"]),
    )

    undirected = graph.to_undirected()
    if undirected.number_of_nodes() == 0:
        return {"zero_backlinks": zero_backlinks, "loose_communities": [], "community_count": 0}

    partition = nx.best_partition(undirected) if undirected.number_of_edges() else {
        node: index for index, node in enumerate(undirected.nodes())
    }

    buckets: dict[int, list[str]] = {}
    for node, group in partition.items():
        buckets.setdefault(group, []).append(node)

    loose_communities: list[dict[str, Any]] = []
    for community_id, members in buckets.items():
        cohesion = _community_cohesion(undirected, members)
        if len(members) >= 3 and cohesion < 0.15:
            loose_communities.append(
                {
                    "community_id": community_id,
                    "size": len(members),
                    "cohesion": round(cohesion, 3),
                    "members": sorted(members),
                }
            )

    loose_communities.sort(key=lambda item: (item["cohesion"], -item["size"], item["community_id"]))
    return {
        "zero_backlinks": zero_backlinks,
        "loose_communities": loose_communities,
        "community_count": len(buckets),
    }
