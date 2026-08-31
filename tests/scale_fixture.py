#!/usr/bin/env python3
"""Launch Beads Map with a deterministic synthetic DAG for browser checks."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import beads_map


def synthetic_graph(repository: Path, node_count: int, edge_count: int) -> dict:
    if node_count < 1:
        raise ValueError("node count must be positive")
    maximum_edges = node_count * (node_count - 1) // 2
    if edge_count < 0 or edge_count > maximum_edges:
        raise ValueError(f"edge count must be between 0 and {maximum_edges}")

    issues = [
        {
            "id": f"scale-{index:04d}",
            "title": f"Synthetic work item {index:04d}",
            "description": "Deterministic browser performance fixture.",
            "status": "closed" if index % 5 == 0 else "open",
            "issue_type": "feature" if index % 7 == 0 else "task",
            "labels": ["even" if index % 2 == 0 else "odd"],
            "assignee": "Fixture owner" if index % 3 == 0 else "",
            "dependencies": [],
        }
        for index in range(node_count)
    ]
    remaining = edge_count
    distance = 1
    while remaining:
        for target in range(distance, node_count):
            if not remaining:
                break
            issues[target]["dependencies"].append(
                {
                    "issue_id": issues[target]["id"],
                    "depends_on_id": issues[target - distance]["id"],
                    "type": "blocks",
                }
            )
            remaining -= 1
        distance += 1
    return beads_map.normalize_graph(repository, issues)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=500)
    parser.add_argument("--edges", type=int, default=1500)
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="beads-map-scale-") as temporary:
        root = Path(temporary)
        repository = root / "scale-fixture"
        (repository / ".beads").mkdir(parents=True)
        catalog = beads_map.RepositoryCatalog(root / "repositories.json")
        catalog.add(repository)
        graph = synthetic_graph(repository, args.nodes, args.edges)
        beads_map.AppHandler.catalog = catalog
        beads_map.AppHandler.snapshots = beads_map.SnapshotCoordinator(lambda _: graph)
        server = beads_map.create_server(args.port, strict=True)
        print(
            f"Scale fixture: {args.nodes} nodes · {args.edges} edges · "
            f"http://127.0.0.1:{args.port}",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
