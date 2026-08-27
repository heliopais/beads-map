from __future__ import annotations

import json
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import beads_map


ROOT = Path(__file__).resolve().parents[1]


class VersionTests(unittest.TestCase):
    def test_parse_bd_version(self) -> None:
        self.assertEqual(
            beads_map.parse_bd_version("bd version 1.2.3 (build)"),
            (1, 2, 3),
        )

    def test_supported_bd_version_is_returned(self) -> None:
        result = subprocess.CompletedProcess(
            ["bd", "version"], 0, stdout="bd version 1.1.0\n", stderr=""
        )
        with patch("beads_map.subprocess.run", return_value=result):
            self.assertEqual(beads_map.ensure_supported_bd(), (1, 1, 0))

    def test_unsupported_bd_version_has_upgrade_guidance(self) -> None:
        result = subprocess.CompletedProcess(
            ["bd", "version"], 0, stdout="bd version 1.0.4\n", stderr=""
        )
        with patch("beads_map.subprocess.run", return_value=result):
            with self.assertRaisesRegex(beads_map.BeadsError, "Upgrade Beads"):
                beads_map.ensure_supported_bd()


class ServerTests(unittest.TestCase):
    def test_implicit_port_falls_back_when_occupied(self) -> None:
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            server = beads_map.create_server(port, strict=False)
            self.addCleanup(server.server_close)
            self.assertNotEqual(server.server_address[1], port)

    def test_explicit_port_is_strict(self) -> None:
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            with self.assertRaisesRegex(beads_map.BeadsError, "explicit port"):
                beads_map.create_server(port, strict=True)


class GraphNormalizationTests(unittest.TestCase):
    def test_nonblocking_relationships_render_without_blocking_work(self) -> None:
        issues = [
            {"id": "origin", "title": "Origin", "status": "closed"},
            {"id": "epic", "title": "Epic", "status": "open", "issue_type": "epic"},
            {"id": "blocker", "title": "Blocker", "status": "open"},
            {
                "id": "follow-on",
                "title": "Follow-on",
                "status": "open",
                "dependencies": [
                    {"issue_id": "follow-on", "depends_on_id": "origin", "type": "discovered-from"},
                    {"issue_id": "follow-on", "depends_on_id": "epic", "type": "parent-child"},
                ],
            },
            {
                "id": "blocked",
                "title": "Blocked",
                "status": "open",
                "dependencies": [
                    {"issue_id": "blocked", "depends_on_id": "blocker", "type": "blocks"},
                ],
            },
        ]

        graph = beads_map.normalize_graph(ROOT, issues)
        edges = {(edge["type"], edge["kind"]) for edge in graph["edges"]}
        nodes = {node["id"]: node for node in graph["nodes"]}

        self.assertEqual(
            edges,
            {
                ("blocks", "blocking"),
                ("discovered-from", "follow-on"),
                ("parent-child", "hierarchy"),
            },
        )
        self.assertEqual(nodes["follow-on"]["state"], "ready")
        self.assertEqual(nodes["follow-on"]["blockers"], [])
        self.assertEqual(nodes["blocked"]["state"], "blocked")
        self.assertEqual(nodes["blocked"]["blockers"], ["blocker"])

    def test_hash_is_stable_when_export_order_changes(self) -> None:
        issues = [
            {"id": "b", "title": "B", "status": "open", "labels": ["z", "a"]},
            {"id": "a", "title": "A", "status": "closed"},
        ]

        first = beads_map.normalize_graph(ROOT, issues)
        second = beads_map.normalize_graph(ROOT, list(reversed(issues)))

        self.assertEqual(beads_map.graph_hash(first), beads_map.graph_hash(second))


class ExportTests(unittest.TestCase):
    def test_timeout_has_readable_error(self) -> None:
        with patch(
            "beads_map.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["bd", "export"], 20),
        ):
            with self.assertRaisesRegex(beads_map.BeadsError, "Timed out"):
                beads_map.export_issues(ROOT)

    def test_malformed_export_has_line_number(self) -> None:
        result = subprocess.CompletedProcess(
            ["bd", "export"], 0, stdout='{"id":"ok"}\nnot-json\n', stderr=""
        )
        with patch("beads_map.subprocess.run", return_value=result):
            with self.assertRaisesRegex(beads_map.BeadsError, "line 2"):
                beads_map.export_issues(ROOT)


class SnapshotTests(unittest.TestCase):
    def test_unchanged_snapshot_returns_metadata_without_graph(self) -> None:
        graph = {"repository": "repo", "path": str(ROOT), "nodes": [], "edges": []}
        coordinator = beads_map.SnapshotCoordinator(lambda repository: graph)

        first = coordinator.refresh(ROOT)
        second = coordinator.refresh(ROOT, first["snapshotHash"])

        self.assertTrue(second["unchanged"])
        self.assertNotIn("nodes", second)
        self.assertFalse(second["freshness"]["stale"])

    def test_failed_refresh_keeps_and_marks_last_good_graph(self) -> None:
        graph = {"repository": "repo", "path": str(ROOT), "nodes": [], "edges": []}
        outcomes = iter([graph, beads_map.BeadsError("temporary failure")])

        def loader(repository: Path) -> dict:
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        coordinator = beads_map.SnapshotCoordinator(loader)
        first = coordinator.refresh(ROOT)
        second = coordinator.refresh(ROOT, first["snapshotHash"])

        self.assertTrue(second["unchanged"])
        self.assertTrue(second["freshness"]["stale"])
        self.assertEqual(second["freshness"]["error"], "temporary failure")

    def test_refreshes_are_serialized_per_repository(self) -> None:
        active = 0
        maximum_active = 0
        first_entered = threading.Event()
        release_first = threading.Event()
        count_lock = threading.Lock()
        graph = {"repository": "repo", "path": str(ROOT), "nodes": [], "edges": []}

        def loader(repository: Path) -> dict:
            nonlocal active, maximum_active
            with count_lock:
                active += 1
                maximum_active = max(maximum_active, active)
                is_first = not first_entered.is_set()
            if is_first:
                first_entered.set()
                release_first.wait(timeout=1)
            with count_lock:
                active -= 1
            return graph

        coordinator = beads_map.SnapshotCoordinator(loader)
        first = threading.Thread(target=coordinator.refresh, args=(ROOT,))
        second = threading.Thread(target=coordinator.refresh, args=(ROOT,))
        first.start()
        self.assertTrue(first_entered.wait(timeout=1))
        second.start()
        release_first.set()
        first.join(timeout=1)
        second.join(timeout=1)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(maximum_active, 1)


class RepositoryCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.catalog_path = Path(self.temporary_directory.name) / "repositories.json"

    def test_legacy_catalog_is_loaded_and_upgraded_atomically(self) -> None:
        self.catalog_path.write_text(
            json.dumps({"repositories": [str(ROOT)], "selected": str(ROOT)}),
            encoding="utf-8",
        )
        catalog = beads_map.RepositoryCatalog(self.catalog_path)

        catalog.add(Path(self.temporary_directory.name))

        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)
        self.assertEqual(len(payload["repositories"]), 2)
        self.assertEqual(list(self.catalog_path.parent.glob(".*.tmp")), [])

    def test_independent_sessions_merge_catalog_updates(self) -> None:
        first = beads_map.RepositoryCatalog(self.catalog_path)
        second = beads_map.RepositoryCatalog(self.catalog_path)
        repository_a = ROOT
        repository_b = Path(self.temporary_directory.name)

        threads = [
            threading.Thread(target=first.add, args=(repository_a,)),
            threading.Thread(target=second.add, args=(repository_b,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        repositories = {
            item["path"] for item in beads_map.RepositoryCatalog(self.catalog_path).payload()["repositories"]
        }
        self.assertEqual(repositories, {str(repository_a.resolve()), str(repository_b.resolve())})

    def test_malformed_catalog_is_not_overwritten(self) -> None:
        self.catalog_path.write_text("not-json", encoding="utf-8")
        catalog = beads_map.RepositoryCatalog(self.catalog_path)

        with self.assertRaisesRegex(beads_map.BeadsError, "Could not read"):
            catalog.add(ROOT)
        self.assertEqual(self.catalog_path.read_text(encoding="utf-8"), "not-json")

    def test_view_metadata_round_trips_without_issue_data(self) -> None:
        catalog = beads_map.RepositoryCatalog(self.catalog_path)
        catalog.add(ROOT)

        catalog.save_view(
            ROOT,
            {
                "zoom": 1.4,
                "scrollLeft": 120,
                "scrollTop": 80,
                "selectedId": "beads-map-ow0",
                "visibleStates": ["ready", "in-progress"],
                "nodes": [{"id": "must-not-persist"}],
            },
        )

        payload = beads_map.RepositoryCatalog(self.catalog_path).payload()
        view = payload["views"][str(ROOT)]
        self.assertEqual(view["zoom"], 1.4)
        self.assertEqual(view["selectedId"], "beads-map-ow0")
        self.assertEqual(view["visibleStates"], ["in-progress", "ready"])
        self.assertNotIn("nodes", view)
        if beads_map.os.name != "nt":
            mode = stat.S_IMODE(self.catalog_path.stat().st_mode)
            self.assertEqual(mode, 0o600)


class PackagingSmokeTests(unittest.TestCase):
    def test_web_asset_exists(self) -> None:
        self.assertTrue((beads_map.WEB_ROOT / "index.html").is_file())

    def test_source_launcher_help(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "beads_map.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--no-browser", result.stdout)


if __name__ == "__main__":
    unittest.main()
