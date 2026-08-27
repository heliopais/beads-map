from __future__ import annotations

import socket
import subprocess
import sys
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
