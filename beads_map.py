#!/usr/bin/env python3
"""Minimal read-only Beads dependency graph POC."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterator, Sequence
from urllib.parse import parse_qs, urlsplit

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows is not currently supported.
    fcntl = None


__version__ = "0.1.9"
BLOCKING_DEPENDENCIES = {"blocks", "conditional-blocks", "waits-for"}
DISPLAYED_DEPENDENCIES = BLOCKING_DEPENDENCIES | {"discovered-from", "parent-child"}
VIEW_STATES = {"completed", "in-progress", "ready", "blocked", "deferred"}
NON_HUMAN_ISSUE_TYPES = {
    "agent",
    "gate",
    "infrastructure",
    "memory",
    "message",
    "molecule",
    "template",
}
MINIMUM_BD_VERSION = (1, 1, 0)
MAXIMUM_BD_VERSION = (2, 0, 0)
ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


class BeadsError(RuntimeError):
    pass


def parse_bd_version(output: str) -> tuple[int, int, int]:
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", output)
    if match is None:
        raise BeadsError("Could not determine the installed bd version.")
    return tuple(int(part) for part in match.groups())


def ensure_supported_bd() -> tuple[int, int, int]:
    try:
        result = subprocess.run(
            ["bd", "version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError as error:
        raise BeadsError(
            "The bd command was not found on PATH. Install Beads >=1.1 and <2, "
            "then try again."
        ) from error
    except subprocess.TimeoutExpired as error:
        raise BeadsError("Timed out while checking the installed bd version.") from error

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise BeadsError(message or "Could not run `bd version`.")

    version = parse_bd_version(result.stdout or result.stderr)
    if not MINIMUM_BD_VERSION <= version < MAXIMUM_BD_VERSION:
        found = ".".join(str(part) for part in version)
        raise BeadsError(
            f"Beads Map requires bd >=1.1 and <2; found {found}. "
            "Upgrade Beads and try again."
        )
    return version


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
        self._views: dict[str, dict] = {}
        self._load()

    def _load(self, *, strict: bool = False) -> None:
        self._repositories = []
        self._selected = None
        self._views = {}
        if not self.path.is_file():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            if strict:
                raise BeadsError(f"Could not read repository catalog: {error}") from error
            print(f"Could not read repository catalog: {error}", file=sys.stderr)
            return
        if not isinstance(payload, dict):
            if strict:
                raise BeadsError("Could not read repository catalog: expected a JSON object.")
            print("Could not read repository catalog: expected a JSON object.", file=sys.stderr)
            return

        repositories = payload.get("repositories", [])
        if not isinstance(repositories, list):
            if strict:
                raise BeadsError("Could not read repository catalog: repositories must be a list.")
            repositories = []
        for value in repositories:
            if not isinstance(value, str):
                continue
            if not value.strip():
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
        views = payload.get("views", {})
        if isinstance(views, dict):
            for repository in self._repositories:
                view = views.get(str(repository))
                if isinstance(view, dict):
                    self._views[str(repository)] = self._validated_view(view)

    @staticmethod
    def _validated_view(view: dict) -> dict:
        normalized: dict = {}
        zoom = view.get("zoom")
        if isinstance(zoom, (int, float)) and not isinstance(zoom, bool):
            normalized["zoom"] = min(2.0, max(0.35, float(zoom)))
        for field in ("scrollLeft", "scrollTop"):
            value = view.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                normalized[field] = min(10_000_000.0, max(0.0, float(value)))
        selected_id = view.get("selectedId")
        if isinstance(selected_id, str) and len(selected_id) <= 512:
            normalized["selectedId"] = selected_id
        visible_states = view.get("visibleStates")
        if isinstance(visible_states, list):
            normalized["visibleStates"] = sorted(
                {state for state in visible_states if state in VIEW_STATES}
            )
        visible_types = view.get("visibleTypes")
        if isinstance(visible_types, list):
            normalized["visibleTypes"] = sorted(
                {
                    value.strip()
                    for value in visible_types
                    if isinstance(value, str) and value.strip() and len(value) <= 128
                }
            )
        return normalized

    @contextmanager
    def _disk_lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.path.with_name(f"{self.path.name}.lock")
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            if os.name != "nt":
                lock_path.chmod(0o600)
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _save(self) -> None:
        payload = {
            "version": 1,
            "repositories": [str(path) for path in self._repositories],
            "selected": str(self._selected) if self._selected else None,
            "views": self._views,
        }
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            if os.name != "nt":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                descriptor = -1
                json.dump(payload, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
            raise

    @contextmanager
    def _current_state(self) -> Iterator[None]:
        with self._lock:
            with self._disk_lock():
                self._load(strict=True)
                yield

    def add(self, repository: Path, *, select: bool = True) -> None:
        with self._current_state():
            if repository not in self._repositories:
                self._repositories.append(repository)
            if select or self._selected is None:
                self._selected = repository
            self._save()

    def select(self, repository: Path) -> None:
        with self._current_state():
            if repository not in self._repositories:
                raise BeadsError("Repository is not in the catalog.")
            self._selected = repository
            self._save()

    def remove(self, repository: Path) -> None:
        with self._current_state():
            if repository not in self._repositories:
                raise BeadsError("Repository is not in the catalog.")
            self._repositories.remove(repository)
            self._views.pop(str(repository), None)
            if self._selected == repository:
                self._selected = self._repositories[0] if self._repositories else None
            self._save()

    def contains(self, repository: Path) -> bool:
        with self._current_state():
            return repository in self._repositories

    def selected(self) -> Path | None:
        with self._current_state():
            return self._selected

    def payload(self) -> dict:
        with self._current_state():
            return {
                "repositories": [
                    {"name": path.name or str(path), "path": str(path)}
                    for path in self._repositories
                ],
                "selected": str(self._selected) if self._selected else None,
                "views": self._views,
            }

    def save_view(self, repository: Path, view: dict) -> None:
        with self._current_state():
            if repository not in self._repositories:
                raise BeadsError("Repository is not in the catalog.")
            self._views[str(repository)] = self._validated_view(view)
            self._save()


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
            if dependency_type in DISPLAYED_DEPENDENCIES and source in by_id and target in by_id:
                if dependency_type in BLOCKING_DEPENDENCIES:
                    kind = "blocking"
                elif dependency_type == "discovered-from":
                    kind = "follow-on"
                else:
                    kind = "hierarchy"
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "type": dependency_type,
                        "kind": kind,
                    }
                )

    blockers: dict[str, list[str]] = {issue_id: [] for issue_id in by_id}
    dependents: dict[str, list[str]] = {issue_id: [] for issue_id in by_id}
    direct_children: dict[str, set[str]] = {issue_id: set() for issue_id in by_id}
    for edge in (edge for edge in edges if edge["kind"] == "blocking"):
        blockers[edge["target"]].append(edge["source"])
        dependents[edge["source"]].append(edge["target"])
    for edge in (edge for edge in edges if edge["kind"] == "hierarchy"):
        direct_children[edge["source"]].add(edge["target"])

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

        issue_type = str(issue.get("issue_type") or "work item")
        node = {
            "id": issue_id,
            "title": issue.get("title") or issue_id,
            "description": issue.get("description") or "",
            "type": issue_type,
            "rawStatus": raw_status,
            "state": state,
            "labels": sorted(issue.get("labels") or []),
            "assignee": issue.get("assignee") or "",
            "blockers": sorted(blockers[issue_id]),
            "activeBlockers": sorted(active_blockers),
            "dependents": sorted(dependents[issue_id]),
        }
        if issue_type.lower() == "epic":
            human_children = [
                by_id[child_id]
                for child_id in direct_children[issue_id]
                if str(by_id[child_id].get("issue_type") or "work item").lower()
                not in NON_HUMAN_ISSUE_TYPES
            ]
            if human_children:
                completed_children = sum(
                    str(child.get("status")) == "closed"
                    and not (child.get("defer_until") or child.get("deferred_until"))
                    for child in human_children
                )
                node["epicProgress"] = {
                    "completed": completed_children,
                    "total": len(human_children),
                }
        nodes.append(node)

    return {
        "repository": repository.name,
        "path": str(repository),
        "nodes": sorted(nodes, key=lambda node: node["id"]),
        "edges": sorted(
            edges,
            key=lambda edge: (edge["source"], edge["target"], edge["type"]),
        ),
    }


def graph_hash(graph: dict) -> str:
    canonical = json.dumps(graph, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SnapshotCoordinator:
    def __init__(self, loader: Callable[[Path], dict] | None = None):
        self._loader = loader or (
            lambda repository: normalize_graph(repository, export_issues(repository))
        )
        self._locks_lock = threading.Lock()
        self._repository_locks: dict[Path, threading.Lock] = {}
        self._snapshots: dict[Path, tuple[dict, str, str]] = {}

    def _lock_for(self, repository: Path) -> threading.Lock:
        with self._locks_lock:
            return self._repository_locks.setdefault(repository, threading.Lock())

    def refresh(self, repository: Path, current_hash: str | None = None) -> dict:
        with self._lock_for(repository):
            previous = self._snapshots.get(repository)
            try:
                graph = self._loader(repository)
                digest = graph_hash(graph)
                updated_at = datetime.now(timezone.utc).isoformat()
                self._snapshots[repository] = (graph, digest, updated_at)
                stale = False
                error_message = None
            except (BeadsError, OSError) as error:
                if previous is None:
                    raise
                graph, digest, updated_at = previous
                stale = True
                error_message = str(error)

            freshness = {
                "stale": stale,
                "error": error_message,
                "updatedAt": updated_at,
            }
            if current_hash == digest:
                return {
                    "unchanged": True,
                    "snapshotHash": digest,
                    "freshness": freshness,
                }
            return {
                **graph,
                "snapshotHash": digest,
                "freshness": freshness,
            }


class AppHandler(BaseHTTPRequestHandler):
    catalog: RepositoryCatalog
    snapshots: SnapshotCoordinator

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
        if path.startswith("/api/") and self.headers.get("X-Beads-Map") != "1":
            self._send_json(403, {"error": "Local preference update was not authorized."})
            return
        if path == "/api/repositories/pick":
            try:
                repository = pick_repository()
                if repository is None:
                    self._send_json(200, {"cancelled": True})
                    return
                graph = self.snapshots.refresh(repository)
                self.catalog.add(repository)
                self._send_json(200, {"catalog": self.catalog.payload(), "graph": graph})
            except (BeadsError, OSError) as error:
                self._send_json(400, {"error": str(error)})
            return
        try:
            payload = self._read_json()
            repository = resolve_repository(str(payload.get("path") or ""))
            if path == "/api/view":
                view = payload.get("view")
                if not isinstance(view, dict):
                    raise ValueError("View must be a JSON object.")
                self.catalog.save_view(repository, view)
                self._send_json(200, {"saved": True})
                return
            if path == "/api/repositories":
                graph = self.snapshots.refresh(repository)
                self.catalog.add(repository)
                self._send_json(200, {"catalog": self.catalog.payload(), "graph": graph})
                return
            if path == "/api/repositories/select":
                if not self.catalog.contains(repository):
                    self._send_json(404, {"error": "Repository is not in the catalog."})
                    return
                graph = self.snapshots.refresh(repository)
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
        if self.headers.get("X-Beads-Map") != "1":
            self._send_json(403, {"error": "Local preference update was not authorized."})
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
            query = parse_qs(urlsplit(self.path).query)
            current_hash = query.get("hash", [None])[0]
            payload = self.snapshots.refresh(repository, current_hash)
            self._send_json(200, payload)
        except (BeadsError, OSError) as error:
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
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_json(self, status: int, value: dict) -> None:
        body = json.dumps(value).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format: str, *args: object) -> None:
        print(f"[beads-map] {format % args}")


def port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65_535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repositories",
        nargs="*",
        metavar="repository",
        help="Beads repository paths to remember",
    )
    parser.add_argument(
        "--port",
        type=port_number,
        help="Local HTTP port (default: 8765, with automatic fallback)",
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def create_server(port: int, *, strict: bool) -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer(("127.0.0.1", port), AppHandler)
    except OSError as error:
        if strict:
            raise BeadsError(f"Could not use explicit port {port}: {error}") from error
    try:
        return ThreadingHTTPServer(("127.0.0.1", 0), AppHandler)
    except OSError as error:
        raise BeadsError(f"Could not start a local server: {error}") from error


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        ensure_supported_bd()
    except BeadsError as error:
        print(error, file=sys.stderr)
        return 2

    catalog = RepositoryCatalog(default_catalog_path())
    snapshots = SnapshotCoordinator()
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
            graph = snapshots.refresh(selected)
        except BeadsError as error:
            print(f"Could not read selected repository yet: {error}", file=sys.stderr)

    AppHandler.catalog = catalog
    AppHandler.snapshots = snapshots
    try:
        server = create_server(args.port or 8765, strict=args.port is not None)
    except BeadsError as error:
        print(error, file=sys.stderr)
        return 2

    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}"
    if graph:
        print(
            f"Beads Map: {graph['repository']} · {len(graph['nodes'])} issues · "
            f"{len(graph['edges'])} relationships"
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
