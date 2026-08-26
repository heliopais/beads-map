# Beads Map POC

A tiny, read-only dependency graph for local Beads repositories. Each graph
stays repository-scoped; use the header selector to switch between them.

```bash
python3 beads_map.py /path/to/repository [/path/to/another/repository]
```

The app opens at `http://127.0.0.1:8765`. It requires Python 3 and `bd` on
`PATH`, but no package installation. Use `--no-browser` to launch without
opening a browser, or `--port 9000` to choose another port. Repositories passed
on the command line are remembered, along with the last selection. Later,
`python3 beads_map.py` reopens that catalog. You can also add and remove
repositories from the header; on macOS, Add opens the native folder chooser,
so no path entry is required.

The POC runs `bd --readonly -C <repository> export`, renders blocking
dependencies from left to right, and shows issue details when a node is
selected. The status chips show or hide Completed, In progress, Ready, Blocked,
and Deferred work. Drag empty canvas space to pan, or `Cmd`-drag vertically to
zoom around the pointer. It does not write to Beads. The catalog stores paths
only in the operating system's user configuration directory; it never stores
issue data.
