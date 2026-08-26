#!/usr/bin/env python3
"""Minimal read-only Beads dependency graph POC."""

from __future__ import annotations

import argparse
import json
import os
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


def default_catalog_path() -> Path:
    override = os.environ.get("BEADS_MAP_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Beads Map"
            / "repositories.json"
        )
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Beads Map" / "repositories.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "beads-map" / "repositories.json"


def resolve_repository(value: str) -> Path:
    if not value.strip():
        raise BeadsError("Repository path is required.")
    repository = Path(value).expanduser().resolve()
    if not repository.is_dir():
        raise BeadsError(f"Repository directory does not exist: {repository}")
    return repository


def pick_repository() -> Path | None:
    if sys.platform != "darwin":
        raise BeadsError("The native folder picker is currently available on macOS.")
    script = 'POSIX path of (choose folder with prompt "Choose a Beads repository")'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except FileNotFoundError as error:
        raise BeadsError("Could not open the macOS folder picker.") from error
    except subprocess.TimeoutExpired as error:
        raise BeadsError("The folder picker timed out.") from error

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        if "(-128)" in message or "User canceled" in message:
            return None
        raise BeadsError(message or "Could not choose a repository folder.")
    return resolve_repository(result.stdout.strip())


class RepositoryCatalog:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._repositories: list[Path] = []
        self._selected: Path | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Could not read repository catalog: {error}", file=sys.stderr)
            return
        if not isinstance(payload, dict):
            print("Could not read repository catalog: expected a JSON object.", file=sys.stderr)
            return

        for value in payload.get("repositories", []):
            if not isinstance(value, str):
                continue
            repository = Path(value).expanduser().resolve()
            if repository not in self._repositories:
                self._repositories.append(repository)
        selected = payload.get("selected")
        if isinstance(selected, str):
            candidate = Path(selected).expanduser().resolve()
            if candidate in self._repositories:
                self._selected = candidate
        if self._selected is None and self._repositories:
            self._selected = self._repositories[0]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "repositories": [str(path) for path in self._repositories],
                    "selected": str(self._selected) if self._selected else None,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if os.name != "nt":
            temporary.chmod(0o600)
        temporary.replace(self.path)

    def add(self, repository: Path, *, select: bool = True) -> None:
        with self._lock:
            if repository not in self._repositories:
                self._repositories.append(repository)
            if select or self._selected is None:
                self._selected = repository
            self._save()

    def select(self, repository: Path) -> None:
        with self._lock:
            if repository not in self._repositories:
                raise BeadsError("Repository is not in the catalog.")
            self._selected = repository
            self._save()

    def remove(self, repository: Path) -> None:
        with self._lock:
            if repository not in self._repositories:
                raise BeadsError("Repository is not in the catalog.")
            self._repositories.remove(repository)
            if self._selected == repository:
                self._selected = self._repositories[0] if self._repositories else None
            self._save()

    def contains(self, repository: Path) -> bool:
        with self._lock:
            return repository in self._repositories

    def selected(self) -> Path | None:
        with self._lock:
            return self._selected

    def payload(self) -> dict:
        with self._lock:
            return {
                "repositories": [
                    {"name": path.name or str(path), "path": str(path)}
                    for path in self._repositories
                ],
                "selected": str(self._selected) if self._selected else None,
            }


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
    catalog: RepositoryCatalog

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlsplit(self.path).path
        if path == "/api/graph":
            self._serve_graph()
            return
        if path == "/api/repositories":
            self._send_json(200, self.catalog.payload())
            return
        if path in {"/", "/index.html"}:
            self._serve_file(WEB_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlsplit(self.path).path
        if path == "/api/repositories/pick":
            if self.headers.get("X-Beads-Map") != "1":
                self._send_json(403, {"error": "Folder picker request was not authorized."})
                return
            try:
                repository = pick_repository()
                if repository is None:
                    self._send_json(200, {"cancelled": True})
                    return
                graph = normalize_graph(repository, export_issues(repository))
                self.catalog.add(repository)
                self._send_json(200, {"catalog": self.catalog.payload(), "graph": graph})
            except (BeadsError, OSError) as error:
                self._send_json(400, {"error": str(error)})
            return
        try:
            payload = self._read_json()
            repository = resolve_repository(str(payload.get("path") or ""))
            if path == "/api/repositories":
                graph = normalize_graph(repository, export_issues(repository))
                self.catalog.add(repository)
                self._send_json(200, {"catalog": self.catalog.payload(), "graph": graph})
                return
            if path == "/api/repositories/select":
                if not self.catalog.contains(repository):
                    self._send_json(404, {"error": "Repository is not in the catalog."})
                    return
                graph = normalize_graph(repository, export_issues(repository))
                self.catalog.select(repository)
                self._send_json(200, {"catalog": self.catalog.payload(), "graph": graph})
                return
        except (BeadsError, OSError, ValueError) as error:
            self._send_json(400, {"error": str(error)})
            return
        self.send_error(404)

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if urlsplit(self.path).path != "/api/repositories":
            self.send_error(404)
            return
        try:
            payload = self._read_json()
            value = str(payload.get("path") or "")
            if not value.strip():
                raise ValueError("Repository path is required.")
            repository = Path(value).expanduser().resolve()
            self.catalog.remove(repository)
            self._send_json(200, self.catalog.payload())
        except (BeadsError, OSError, ValueError) as error:
            self._send_json(400, {"error": str(error)})

    def _serve_graph(self) -> None:
        repository = self.catalog.selected()
        if repository is None:
            self._send_json(404, {"error": "No repository is selected. Add one to begin."})
            return
        try:
            payload = normalize_graph(repository, export_issues(repository))
            self._send_json(200, payload)
        except BeadsError as error:
            self._send_json(500, {"error": str(error)})

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request length.") from error
        if length < 1 or length > 16_384:
            raise ValueError("Request body must contain a small JSON object.")
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as error:
            raise ValueError("Request body is not valid JSON.") from error
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

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
    parser.add_argument(
        "repositories",
        nargs="*",
        metavar="repository",
        help="Beads repository paths to remember",
    )
    parser.add_argument("--port", type=int, default=8765, help="Local HTTP port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog = RepositoryCatalog(default_catalog_path())
    supplied = args.repositories
    if not supplied and catalog.selected() is None:
        supplied = ["."]
    for index, value in enumerate(supplied):
        try:
            repository = resolve_repository(value)
            catalog.add(repository, select=index == 0)
        except BeadsError as error:
            print(error, file=sys.stderr)
            return 2
        except OSError as error:
            print(f"Could not save repository catalog: {error}", file=sys.stderr)
            return 2

    selected = catalog.selected()
    graph = None
    if selected is not None:
        try:
            graph = normalize_graph(selected, export_issues(selected))
        except BeadsError as error:
            print(f"Could not read selected repository yet: {error}", file=sys.stderr)

    AppHandler.catalog = catalog
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), AppHandler)
    except OSError as error:
        print(f"Could not start local server: {error}", file=sys.stderr)
        return 2

    url = f"http://127.0.0.1:{args.port}"
    if graph:
        print(
            f"Beads Map: {graph['repository']} · {len(graph['nodes'])} issues · "
            f"{len(graph['edges'])} dependencies"
        )
    else:
        print("Beads Map: add or select a readable Beads repository in the browser")
    print(f"Repository catalog: {catalog.path}")
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
