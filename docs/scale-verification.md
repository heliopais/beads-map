# Browser scale verification

Use the deterministic standard-library fixture from the repository root:

```bash
python3 tests/scale_fixture.py --nodes 500 --edges 1500
python3 tests/scale_fixture.py --nodes 1000 --edges 3000
python3 tests/scale_fixture.py --nodes 1001 --edges 3001
```

For each supported fixture, verify initial load, search and Enter selection,
Completed filtering, canvas drag, and Zoom in. The fixture creates only a
temporary synthetic repository and catalog; `Ctrl-C` removes both.

## 2026-08-31 baseline

Measured in the Codex in-app Chromium browser on the development Mac:

| Nodes | Edges | Initial graph visible | Interaction result |
| ---: | ---: | ---: | --- |
| 500 | 1,500 | 293 ms | Search, selection, filtering, pan, and zoom passed |
| 1,000 | 3,000 | 415 ms | Search, selection, filtering, pan, and zoom passed |
| 1,001 | 3,001 | Paused | Full counts and guidance shown; narrowing and best-effort render passed |

These are local smoke-test timings, not a latency guarantee. Repeat after
material layout or rendering changes and record the environment with new
results.
