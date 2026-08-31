# Beads Map

A tiny dependency graph for local Beads repositories with explicit editing for
five metadata fields. Each graph stays repository-scoped; use the header
selector to switch between them.

Requires Python 3.11 or newer, `uv`, and `bd >=1.1,<2` on `PATH`.

## Install

```bash
uv tool install git+https://github.com/heliopais/beads-map.git
beads-map /path/to/repository [/path/to/another/repository]
```

The app opens on loopback port 8765, or another free port when 8765 is already
in use. Use `--no-browser` to launch without opening a browser, or `--port 9000`
to require a specific port. Repositories passed on the command line are
remembered, along with the last selection. Later, `beads-map` reopens that
catalog. You can also add and remove repositories from the header; on macOS,
Add opens the native folder chooser, so no path entry is required.
Missing, moved, unreadable, and invalid catalog entries remain visible with a
warning. Select one to Retry it, Locate its replacement with the folder picker,
or Remove only that catalog entry; failed recovery keeps the current graph.

Upgrade or uninstall explicitly:

```bash
uv tool upgrade beads-map
uv tool uninstall beads-map
```

From a source checkout, the original launcher remains available without
installing the package:

```bash
python3 beads_map.py /path/to/repository
```

The app runs `bd --readonly -C <repository> export` and renders work
relationships from left to right with crossing-aware task ordering and routed
edge gutters. Solid edges are prerequisites, dashed edges are follow-on
provenance, and dotted edges are parent-child hierarchy; only prerequisites
affect Blocked state. Selecting a node shows its details, highlights direct
upstream and downstream relationships, and fades unrelated work without moving
the graph. The details panel can instead focus the complete prerequisite
Blockers path, dependent outcomes, or Both; these modes follow prerequisite
relationships transitively while leaving filters and node positions unchanged.
With a graph node focused, use Left/Right to enter its direct upstream or
downstream relationships and Up/Down to cycle multiple choices; the opposite
horizontal arrow returns to the starting node. Select it again or press Escape
to clear. The details panel groups available metadata and dates, exposes
clickable prerequisite, dependent, hierarchy, and follow-on relationships, and
shows description, acceptance criteria, design, notes, and timestamped comments
when Beads exports them. Empty or unknown fields are omitted safely. It can also
copy the selected bead ID. Search finds work by ID, title, description,
label, or assignee without filtering or relaying out the graph; Enter and
Shift-Enter cycle through matches. The status chips show or hide Completed, In
progress, Ready, Blocked, and Deferred work; the adjacent type chips and
multi-select Label and Assignee menus combine with them to narrow the graph
further. Multiple selections within a menu are alternatives, while separate
filter groups combine. Show all resets every filter. What’s ready? applies a
one-click preset for Ready work across every work type. When a filter hides an
intermediary task between two matching tasks, the graph retains it as a compact,
dashed Filter context card so the real prerequisite path remains visible and
inspectable. These context cards are not counted as filter matches, and Show all
restores their normal presentation. If filters hide every item, the canvas explains that Show all restores
the graph; an actually empty repository uses different wording. Epic nodes with
direct human-facing children show a simple closed/total
count; deferred children remain incomplete, and the count never changes the
epic's own state. Double-click an epic to open a focused sub-map containing the
epic and all of its nested child work, or use the `⤢` control shown on epic
cards. A sub-map starts with every status and type visible; use Back to full map
to restore the repository overview and its previous filters. Filter visibility
is remembered per repository. Use Epics for a compact repository-wide list with
direct-child progress; select an epic to reveal and center it, or open its
sub-map directly. Drag empty
canvas space to pan, or `Cmd`-drag vertically to zoom around the pointer. The
minimap appears when the graph extends beyond the viewport; click or drag it to
navigate the larger canvas. Export SVG downloads the currently rendered scope
and filters with resolved styling entirely in the browser. The
supported rendering envelope is 1,000 displayed issues and 3,000 displayed
relationships. Above it, the canvas pauses with complete snapshot counts and a
recommendation to narrow the existing filters; **Render best effort** explicitly
overrides the gate for that snapshot. The repeatable browser fixture and latest
measurements are in `docs/scale-verification.md`. The
graph checks for Beads changes every five seconds and skips redrawing when the
snapshot is unchanged. If a read fails, the last good graph stays visible and
is marked stale. After a successful refresh, added, newly completed, and
otherwise updated work is marked briefly by comparing only the two in-memory
snapshots; no history is stored.

Node coordinates are cached in memory per repository and epic scope. Filters
and metadata-only refreshes therefore preserve the user's mental map, while a
dependency change recomputes its connected component and leaves unrelated work
in place where space permits. **Re-layout** discards the current scope's cache
and recomputes the full arrangement; no manual coordinates are persisted.

Use **Edit** in the selected-bead details panel to change title, description,
priority, assignee, or labels. Save uses `bd update`, checks that the repository
snapshot has not changed since editing began, and refreshes the graph from Beads
afterward. Conflicts and write failures keep the draft for explicit recovery.
Status, type, workflow actions, relationships, issue creation/deletion, and sync
remain read-only.

The catalog stores repository paths and per-repository view preferences in the
operating system's user configuration directory; it never stores issue data or
edit drafts. Catalog updates are locked and atomically replaced so two running
Beads Map sessions do not lose one another's changes.
