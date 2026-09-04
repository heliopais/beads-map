#!/usr/bin/env python3
"""Exercise one external-beta browser journey against a real Beads database."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import traceback

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import beads_map


def run(command: list[str], repository: Path) -> str:
    result = subprocess.run(
        command,
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout.strip()


def create_issue(repository: Path, title: str, description: str) -> str:
    return run(
        [
            "bd",
            "create",
            title,
            "--description",
            description,
            "--type",
            "task",
            "--silent",
        ],
        repository,
    )


def build_real_repository(root: Path) -> tuple[Path, dict[str, str], list[dict]]:
    repository = root / "real-beads-fixture"
    repository.mkdir()
    run(["git", "init", "-q"], repository)
    run(
        [
            "bd",
            "init",
            "--non-interactive",
            "--skip-agents",
            "--skip-hooks",
            "--prefix",
            "journey",
        ],
        repository,
    )
    ids = {
        "completed": create_issue(
            repository,
            "Completed integration task",
            "Already-finished browser fixture work.",
        ),
        "ready": create_issue(
            repository,
            "Ready integration task",
            "Ready details body from the real Beads database.",
        ),
        "blocked": create_issue(
            repository,
            "Blocked integration task",
            "Depends on the ready integration task.",
        ),
    }
    run(["bd", "close", ids["completed"]], repository)
    run(["bd", "dep", "add", ids["blocked"], ids["ready"]], repository)
    exported = beads_map.export_issues(repository)
    if len(exported) != 3:
        raise AssertionError(f"Expected three real Beads issues; found {len(exported)}")
    return repository, ids, exported


def chrome_service() -> Service:
    configured = os.environ.get("CHROMEWEBDRIVER", "")
    candidates = [Path(configured), Path(configured) / "chromedriver"] if configured else []
    executable = next((candidate for candidate in candidates if candidate.is_file()), None)
    return Service(executable_path=str(executable)) if executable else Service()


def wait_for(wait: WebDriverWait, description: str, predicate):
    try:
        return wait.until(lambda driver: predicate(driver) or False)
    except TimeoutException as error:
        raise AssertionError(f"Timed out waiting for {description}") from error


def save_failure_artifacts(
    artifacts: Path,
    driver,
    diagnostic: dict,
) -> None:
    artifacts.mkdir(parents=True, exist_ok=True)
    if driver is not None:
        try:
            driver.save_screenshot(str(artifacts / "browser-failure.png"))
            (artifacts / "page-source.html").write_text(
                driver.page_source,
                encoding="utf-8",
            )
            diagnostic["currentUrl"] = driver.current_url
            diagnostic["title"] = driver.title
            diagnostic["browserConsole"] = driver.get_log("browser")
        except Exception as artifact_error:  # diagnostics must not mask the failure
            diagnostic["artifactError"] = repr(artifact_error)
    (artifacts / "diagnostic.json").write_text(
        json.dumps(diagnostic, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path(os.environ.get("BROWSER_ARTIFACTS", "browser-artifacts")),
        help="Directory for failure-only browser diagnostics",
    )
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    driver = None
    server = None
    diagnostic: dict = {"python": sys.version, "platform": sys.platform}

    try:
        version = beads_map.ensure_supported_bd()
        diagnostic["bdVersion"] = ".".join(str(part) for part in version)
        with tempfile.TemporaryDirectory(prefix="beads-map-browser-") as temporary:
            root = Path(temporary)
            repository, ids, exported = build_real_repository(root)
            diagnostic.update(
                {
                    "issueIds": ids,
                    "exportedIssues": [issue["id"] for issue in exported],
                }
            )

            catalog = beads_map.RepositoryCatalog(root / "repositories.json")
            beads_map.AppHandler.catalog = catalog
            beads_map.AppHandler.snapshots = beads_map.SnapshotCoordinator()
            server = beads_map.create_server(0, strict=True)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            diagnostic["baseUrl"] = base_url

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1440,900")
            options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
            driver = webdriver.Chrome(service=chrome_service(), options=options)
            wait = WebDriverWait(driver, 12)

            driver.get(base_url)
            wait_for(
                wait,
                "the empty first-run state",
                lambda browser: browser.find_element(By.ID, "first-run").is_displayed(),
            )
            first_run = driver.find_element(By.ID, "first-run")
            if "Map your Beads work" not in first_run.text:
                raise AssertionError("First-run guidance did not explain how to begin")

            catalog.add(repository)
            driver.refresh()
            wait_for(
                wait,
                "three nodes loaded from the real Beads database",
                lambda browser: len(browser.find_elements(By.CSS_SELECTOR, ".node")) == 3,
            )
            counts = driver.find_element(By.ID, "counts").text
            if "3 issues" not in counts or "1 relationship" not in counts:
                raise AssertionError(f"Unexpected loaded graph summary: {counts}")

            completed_filter = driver.find_element(
                By.CSS_SELECTOR,
                '[data-state="completed"]',
            )
            completed_filter.click()
            wait_for(
                wait,
                "the completed filter to hide finished work",
                lambda browser: browser.find_element(By.ID, "counts").text.startswith(
                    "2 of 3 issues"
                ),
            )
            if driver.find_elements(By.CSS_SELECTOR, f'.node[data-id="{ids["completed"]}"]'):
                raise AssertionError("Completed filter left the completed issue visible")

            ready_node = driver.find_element(
                By.CSS_SELECTOR,
                f'.node[data-id="{ids["ready"]}"]',
            )
            ready_node.click()
            wait_for(
                wait,
                "selected issue details",
                lambda browser: browser.find_element(By.ID, "detail-title").text
                == "Ready integration task",
            )
            if "Ready details body" not in driver.find_element(
                By.ID,
                "detail-description",
            ).get_attribute("textContent"):
                raise AssertionError("Selected details did not contain the real description")
            if ids["blocked"] not in driver.find_element(
                By.ID,
                "detail-dependents",
            ).get_attribute("textContent"):
                raise AssertionError("Selected details did not contain the real dependent")

            console_errors = [
                entry
                for entry in driver.get_log("browser")
                if entry.get("level") == "SEVERE"
            ]
            if console_errors:
                raise AssertionError(f"Browser console errors: {console_errors}")

            # Stop the browser and server before TemporaryDirectory removes the
            # repository they are still able to poll.
            driver.quit()
            driver = None
            server.shutdown()
            server.server_close()
            server = None

        print(
            "Browser journey passed: empty state, real-bd load, status filter, "
            "selection, details, and relationship context"
        )
        return 0
    except Exception as error:
        diagnostic["error"] = repr(error)
        diagnostic["traceback"] = traceback.format_exc()
        save_failure_artifacts(artifacts, driver, diagnostic)
        print(diagnostic["traceback"], file=sys.stderr)
        print(f"Failure diagnostics: {artifacts}", file=sys.stderr)
        return 1
    finally:
        if driver is not None:
            driver.quit()
        if server is not None:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
