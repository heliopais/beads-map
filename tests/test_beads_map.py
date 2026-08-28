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
from urllib.error import HTTPError
from urllib.request import Request, urlopen
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

    def test_epic_progress_counts_only_direct_human_children(self) -> None:
        def child(
            issue_id: str,
            status: str,
            parent_id: str,
            issue_type: str = "task",
            **fields: object,
        ) -> dict:
            return {
                "id": issue_id,
                "title": issue_id,
                "status": status,
                "issue_type": issue_type,
                "dependencies": [
                    {
                        "issue_id": issue_id,
                        "depends_on_id": parent_id,
                        "type": "parent-child",
                    }
                ],
                **fields,
            }

        issues = [
            {"id": "epic", "title": "Epic", "status": "open", "issue_type": "epic"},
            child("closed-child", "closed", "epic"),
            child("open-child", "open", "epic"),
            child("deferred-child", "open", "epic", deferred_until="tomorrow"),
            child("system-child", "closed", "epic", issue_type="agent"),
            child("nested-child", "closed", "open-child"),
            {
                "id": "empty-epic",
                "title": "Empty",
                "status": "closed",
                "issue_type": "epic",
            },
        ]

        graph = beads_map.normalize_graph(ROOT, issues)
        nodes = {node["id"]: node for node in graph["nodes"]}

        self.assertEqual(nodes["epic"]["epicProgress"], {"completed": 1, "total": 3})
        self.assertEqual(nodes["epic"]["rawStatus"], "open")
        self.assertEqual(nodes["epic"]["state"], "ready")
        self.assertEqual(nodes["deferred-child"]["state"], "deferred")
        self.assertNotIn("epicProgress", nodes["open-child"])
        self.assertNotIn("epicProgress", nodes["empty-epic"])

    def test_hash_is_stable_when_export_order_changes(self) -> None:
        issues = [
            {"id": "b", "title": "B", "status": "open", "labels": ["z", "a"]},
            {"id": "a", "title": "A", "status": "closed"},
        ]

        first = beads_map.normalize_graph(ROOT, issues)
        second = beads_map.normalize_graph(ROOT, list(reversed(issues)))

        self.assertEqual(beads_map.graph_hash(first), beads_map.graph_hash(second))

    def test_normalize_graph_preserves_available_detail_metadata(self) -> None:
        graph = beads_map.normalize_graph(
            ROOT,
            [{
                "id": "detail",
                "title": "Detail",
                "status": "in_progress",
                "priority": 1,
                "created_at": "2026-08-01T10:00:00Z",
                "updated_at": "2026-08-02T11:00:00Z",
                "started_at": "2026-08-02T10:30:00Z",
                "closed_at": None,
            }],
        )

        node = graph["nodes"][0]
        self.assertEqual(node["priority"], 1)
        self.assertEqual(node["createdAt"], "2026-08-01T10:00:00Z")
        self.assertEqual(node["updatedAt"], "2026-08-02T11:00:00Z")
        self.assertEqual(node["startedAt"], "2026-08-02T10:30:00Z")
        self.assertEqual(node["closedAt"], "")


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


class MetadataUpdateTests(unittest.TestCase):
    def valid_payload(self) -> dict:
        return {
            "repository": str(ROOT),
            "issueId": "beads-map-123",
            "snapshotHash": "a" * 64,
            "fields": {
                "title": "  Updated title  ",
                "description": "Updated description",
                "priority": 1,
                "assignee": "  Helio  ",
                "labels": ["beta", "alpha", "beta"],
            },
        }

    def test_update_request_is_allowlisted_and_normalized(self) -> None:
        repository, issue_id, snapshot_hash, fields = (
            beads_map.validate_update_request(self.valid_payload())
        )

        self.assertEqual(repository, str(ROOT))
        self.assertEqual(issue_id, "beads-map-123")
        self.assertEqual(snapshot_hash, "a" * 64)
        self.assertEqual(fields["title"], "Updated title")
        self.assertEqual(fields["assignee"], "Helio")
        self.assertEqual(fields["labels"], ["alpha", "beta"])

    def test_update_request_rejects_unsupported_and_invalid_fields(self) -> None:
        cases = []
        unsupported = self.valid_payload()
        unsupported["fields"] = {**unsupported["fields"], "status": "closed"}
        cases.append(unsupported)
        empty_title = self.valid_payload()
        empty_title["fields"] = {**empty_title["fields"], "title": "   "}
        cases.append(empty_title)
        boolean_priority = self.valid_payload()
        boolean_priority["fields"] = {**boolean_priority["fields"], "priority": True}
        cases.append(boolean_priority)
        invalid_label = self.valid_payload()
        invalid_label["fields"] = {**invalid_label["fields"], "labels": ["bad\nlabel"]}
        cases.append(invalid_label)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    beads_map.validate_update_request(payload)

    def test_bd_update_uses_one_argument_list_and_exact_label_delta(self) -> None:
        fields = self.valid_payload()["fields"]
        fields["title"] = "Updated title"
        fields["assignee"] = ""
        fields["description"] = ""
        fields["labels"] = ["keep", "new"]
        result = subprocess.CompletedProcess(["bd", "update"], 0, stdout="", stderr="")

        with patch("beads_map.subprocess.run", return_value=result) as run:
            beads_map.update_issue_metadata(
                ROOT,
                "beads-map-123",
                fields,
                {"labels": ["keep", "old"]},
            )

        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["bd", "-C", str(ROOT), "update", "beads-map-123"])
        self.assertIn("--allow-empty-description", command)
        self.assertIn("--add-label", command)
        self.assertIn("new", command)
        self.assertIn("--remove-label", command)
        self.assertIn("old", command)
        self.assertNotIn("shell", run.call_args.kwargs)
        run.assert_called_once()

    def test_bd_update_failure_is_readable(self) -> None:
        fields = self.valid_payload()["fields"]
        result = subprocess.CompletedProcess(
            ["bd", "update"], 1, stdout="", stderr="database busy"
        )
        with patch("beads_map.subprocess.run", return_value=result):
            with self.assertRaisesRegex(beads_map.BeadsError, "database busy"):
                beads_map.update_issue_metadata(ROOT, "beads-map-123", fields, {})

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

    def test_metadata_update_checks_hash_writes_and_returns_fresh_graph(self) -> None:
        original = {
            "repository": "repo",
            "path": str(ROOT),
            "nodes": [{"id": "item", "title": "Before", "labels": ["old"]}],
            "edges": [],
        }
        updated = {
            **original,
            "nodes": [{"id": "item", "title": "After", "labels": ["new"]}],
        }
        graphs = iter([original, updated])
        writes = []
        coordinator = beads_map.SnapshotCoordinator(
            lambda repository: next(graphs),
            lambda *arguments: writes.append(arguments),
        )

        response = coordinator.update_issue(
            ROOT,
            "item",
            beads_map.graph_hash(original),
            {"title": "After", "labels": ["new"]},
        )

        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1], "item")
        self.assertEqual(response["nodes"][0]["title"], "After")
        self.assertEqual(response["snapshotHash"], beads_map.graph_hash(updated))
        self.assertFalse(response["freshness"]["stale"])

    def test_metadata_update_rejects_conflict_before_write(self) -> None:
        graph = {
            "repository": "repo",
            "path": str(ROOT),
            "nodes": [{"id": "item"}],
            "edges": [],
        }
        writes = []
        coordinator = beads_map.SnapshotCoordinator(
            lambda repository: graph,
            lambda *arguments: writes.append(arguments),
        )

        with self.assertRaises(beads_map.SnapshotConflict) as raised:
            coordinator.update_issue(ROOT, "item", "0" * 64, {})

        self.assertEqual(raised.exception.snapshot_hash, beads_map.graph_hash(graph))
        self.assertEqual(writes, [])

    def test_metadata_update_rejects_unknown_issue_before_write(self) -> None:
        graph = {
            "repository": "repo",
            "path": str(ROOT),
            "nodes": [],
            "edges": [],
        }
        writes = []
        coordinator = beads_map.SnapshotCoordinator(
            lambda repository: graph,
            lambda *arguments: writes.append(arguments),
        )

        with self.assertRaises(beads_map.IssueNotFound):
            coordinator.update_issue(ROOT, "missing", beads_map.graph_hash(graph), {})

        self.assertEqual(writes, [])

    def test_failed_post_write_refresh_keeps_preflight_snapshot(self) -> None:
        graph = {
            "repository": "repo",
            "path": str(ROOT),
            "nodes": [{"id": "item"}],
            "edges": [],
        }
        outcomes = iter([graph, beads_map.BeadsError("refresh failed")])

        def loader(repository: Path) -> dict:
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        coordinator = beads_map.SnapshotCoordinator(loader, lambda *arguments: None)
        with self.assertRaisesRegex(beads_map.BeadsError, "refresh failed"):
            coordinator.update_issue(ROOT, "item", beads_map.graph_hash(graph), {})

        self.assertEqual(coordinator._snapshots[ROOT][0], graph)


class MetadataUpdateEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name).resolve()
        catalog = beads_map.RepositoryCatalog(self.repository / "catalog.json")
        catalog.add(self.repository)
        self.state = {
            "repository": self.repository.name,
            "path": str(self.repository),
            "nodes": [{"id": "item", "title": "Before", "labels": []}],
            "edges": [],
        }

        def updater(repository: Path, issue_id: str, fields: dict, node: dict) -> None:
            self.state = {
                **self.state,
                "nodes": [{**node, **fields}],
            }

        beads_map.AppHandler.catalog = catalog
        beads_map.AppHandler.snapshots = beads_map.SnapshotCoordinator(
            lambda repository: self.state,
            updater,
        )
        self.server = beads_map.ThreadingHTTPServer(
            ("127.0.0.1", 0), beads_map.AppHandler
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, payload: dict, *, authorized: bool = True) -> tuple[int, dict]:
        return self.request_bytes(json.dumps(payload).encode("utf-8"), authorized=authorized)

    def request_bytes(self, body: bytes, *, authorized: bool = True) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["X-Beads-Map"] = "1"
        request = Request(
            f"http://127.0.0.1:{self.server.server_address[1]}/api/issues/update",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            return error.code, json.loads(error.read())
        with response:
            return response.status, json.loads(response.read())

    def payload(self) -> dict:
        return {
            "repository": str(self.repository),
            "issueId": "item",
            "snapshotHash": beads_map.graph_hash(self.state),
            "fields": {
                "title": "After",
                "description": "Description",
                "priority": 2,
                "assignee": "Helio",
                "labels": ["edited"],
            },
        }

    def test_endpoint_requires_header_and_selected_repository(self) -> None:
        status, _ = self.request(self.payload(), authorized=False)
        self.assertEqual(status, 403)

        payload = self.payload()
        payload["repository"] = str(ROOT)
        status, _ = self.request(payload)
        self.assertEqual(status, 404)

    def test_endpoint_reports_validation_conflict_and_unknown_issue(self) -> None:
        invalid = self.payload()
        invalid["fields"] = {**invalid["fields"], "status": "closed"}
        status, _ = self.request(invalid)
        self.assertEqual(status, 400)

        stale = self.payload()
        stale["snapshotHash"] = "0" * 64
        status, response = self.request(stale)
        self.assertEqual(status, 409)
        self.assertEqual(response["snapshotHash"], beads_map.graph_hash(self.state))

        missing = self.payload()
        missing["issueId"] = "missing"
        status, _ = self.request(missing)
        self.assertEqual(status, 404)

    def test_endpoint_rejects_malformed_and_oversized_bodies(self) -> None:
        status, _ = self.request_bytes(b"{")
        self.assertEqual(status, 400)

        status, _ = self.request_bytes(b"x" * 16_385)
        self.assertEqual(status, 400)

    def test_endpoint_reports_write_failure_without_changing_graph(self) -> None:
        original = self.state

        def fail_update(*arguments: object) -> None:
            raise beads_map.BeadsError("database busy")

        beads_map.AppHandler.snapshots = beads_map.SnapshotCoordinator(
            lambda repository: self.state,
            fail_update,
        )
        status, response = self.request(self.payload())

        self.assertEqual(status, 500)
        self.assertEqual(response["error"], "database busy")
        self.assertIs(self.state, original)

    def test_endpoint_returns_fresh_canonical_graph(self) -> None:
        status, response = self.request(self.payload())

        self.assertEqual(status, 200)
        self.assertEqual(response["nodes"][0]["title"], "After")
        self.assertEqual(response["nodes"][0]["labels"], ["edited"])
        self.assertEqual(response["snapshotHash"], beads_map.graph_hash(self.state))


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
                "visibleTypes": ["feature", "task", "feature", "", 7],
                "nodes": [{"id": "must-not-persist"}],
            },
        )

        payload = beads_map.RepositoryCatalog(self.catalog_path).payload()
        view = payload["views"][str(ROOT)]
        self.assertEqual(view["zoom"], 1.4)
        self.assertEqual(view["selectedId"], "beads-map-ow0")
        self.assertEqual(view["visibleStates"], ["in-progress", "ready"])
        self.assertEqual(view["visibleTypes"], ["feature", "task"])
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
