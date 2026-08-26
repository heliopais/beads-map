# Beads Map POC

A tiny, read-only dependency graph for one local Beads repository.

```bash
python3 beads_map.py /path/to/repository
```

The app opens at `http://127.0.0.1:8765`. It requires Python 3 and `bd` on
`PATH`, but no package installation. Use `--no-browser` to launch without
opening a browser, or `--port 9000` to choose another port.

The POC runs `bd --readonly -C <repository> export`, renders blocking
dependencies from left to right, and shows issue details when a node is
selected. It does not write to Beads.
