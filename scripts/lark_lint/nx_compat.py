from __future__ import annotations

import networkx as nx
from importlib import machinery, util
import sys


def best_partition(graph: nx.Graph) -> dict[str, int]:
    search_path = [entry for entry in sys.path[1:] if entry]
    spec = machinery.PathFinder.find_spec("community", search_path)
    if spec is None or spec.loader is None:
        raise ImportError("python-louvain is not installed. Run `pip install -r requirements.txt`.")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    community_louvain = module
    return community_louvain.best_partition(graph)


nx.best_partition = best_partition
