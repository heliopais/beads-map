# Beads Map

A tiny, read-only dependency graph for local Beads repositories. Each graph
stays repository-scoped; use the header selector to switch between them.

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
affect Blocked state. Selecting a node shows its details. The status chips show
or hide Completed, In progress, Ready, Blocked, and Deferred work. Drag empty
canvas space to pan, or `Cmd`-drag vertically to zoom around the pointer. The
graph checks for Beads changes every five seconds and skips redrawing when the
snapshot is unchanged. If a read fails, the last good graph stays visible and
is marked stale.

It does not write to Beads. The catalog stores repository paths and per-repository
view preferences in the operating system's user configuration directory; it
never stores issue data. Catalog updates are locked and atomically replaced so
two running Beads Map sessions do not lose one another's changes.
