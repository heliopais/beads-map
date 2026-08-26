#!/usr/bin/env python3
"""Minimal read-only Beads dependency graph POC."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


BLOCKING_DEPENDENCIES = {"blocks", "conditional-blocks", "waits-for"}
ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


class BeadsError(RuntimeError):
    pass


def export_issues(repository: Path) -> list[dict]:
    command = ["bd", "--readonly", "-C", str(repository), "export"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError as error:
        raise BeadsError("The `bd` command is not installed or not on PATH.") from error
    except subprocess.TimeoutExpired as error:
        raise BeadsError("Timed out while reading Beads.") from error

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Unknown Beads error"
        raise BeadsError(message)

    issues: list[dict] = []
    for line_number, line in enumerate(result.stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            issues.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise BeadsError(f"Invalid JSON from Beads on line {line_number}.") from error
    return issues


def normalize_graph(repository: Path, issues: list[dict]) -> dict:
    by_id = {issue["id"]: issue for issue in issues if issue.get("id")}
    edges: list[dict] = []

    for issue in by_id.values():
        for dependency in issue.get("dependencies") or []:
            dependency_type = dependency.get("type") or dependency.get("dependency_type")
            source = dependency.get("depends_on_id")
            target = dependency.get("issue_id") or issue["id"]
            if (
                dependency_type in BLOCKING_DEPENDENCIES
                and source in by_id
                and target in by_id
            ):
                edges.append({"source": source, "target": target, "type": dependency_type})

    blockers: dict[str, list[str]] = {issue_id: [] for issue_id in by_id}
    dependents: dict[str, list[str]] = {issue_id: [] for issue_id in by_id}
    for edge in edges:
        blockers[edge["target"]].append(edge["source"])
        dependents[edge["source"]].append(edge["target"])

    nodes = []
    for issue_id, issue in by_id.items():
        raw_status = str(issue.get("status") or "unknown")
        deferred = bool(issue.get("defer_until") or issue.get("deferred_until"))
        active_blockers = [
            blocker_id
            for blocker_id in blockers[issue_id]
            if str(by_id[blocker_id].get("status")) != "closed"
        ]

        if raw_status == "closed":
            state = "completed"
        elif deferred:
            state = "deferred"
        elif raw_status == "in_progress":
            state = "in-progress"
        elif active_blockers:
            state = "blocked"
        else:
            state = "ready"

        nodes.append(
            {
                "id": issue_id,
                "title": issue.get("title") or issue_id,
                "description": issue.get("description") or "",
                "type": issue.get("issue_type") or "work item",
                "rawStatus": raw_status,
                "state": state,
                "labels": issue.get("labels") or [],
                "assignee": issue.get("assignee") or "",
                "blockers": blockers[issue_id],
                "activeBlockers": active_blockers,
                "dependents": dependents[issue_id],
            }
        )

    return {
        "repository": repository.name,
        "path": str(repository),
        "nodes": nodes,
        "edges": edges,
    }


class AppHandler(BaseHTTPRequestHandler):
    repository: Path

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlsplit(self.path).path
        if path == "/api/graph":
            self._serve_graph()
            return
        if path in {"/", "/index.html"}:
            self._serve_file(WEB_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(404)

    def _serve_graph(self) -> None:
        try:
            payload = normalize_graph(self.repository, export_issues(self.repository))
            self._send_json(200, payload)
        except BeadsError as error:
            self._send_json(500, {"error": str(error)})

    def _serve_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, value: dict) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[beads-map] {format % args}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", default=".", help="Beads repository path")
    parser.add_argument("--port", type=int, default=8765, help="Local HTTP port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).expanduser().resolve()
    if not repository.is_dir():
        print(f"Repository directory does not exist: {repository}", file=sys.stderr)
        return 2

    try:
        graph = normalize_graph(repository, export_issues(repository))
    except BeadsError as error:
        print(f"Could not read Beads: {error}", file=sys.stderr)
        return 2

    AppHandler.repository = repository
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), AppHandler)
    except OSError as error:
        print(f"Could not start local server: {error}", file=sys.stderr)
        return 2

    url = f"http://127.0.0.1:{args.port}"
    print(
        f"Beads Map: {graph['repository']} · {len(graph['nodes'])} issues · "
        f"{len(graph['edges'])} dependencies"
    )
    print(f"Open {url} · press Ctrl-C to stop")
    if not args.no_browser:
        threading.Timer(0.2, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
