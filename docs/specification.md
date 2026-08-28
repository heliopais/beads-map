# Beads Map product specification

## Product

Beads Map is a local web application for understanding the current work in one
Beads repository at a time. Its main surface is the dependency DAG:
blockers flow from left to right into the work they block. A user can keep a
catalog of local repositories and switch between their separate graphs, but the
application never joins repositories into one graph.

The existing POC is the implementation baseline. The first release packages and
hardens it; it does not replace it with a new stack.

### In scope

- Show all human-facing work, including unlinked work, in the active repository.
- Represent `blocks`, `conditional-blocks`, and `waits-for` as solid prerequisite edges.
- Represent `discovered-from` as a dashed, nonblocking follow-on edge.
- Represent parent-child organization as a visually distinct dotted hierarchy edge.
- Derive blocking state and blocker/dependent details from prerequisite edges only.
- Derive the display states Completed, In progress, Ready, Blocked, and Deferred.
- Keep closed work connected and dim it by default.
- Distinguish work type independently from state, with a stronger accent for
  epics and redundant text/icon/color state cues.
- Pan, zoom, fit, re-layout, select work, inspect details, and navigate
  relationships with the keyboard.
- Search without hiding the graph. Provide explicit state, type, label, and
  assignee filters, plus transitive Blockers, Dependents, and Both path focus.
- Show unweighted counts for the five execution states. For an epic, optionally
  show `completed / total` across its direct human-facing children only.
- Remember repositories and each repository's view state locally.
- Refresh the active repository automatically and on demand without disturbing
  the current view when its graph has not changed.
- Explicitly edit title, description, priority, assignee, and labels for the
  selected bead, with stale-snapshot protection and a canonical refresh.

### Out of scope

- Creating or deleting Beads records; changing status, type, workflow state, or
  relationships; claiming, closing, deferring, reopening, or syncing work.
- A cross-repository graph or portfolio summary.
- History, trends, time travel, hosted collaboration, or stakeholder reports.
- Persisted manual node placement, semantic clustering, a daemon, a tray app, or
  automatic update checks.

## User-visible behavior

The command is `beads-map [repository ...]`. It runs in the foreground on a
loopback address and opens the default browser unless `--no-browser` is passed.
`Ctrl-C` stops it. It tries port 8765; if that implicit port is unavailable it
chooses another free loopback port. An explicitly supplied `--port` is strict.

Repositories passed on the command line are added to the local catalog and the
first is selected. With no arguments, the last selection is restored. With an
empty catalog, the current directory is used when it is a valid Beads repository;
otherwise the empty application opens so the user can choose a folder. macOS has
a native folder picker. Linux is best-effort through command-line paths; Windows
is not supported in the first release.

Each catalog entry identifies one local working copy by canonical real path.
Aliases deduplicate, while distinct working copies stay distinct. Missing,
unreadable, moved, or invalid entries remain visible and offer Retry, Locate, and
catalog-only Remove. A failed repository switch leaves the current graph intact.
A failed refresh retains the last good graph in memory and marks it stale. No
issue data survives application restart. Edit drafts are also in-memory only.

The stable layout runs left to right from originating or prerequisite work to its
children, follow-ons, and dependent outcomes.
Filtering and path focus preserve positions, and a refresh re-lays out only graph
components whose dependencies changed. The initial graph is usable within two
seconds at 500 nodes and 1,500 edges, and within five seconds at 1,000 nodes and
3,000 edges on a development reference machine. Above that envelope, show the
complete counts and ask the user to narrow the graph. If rendering optimization
is required, it must preserve the full graph's meaning and interactions.

## Implementation architecture

Use one Python foreground process, the Python standard-library HTTP server,
packaged HTML/CSS/vanilla JavaScript, and native SVG. Keep direct function
composition and at most three focused Python responsibilities:

1. Application entry point, CLI lifecycle, and loopback HTTP server.
2. Beads reading, normalization, snapshot hashing, refresh coordination, and
   the allowlisted metadata-update boundary.
3. Repository catalog and per-repository view persistence.

These responsibilities may begin as three modules beside the packaged web asset.
Do not add a web framework, Node build, frontend bundler, graph library,
application database, plugin system, dependency-injection framework, or layered
repository abstractions without a measured need.

### Data flow

Only the Python process invokes Beads. For the selected repository it starts one
short-lived read at a time, normalizes the complete result, calculates a
canonical content hash, and atomically replaces the in-memory graph only after a
successful read. The browser periodically asks whether the active snapshot hash
changed and requests the new graph only when needed. Manual refresh uses the same
path. The browser owns transient interaction state; the server owns snapshots,
catalog state, and persisted view metadata.

Metadata editing uses an explicit details-panel mode. Save sends the selected
repository, bead ID, edit-start snapshot hash, and the complete five-field
allowlist. The server serializes refresh, hash comparison, one shell-free `bd
update`, and canonical refresh with the same per-repository coordinator. A stale
hash returns a conflict before writing; validation, conflicts, and failures keep
the browser draft intact.

Use the installed `bd` CLI as the sole Beads boundary:

```text
bd --readonly -C <repository> export
bd -C <repository> update <issue-id> <allowlisted metadata flags>
```

Normalize issues, labels, comments, raw status, parent links, and dependencies
behind that boundary. Hydrate only dependency endpoints missing from the export,
using bounded, read-only `bd show ... --json` calls. Require `bd >= 1.1.0, < 2.0.0`
and provide an actionable diagnostic for missing or unsupported versions.

Do not read Dolt or `.beads/issues.jsonl` directly, run `bd dolt pull`, use MCP as
the data plane, or keep a `bd --watch` process alive. Bound subprocess duration,
serialize reads per repository, and tolerate unknown fields and dependency types.

### Local persistence and safety

Store one versioned JSON document in the operating system's user configuration
directory. It contains repository paths, the last selection, and per-repository
view metadata such as viewport, selection, and completed-work visibility. It
contains no issue, comment, dependency, or graph snapshot data.

For every catalog mutation, take a short advisory file lock, reload the latest
document, merge the mutation, and save by atomic replacement. Protect the file
with user-only permissions where the platform supports them. Do not scan the
filesystem for repositories or disclose catalog paths over the network.

Bind only to loopback. Serve the application and its JSON interface from the same
origin, send no permissive CORS headers, and reject state-changing requests that
lack the application header. Catalog/view requests change local preferences
only. `POST /api/issues/update` is the sole Beads mutation endpoint and accepts
only title, description, priority, assignee, and labels for the selected
repository and a bead present in the freshly checked snapshot.

## Distribution

Package the command and web assets as a Python project installable with `uv tool`.
Support installation from Git before a package-index release. Upgrades and
uninstallation are explicit user actions. Keep `python3 beads_map.py` as the
source-checkout fallback during the transition.

## Verification

Ordinary tests must not depend on a live Beads database.

- Fast Python tests cover the CLI, port selection, HTTP interface, version checks,
  subprocess timeouts, normalization, hashing, refresh serialization, stale
  fallback, catalog locking, merging, permissions, atomic persistence, mutation
  validation, command construction, conflicts, and write/refresh failures.
- Fixture tests cover representative and malformed exports, missing dependency
  endpoints, unknown fields, missing or moved repositories, filters, long paths,
  and transient read failures.
- Development-only browser smoke and performance tests exercise the real SVG
  workspace through 1,000 nodes and 3,000 edges, including pan, zoom, selection,
  filtering, path focus, repository switching, view restoration, metadata Save
  and Cancel, stale conflict recovery, failure retention, and narrow layout.
- A small optional integration suite may run against an installed supported `bd`.

## Delivery order

1. Package the current POC as the `beads-map` uv tool without changing its stack.
2. Extract the three responsibilities above and harden the Beads and catalog
   boundaries.
3. Complete the specified graph navigation, details, recovery, and accessibility
   behavior in the existing web asset.
4. Add the fixture, browser, and scale gates, then publish the first release.

The source of truth for rationale remains the closed decision tickets under the
Beads map `beads-map-lnd`; this document is their concise implementation handoff.
